import os
# Ép hệ thống chỉ sử dụng 1 GPU (GPU 0), ẩn GPU 1 đi để tránh lỗi xung đột DDP của Unsloth Free
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
# Thiết lập cấu hình quản lý bộ nhớ của PyTorch để tránh phân mảnh VRAM
os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"

import torch
from datasets import load_dataset
from unsloth import FastLanguageModel
from trl import SFTTrainer, SFTConfig

# ==========================================
# 1. THIẾT LẬP SIÊU THAM SỐ (HYPERPARAMETERS)
# ==========================================
# Giảm xuống 2048 vì 900 từ tiếng Việt (~1300 tokens) hoàn toàn nằm gọn trong 2048 tokens.
# Điều này giúp giảm cực kỳ nhiều tải VRAM so với 4096.
MAX_SEQ_LENGTH = 2048  
DTYPE = None           # None cho tự động nhận diện (Float16 cho Tesla T4/V100, Bfloat16 cho Ampere trở lên)
LOAD_IN_4BIT = True    # Dùng QLoRA 4-bit để tiết kiệm VRAM (chạy được trên Colab T4 16GB VRAM)

# Tên mô hình nền tảng hỗ trợ tiếng Việt tốt
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct" 

# ==========================================
# 2. KHỞI TẠO MÔ HÌNH VÀ TOKENIZER QWEN 2.5
# ==========================================
print("--> Loading model and tokenizer...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_NAME,
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=DTYPE,
    load_in_4bit=LOAD_IN_4BIT,
)

# Cấu hình LoRA (PEFT)
print("--> Configuring LoRA adapters...")
model = FastLanguageModel.get_peft_model(
    model,
    r=16,                # Lora rank (8, 16, 32, 64)
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj"],
    lora_alpha=16,
    lora_dropout=0,      # Tối ưu hóa cho unsloth
    bias="none",         # Tối ưu hóa cho unsloth
    use_gradient_checkpointing="unsloth", # Tiết kiệm bộ nhớ tối đa
    random_state=3407,
    use_rslora=False,
    loftq_config=None,
)

# ==========================================
# 3. CHUẨN BỊ VÀ ĐỊNH DẠNG DỮ LIỆU HUẤN LUYỆN
# ==========================================
# Đọc file train_clean.json sẵn có (tự động phát hiện Kaggle hoặc Local)
KAGGLE_DATA_PATH = "/kaggle/input/datasets/bdragon1008/ai-race-dataset/train_clean.json"
LOCAL_DATA_PATH = "train_clean.json"

if os.path.exists(KAGGLE_DATA_PATH):
    DATA_PATH = KAGGLE_DATA_PATH
elif os.path.exists(LOCAL_DATA_PATH):
    DATA_PATH = LOCAL_DATA_PATH
else:
    raise FileNotFoundError(
        f"Không tìm thấy file dữ liệu ở cả đường dẫn Kaggle ({KAGGLE_DATA_PATH}) "
        f"và đường dẫn Local ({LOCAL_DATA_PATH})!"
    )

print(f"--> Loading dataset from {DATA_PATH}...")
# Unsloth sử dụng chat template để format dữ liệu tự động
def formatting_prompts_func(examples):
    convs = examples["conversations"]
    texts = []
    for conv in convs:
        # Chuyển đổi định dạng ShareGPT sang hội thoại dạng ChatML/Qwen
        # Mỗi lượt có 'from' (human/gpt) và 'value'
        formatted_chat = []
        for msg in conv:
            role = "user" if msg["from"] == "human" else "assistant"
            formatted_chat.append({"role": role, "content": msg["value"]})
        
        # Áp dụng template của tokenizer (eos_token tự động thêm vào)
        texts.append(tokenizer.apply_chat_template(formatted_chat, tokenize=False, add_generation_prompt=False))
    return { "text" : texts }

dataset = load_dataset("json", data_files=DATA_PATH, split="train")
dataset = dataset.map(formatting_prompts_func, batched=True)

# ==========================================
# 4. THIẾT LẬP THAM SỐ HUẤN LUYỆN (TRAINING ARGS)
# ==========================================
print("--> Setting up Training Arguments...")
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    dataset_num_proc=2,
    packing=False, # Có thể để True nếu muốn gộp các văn bản ngắn lại
    args=SFTConfig(
        per_device_train_batch_size=1, # Giảm xuống 1 để tránh OOM
        gradient_accumulation_steps=8, # Tăng lên 8 để giữ tổng batch_size = 8
        warmup_steps=10,
        num_train_epochs=1,        # 1 epoch với 8k+ mẫu là đủ để bắt đầu, tăng lên nếu loss vẫn giảm ổn định
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir="outputs",
        
        # 📌 SỬA LỖI TƯƠNG THÍCH TRANSFORMERS 5.x / 4.46+
        average_tokens_across_devices=False,
        
        # 📌 THIẾT LẬP CHECKPOINT NGẮN (FALLBACK) THEO KẾ HOẠCH V6.3
        # Đề phòng deadline gần kề, lưu checkpoint sau mỗi 10 steps
        save_strategy="steps",
        save_steps=10,
        save_total_limit=5,        # Chỉ giữ lại 5 checkpoint tốt/mới nhất để tránh đầy ổ đĩa
    ),
)

# Chạy huấn luyện
print("--> Starting training...")
trainer_stats = trainer.train()

# ==========================================
# 5. LƯU MÔ HÌNH SAU KHI TRAIN
# ==========================================
print("--> Saving fine-tuned LoRA model...")
# Chỉ lưu Lora Adapter (dung lượng nhẹ, khoảng vài chục MB)
model.save_pretrained("qwen2.5-7b-lora-adapter")
tokenizer.save_pretrained("qwen2.5-7b-lora-adapter")

print("--> Merging and saving final 16-bit model (this takes longer but is optimal for offline inference)...")
# Gộp trực tiếp lora adapter vào mô hình gốc và lưu thành bản 16-bit độc lập
model.save_pretrained_merged(
    "qwen2.5-7b-lora-merged", 
    tokenizer, 
    save_method="merged_16bit"
)

print("--> FINISHED! You can now use 'qwen2.5-7b-lora-merged' for offline inference.")

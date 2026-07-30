# 🤖 Hướng dẫn Fine-tune LLM (Qwen2.5-7B-Instruct)

Thư mục này dành cho **Thành viên 1** để thiết lập môi trường, viết notebook và huấn luyện mô hình LLM trích xuất thực thể & bối cảnh.

---

## 1. Cấu hình Huấn luyện Khuyến nghị
*   **Mô hình nền tảng:** `Qwen/Qwen2.5-7B-Instruct` hoặc `google/gemma-2-9b-it` (không vượt quá 9B tham số).
*   **Dữ liệu đầu vào:** Tệp `../train_clean.json` (chứa 8,223 mẫu bệnh án ShareGPT tiếng Việt).
*   **Framework khuyến nghị:** **Unsloth** (để train nhanh bằng QLoRA 4-bit trên Google Colab T4/A100 hoặc Kaggle).

---

## 2. Các siêu tham số LoRA gợi ý (Hyperparameters)
```python
# Cấu hình LoRA trong notebook
model = FastLanguageModel.get_peft_model(
    model,
    r = 16, # Hoặc 32 nếu cần học sâu hơn
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 32,
    lora_dropout = 0, # Tối ưu cho training speed
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
)
```

---

## 3. Quy tắc Checkpoint & Giới hạn Sinh (Inference)
*   **Lưu Checkpoint ngắn:** Bật cấu hình lưu checkpoint sau mỗi `5 - 10 steps` trong `TrainingArguments` (ví dụ: `save_steps=5` hoặc `save_steps=10`) để đề phòng deadline sát nút vẫn có thể lấy checkpoint gần nhất chạy nộp bài.
*   **JSON Schema:** Khi chạy inference trên tập test, cấu hình Generator ở chế độ **Structured Output** (hoặc dùng thư viện `Outlines`) để ép LLM sinh đúng định dạng JSON, loại bỏ hoàn toàn lỗi cú pháp.

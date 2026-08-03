"""
Chạy Qwen 2.5 7B + LoRA Adapter cục bộ bằng PEFT + transformers + bitsandbytes (không cần Unsloth).
Ghi kết quả vào pipeline/submission_list/submissionv3/ (ghi đè file cũ từ Kaggle nếu có).

YÊU CẦU: ~5GB VRAM (RTX 3050 Ti 4GB có thể sát ngưỡng, dùng CPU offload nếu OOM).
"""
import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

import torch
from peft import PeftModel
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)

# === Đường dẫn ===
PIPELINE_DIR = Path(__file__).parent
BASE_DIR = PIPELINE_DIR.parent

ADAPTER_PATH = BASE_DIR / "finetune_qwen_7b" / "qwen2.5-7b-lora-adapter"
INPUT_DIR    = BASE_DIR / "input_turn2_vong1" / "input"
OUTPUT_DIR   = BASE_DIR / "pipeline" / "submission_list" / "submissionv3"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Base model từ adapter_config
BASE_MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
MAX_NEW_TOKENS  = 1024

PROMPT_TEMPLATE = """\
Bạn là một chuyên gia y tế AI. Hãy phân tích đoạn văn bản lâm sàng tiếng Việt sau đây, trích xuất tất cả các thực thể y tế và trả về dưới dạng một danh sách JSON.

Với mỗi thực thể, bạn cần xác định:
1. `text`: Đoạn văn bản chính xác của thực thể. KHÔNG được tự ý sửa lỗi hay chuẩn hóa.
2. `position`: Vị trí ký tự bắt đầu và kết thúc [start, end] trong văn bản gốc.
3. `type`: Một trong: TRIỆU_CHỨNG, TÊN_XÉT_NGHIỆM, KẾT_QUẢ_XÉT_NGHIỆM, CHẨN_ĐOÁN, THUỐC.
4. `assertions`: Mảng thuộc tính ngữ cảnh: "isNegated", "isHistorical", "isFamily". Bỏ trống nếu không có.
5. `candidates`: Bỏ trống mảng [].

Văn bản lâm sàng:
\"\"\"
{text}
\"\"\"
"""

def split_text_into_chunks(text, max_words=256, overlap_words=60):
    words_data = []
    for m in re.finditer(r'\S+', text):
        words_data.append({"word": m.group(), "start": m.start(), "end": m.end()})
    if not words_data:
        return [{"text": text, "start_offset": 0}]
    chunks = []
    total_words = len(words_data)
    start_idx = 0
    while start_idx < total_words:
        end_idx = min(start_idx + max_words, total_words)
        char_start = words_data[start_idx]["start"]
        char_end   = words_data[end_idx - 1]["end"]
        chunks.append({"text": text[char_start:char_end], "start_offset": char_start})
        if end_idx == total_words:
            break
        start_idx = max(start_idx + 1, end_idx - overlap_words)
    return chunks


def run_inference(model, tokenizer, text):
    messages = [{"role": "user", "content": PROMPT_TEMPLATE.format(text=text)}]
    inputs = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
    ).to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            input_ids=inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            use_cache=True,
            do_sample=False,
            repetition_penalty=1.15,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id else tokenizer.eos_token_id,
        )

    generated_ids  = [out[len(inp):] for inp, out in zip(inputs, outputs)]
    generated_text = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

    try:
        clean_json = re.sub(r'^```json\s*|```$', '', generated_text.strip(), flags=re.MULTILINE)
        return json.loads(clean_json)
    except Exception as e:
        print(f"  ❌ Lỗi parse JSON: {e}")
        print(f"  Raw output: {generated_text[:300]}")
        return []


def main():
    print("=" * 80)
    print("  CHẠY QWEN 2.5 7B + LoRA ADAPTER CỤC BỘ (PEFT + transformers + bitsandbytes)")
    print("=" * 80)
    print(f"Base model:   {BASE_MODEL_NAME}")
    print(f"Adapter path: {ADAPTER_PATH}")
    print(f"Input dir:    {INPUT_DIR}")
    print(f"Output dir:   {OUTPUT_DIR}")

    # === Tải tokenizer từ adapter folder (chứa tokenizer.json, tokenizer_config.json) ===
    print("\n→ Tải tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(str(ADAPTER_PATH), trust_remote_code=True)

    # === Tải base model với 4-bit (bitsandbytes) ===
    print("→ Tải base model Qwen 7B ở dạng 4-bit (có thể mất vài phút lần đầu)...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",       # tự chia GPU/CPU nếu VRAM không đủ
        trust_remote_code=True,
    )

    # === Nạp LoRA adapter ===
    print(f"→ Nạp LoRA adapter từ {ADAPTER_PATH}...")
    model = PeftModel.from_pretrained(base_model, str(ADAPTER_PATH))
    model.eval()

    # === Chạy inference ===
    txt_files = sorted(
        list(INPUT_DIR.glob("*.txt")),
        key=lambda x: int(x.stem) if x.stem.isdigit() else 9999
    )
    print(f"\nTìm thấy {len(txt_files)} tệp. Bắt đầu inference Qwen...\n")

    for f in txt_files:
        text = f.read_text(encoding="utf-8")
        chunks = split_text_into_chunks(text, max_words=256, overlap_words=60)

        all_entities = []
        seen_positions = set()

        for chunk in chunks:
            chunk_text = chunk["text"]
            offset     = chunk["start_offset"]

            raw_ents = run_inference(model, tokenizer, chunk_text)
            for ent in raw_ents:
                pos = ent.get("position", [])
                if isinstance(pos, list) and len(pos) == 2:
                    ent["position"] = [pos[0] + offset, pos[1] + offset]
                key = (ent.get("position", [None])[0], ent.get("text", ""))
                if key not in seen_positions:
                    seen_positions.add(key)
                    all_entities.append(ent)

        out_f = OUTPUT_DIR / f"{f.stem}.json"
        with open(out_f, "w", encoding="utf-8") as out_file:
            json.dump(all_entities, out_file, ensure_ascii=False, indent=2)
        print(f"  -> {f.stem}.json: {len(all_entities)} thực thể")

    print("\n🎉 Hoàn thành! Kết quả Qwen lưu tại:", OUTPUT_DIR)


if __name__ == "__main__":
    main()

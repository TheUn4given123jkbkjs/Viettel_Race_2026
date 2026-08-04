"""
Chạy Qwen 2.5 7B qua Ollama local API (không cần fine-tune LoRA, test pipeline end-to-end).
Ghi kết quả vào pipeline/submission_list/submissionv3_ollama/ để không ghi đè submissionv3 gốc.
"""
import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# === Đường dẫn ===
PIPELINE_DIR = Path(__file__).parent
BASE_DIR     = PIPELINE_DIR.parent

INPUT_DIR    = BASE_DIR / "input_turn2_vong1" / "input"
OUTPUT_DIR   = BASE_DIR / "pipeline" / "submission_list" / "submissionv3_ollama"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"
MAX_WORDS    = 256
OVERLAP_WORDS = 60

SYSTEM_PROMPT = """Bạn là một chuyên gia y tế AI chuyên phân tích văn bản lâm sàng tiếng Việt.
Nhiệm vụ: Trích xuất TẤT CẢ thực thể y tế từ văn bản và trả về JSON list.
Quy tắc bắt buộc:
- Trả về DUY NHẤT một JSON array, không giải thích thêm.
- Trường "text" PHẢI là chuỗi con xuất hiện nguyên bản trong văn bản gốc.
- Trường "type": một trong TRIỆU_CHỨNG, TÊN_XÉT_NGHIỆM, KẾT_QUẢ_XÉT_NGHIỆM, CHẨN_ĐOÁN, THUỐC.
- Trường "assertions": mảng, chứa "isNegated", "isHistorical", "isFamily" nếu có, nếu không thì [].
- Trường "candidates": mảng rỗng [].
- Trường "position": [start_char_index, end_char_index] trong văn bản gốc."""

USER_TEMPLATE = """Văn bản lâm sàng:
\"\"\"
{text}
\"\"\"

Trả về JSON array:"""


def split_text_into_chunks(text, max_words=MAX_WORDS, overlap_words=OVERLAP_WORDS):
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


def ollama_generate(chunk_text):
    prompt = f"{SYSTEM_PROMPT}\n\n{USER_TEMPLATE.format(text=chunk_text)}"
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 1024,
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            generated_text = result.get("response", "")
    except urllib.error.URLError as e:
        print(f"  ⚠️ Ollama request failed: {e}")
        return []

    try:
        # Tìm JSON array trong response
        match = re.search(r'\[.*\]', generated_text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"  ❌ Lỗi parse JSON: {e}")
        print(f"  Raw: {generated_text[:200]}")
    return []


def main():
    print("=" * 80)
    print("  QWEN 2.5 7B LOCAL VIA OLLAMA (base model, no LoRA adapter)")
    print("=" * 80)
    print(f"Model:     {OLLAMA_MODEL}")
    print(f"Input:     {INPUT_DIR}")
    print(f"Output:    {OUTPUT_DIR}")

    # Kiểm tra Ollama đang chạy
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
            models = json.loads(r.read())
            names = [m["name"] for m in models.get("models", [])]
            if OLLAMA_MODEL not in names:
                print(f"❌ Model '{OLLAMA_MODEL}' không có trong Ollama. Chạy: ollama pull {OLLAMA_MODEL}")
                return
            print(f"✅ Ollama running, model '{OLLAMA_MODEL}' sẵn sàng.")
    except Exception as e:
        print(f"❌ Không kết nối được Ollama tại localhost:11434 ({e}). Hãy chạy: ollama serve")
        return

    txt_files = sorted(
        list(INPUT_DIR.glob("*.txt")),
        key=lambda x: int(x.stem) if x.stem.isdigit() else 9999
    )
    print(f"\nTìm thấy {len(txt_files)} tệp. Bắt đầu inference...\n")

    for f in txt_files:
        text = f.read_text(encoding="utf-8")
        chunks = split_text_into_chunks(text)
        all_entities = []
        seen = set()

        for chunk in chunks:
            raw_ents = ollama_generate(chunk["text"])
            offset = chunk["start_offset"]
            for ent in raw_ents:
                pos = ent.get("position", [])
                if isinstance(pos, list) and len(pos) == 2:
                    ent["position"] = [pos[0] + offset, pos[1] + offset]
                key = (ent.get("position", [None])[0], ent.get("text", ""))
                if key not in seen:
                    seen.add(key)
                    all_entities.append(ent)

        out_f = OUTPUT_DIR / f"{f.stem}.json"
        with open(out_f, "w", encoding="utf-8") as out_file:
            json.dump(all_entities, out_file, ensure_ascii=False, indent=2)
        print(f"  -> {f.stem}.json: {len(all_entities)} thực thể")

    print(f"\n🎉 Hoàn thành! Kết quả lưu tại: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

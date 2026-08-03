"""
Script chạy PhoBERT predictor đúng cách, dùng PhobertPredictor từ phobert_predictor.py.
Ghi kết quả vào input_turn2_vong1/output/ cho tất cả 100 file.
"""
import json
import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
BASE_DIR = PIPELINE_DIR.parent
sys.path.append(str(PIPELINE_DIR))

from phobert_predictor import PhobertPredictor

def main():
    PHOBERT_MODEL_PATH = BASE_DIR / "fine_tune_phobert" / "phobert_ner_model"
    INPUT_DIR = BASE_DIR / "input_turn2_vong1" / "input"
    OUTPUT_DIR = BASE_DIR / "input_turn2_vong1" / "output"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[PhoBERT] Model path: {PHOBERT_MODEL_PATH}")
    print(f"[PhoBERT] Input dir:  {INPUT_DIR}")
    print(f"[PhoBERT] Output dir: {OUTPUT_DIR}")

    predictor = PhobertPredictor(model_path=str(PHOBERT_MODEL_PATH))

    txt_files = sorted(
        list(INPUT_DIR.glob("*.txt")),
        key=lambda x: int(x.stem) if x.stem.isdigit() else 9999
    )

    print(f"\nTìm thấy {len(txt_files)} tệp. Bắt đầu suy luận PhoBERT...\n")

    for f in txt_files:
        text = f.read_text(encoding="utf-8")
        entities = predictor.predict(text)

        out_f = OUTPUT_DIR / f"{f.stem}.json"
        with open(out_f, "w", encoding="utf-8") as out_file:
            json.dump(entities, out_file, ensure_ascii=False, indent=2)

        print(f"  -> {f.name}: {len(entities)} thực thể -> {out_f.name}")

    print("\n🎉 Hoàn thành! Kết quả PhoBERT lưu tại: input_turn2_vong1/output/")

if __name__ == "__main__":
    main()

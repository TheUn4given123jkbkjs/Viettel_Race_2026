"""
Script rà soát toàn bộ 5,995 files để lập danh sách tất cả các cụm từ (entity text)
đang được map tới các mã ICD-10 kỳ quặc hoặc nghi ngờ sai.
"""
import json, sqlite3, re, sys
from pathlib import Path
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIRS = ["sample_A", "sample_C", "sample_Long"]
DB_PATH = BASE_DIR / "db" / "medical_codes.db"

def main():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Pre-load code names
    cursor.execute("SELECT code, name_vi FROM icd10")
    code_names = dict(cursor.fetchall())
    conn.close()
    
    # Collect text -> codes
    text_to_codes = defaultdict(Counter)
    code_to_texts = defaultdict(Counter)
    
    total_files = 0
    for s_dir in SAMPLE_DIRS:
        output_root = BASE_DIR / s_dir / "output"
        if not output_root.exists():
            continue
        for jf in sorted(output_root.rglob("*.json")):
            total_files += 1
            try:
                entities = json.loads(jf.read_text(encoding="utf-8"))
            except:
                try:
                    entities = json.loads(jf.read_text(encoding="utf-8-sig"))
                except:
                    continue
            if not isinstance(entities, list):
                continue
            
            for ent in entities:
                if ent.get("type") != "CHẨN_ĐOÁN":
                    continue
                text = ent.get("text", "").strip().lower()
                candidates = ent.get("candidates", [])
                for c in candidates:
                    text_to_codes[text][c] += 1
                    code_to_texts[c][text] += 1

    print(f"Quét {total_files} files, tìm thấy {len(text_to_codes)} text chẩn đoán độc bản.")
    
    # Suspicious code categories:
    # 1. Giang mai (A50-A53)
    # 2. Lậu / Rubella (A54, B06)
    # 3. Phá thai / Sảy thai (O00-O08)
    # 4. Thai sản Z35.x cho bệnh nhân không thai
    # 5. Y06 (Cẩu thả bỏ rơi)
    # 6. ĐTĐ sai mã (E12.9, E13, E13.0)
    
    suspicious_patterns = [
        ("A50", "A53", "Giang mai"),
        ("A54", "A54", "Lậu"),
        ("B06", "B06", "Rubella"),
        ("O00", "O08", "Sản khoa / Phá thai"),
        ("Z35", "Z35", "Theo dõi thai phụ"),
        ("Y06", "Y06", "Cẩu thả bỏ rơi"),
        ("E12", "E13", "ĐTĐ loại khác/suy dinh dưỡng")
    ]
    
    for start_code, end_code, label in suspicious_patterns:
        print(f"\n==================================================")
        print(f"  KIỂM TRA NHÓM: {label} ({start_code}..{end_code})")
        print(f"==================================================")
        
        found_codes = [c for c in code_to_texts if any(c.startswith(prefix) for prefix in [start_code, end_code]) or (start_code <= c <= end_code)]
        for c in sorted(set(found_codes)):
            texts = code_to_texts[c]
            c_name = code_names.get(c, "???")
            print(f"\n  Mã {c} ({c_name}) — xuất hiện {sum(texts.values())} lần:")
            for t, cnt in texts.most_common(5):
                print(f"    - [{cnt:3d}x] \"{t}\"")

if __name__ == "__main__":
    main()

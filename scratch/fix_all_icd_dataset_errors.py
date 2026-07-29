"""
Script hậu xử lý toàn diện: Quét 5,995 files JSON và áp dụng Smart ICD-10 Mapper
để sửa triệt để tất cả các lỗi ánh xạ ICD-10 trong toàn bộ tập dữ liệu.
"""
import os, json, sqlite3, re, sys
from pathlib import Path
from collections import Counter
from icd10_mapper import smart_icd10_lookup

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIRS = ["sample_A", "sample_C", "sample_Long"]
DB_PATH = BASE_DIR / "db" / "medical_codes.db"

# Danh sách các mã sai nghiêm trọng cần loại bỏ/thay thế bắt buộc
BAD_CODES = {
    "Y06", "Y06.2", "A50.04", "A54.84", "B06.81", "A52.06",
    "Z35.0", "Z35.1", "Z35.3", "Z35.4",
    "O04.0", "O03.0", "O03.5",
    "E12.9", "E13", "E13.0"
}

def compact_json_format(data):
    s = json.dumps(data, ensure_ascii=False, indent=2)
    s = re.sub(r'\[\s*\n\s*(\d+),\s*\n\s*(\d+)\s*\n\s*\]', r'[\1, \2]', s)
    s = re.sub(r'\[\s*\n\s*\]', r'[]', s)
    s = re.sub(r'\[\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1"]', s)
    s = re.sub(r'\[\s*\n\s*"([^"]+)",\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1", "\2"]', s)
    return s

def main():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    print("=" * 70)
    print("  SỬA TRIỆT ĐỂ LỖI ÁNH XẠ ICD-10 TRÊN TOÀN BỘ TẬP DỮ LIỆU")
    print("=" * 70)
    
    total_files = 0
    modified_files = 0
    fixed_entities = 0
    code_changes = Counter()
    
    for s_dir in SAMPLE_DIRS:
        output_root = BASE_DIR / s_dir / "output"
        if not output_root.exists():
            continue
            
        json_files = sorted(output_root.rglob("*.json"))
        dir_modified = 0
        
        for jf in json_files:
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
                
            file_modified = False
            
            for ent in entities:
                if ent.get("type") != "CHẨN_ĐOÁN":
                    continue
                    
                text = ent.get("text", "")
                candidates = ent.get("candidates", [])
                
                # Check if current candidates contain any bad code or if mapper has a better mapping
                has_bad_code = any(c in BAD_CODES for c in candidates)
                new_candidates = smart_icd10_lookup(cursor, text)
                
                if new_candidates and (has_bad_code or new_candidates != candidates):
                    for old_c in candidates:
                        for new_c in new_candidates:
                            if old_c != new_c:
                                code_changes[f"{old_c} -> {new_c}"] += 1
                    ent["candidates"] = new_candidates
                    file_modified = True
                    fixed_entities += 1
                    
            if file_modified:
                formatted = compact_json_format(entities)
                jf.write_text(formatted, encoding="utf-8")
                dir_modified += 1
                modified_files += 1
                
        print(f"  📂 {s_dir:12s}: Đã sửa {dir_modified}/{len(json_files)} files")
        
    print(f"\n{'=' * 70}")
    print(f"  KẾT QUẢ SỬA TOÀN BỘ")
    print(f"{'=' * 70}")
    print(f"  Tổng files quét: {total_files}")
    print(f"  Tổng files sửa: {modified_files}")
    print(f"  Tổng thực thể CHẨN_ĐOÁN được sửa: {fixed_entities}")
    
    print("\n  Top 15 thay đổi mã ICD-10 phổ biến nhất:")
    for change, cnt in code_changes.most_common(15):
        print(f"    - [{cnt:4d}x] {change}")
        
    conn.close()

if __name__ == "__main__":
    main()

"""
Thống kê chi tiết: với mỗi nhóm mã ICD-10 có tần suất cao bất thường,
liệt kê mã nghĩa trong DB + các entity text thực tế đang map đến nó.
Mục đích: hiểu rõ ngữ cảnh nào dùng mã nào trước khi sửa.
"""
import os, json, sqlite3, re, sys
from pathlib import Path
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIRS = ["sample_A", "sample_C", "sample_Long"]
DB_PATH = BASE_DIR / "db" / "medical_codes.db"

# Các mã cần điều tra (top 15 sau sửa FTS lần 1)
INVESTIGATE_CODES = [
    "I10", "E13.0", "E12.9", "E13", "I11", 
    "Z35.0", "Z35.1", "Z35.3",
    "A52.06", "I67.4", "A50.04", "B06.81", 
    "O04.0", "A54.84", "Y06"
]

def main():
    # 1. Tra cứu tên đầy đủ các mã trong DB
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    print("=" * 80)
    print("  THỐNG KÊ CHI TIẾT: MÃ ICD-10 TẦN SUẤT CAO")
    print("=" * 80)
    
    print("\n── 1. NGHĨA CỦA CÁC MÃ TRONG DATABASE ──\n")
    db_names = {}
    for code in INVESTIGATE_CODES:
        cursor.execute("SELECT code, name_vi FROM icd10 WHERE code = ?", (code,))
        row = cursor.fetchone()
        if row:
            db_names[code] = row[1]
            print(f"  {code:10s} → {row[1]}")
        else:
            db_names[code] = "(KHÔNG CÓ TRONG DB)"
            print(f"  {code:10s} → ⚠️ KHÔNG TÌM THẤY TRONG DATABASE")
    
    # 1.5. Tra thêm các mã liên quan ĐTĐ để hiểu toàn cảnh
    print("\n── 1.5. TẤT CẢ MÃ ĐÁI THÁO ĐƯỜNG TRONG DB ──\n")
    cursor.execute("SELECT code, name_vi FROM icd10 WHERE code LIKE 'E1%' ORDER BY code")
    for row in cursor.fetchall():
        print(f"  {row[0]:10s} → {row[1]}")
    
    conn.close()
    
    # 2. Thu thập entity text thực tế đang map đến từng mã
    print("\n── 2. CÁC ENTITY TEXT THỰC TẾ MAP ĐẾN TỪNG MÃ ──\n")
    
    code_to_entities = defaultdict(list)  # code -> [(text, sample_dir, filename)]
    code_to_cooccur = defaultdict(lambda: Counter())  # code -> Counter of co-occurring codes
    
    for s_dir in SAMPLE_DIRS:
        output_root = BASE_DIR / s_dir / "output"
        if not output_root.exists():
            continue
        for jf in sorted(output_root.rglob("*.json")):
            try:
                entities = json.loads(jf.read_text(encoding="utf-8"))
            except:
                try:
                    entities = json.loads(jf.read_text(encoding="utf-8-sig"))
                except:
                    continue
            if not isinstance(entities, list):
                continue
            
            # Collect all candidates in this file for co-occurrence
            all_codes_in_file = set()
            for ent in entities:
                for c in ent.get("candidates", []):
                    all_codes_in_file.add(c)
            
            for ent in entities:
                candidates = ent.get("candidates", [])
                etype = ent.get("type", "")
                text = ent.get("text", "")
                
                for code in candidates:
                    if code in INVESTIGATE_CODES:
                        code_to_entities[code].append((text, s_dir, jf.name))
                        # Co-occurrence: what other codes appear in the same file
                        for other in all_codes_in_file:
                            if other != code:
                                code_to_cooccur[code][other] += 1
    
    for code in INVESTIGATE_CODES:
        entries = code_to_entities.get(code, [])
        print(f"  ┌─ {code} ({db_names.get(code, '?')}) — {len(entries)} lần xuất hiện")
        
        # Đếm unique entity texts
        text_counter = Counter(e[0] for e in entries)
        print(f"  │  Unique entity texts: {len(text_counter)}")
        
        # Hiện top 8 entity text
        for txt, cnt in text_counter.most_common(8):
            sample_example = next(e for e in entries if e[0] == txt)
            print(f"  │  [{cnt:3d}x] \"{txt[:70]}\" ({sample_example[1]}/{sample_example[2]})")
        
        # Co-occurring codes (top 5)
        cooccur = code_to_cooccur.get(code, Counter())
        if cooccur:
            top_co = cooccur.most_common(5)
            co_str = ", ".join(f"{c}({n})" for c, n in top_co)
            print(f"  │  Top co-occurring codes: {co_str}")
        
        print(f"  └─")
        print()
    
    # 3. Phân tích nhóm ĐTĐ: E12.9 vs E13 vs E13.0
    print("\n── 3. PHÂN TÍCH CHÉO: CÁC FILE CÓ ĐỒNG THỜI E12.9 + E13 + E13.0 ──\n")
    
    triple_count = 0
    double_count = 0
    single_count = 0
    dtd_codes = {"E12.9", "E13", "E13.0"}
    
    for s_dir in SAMPLE_DIRS:
        output_root = BASE_DIR / s_dir / "output"
        if not output_root.exists():
            continue
        for jf in sorted(output_root.rglob("*.json")):
            try:
                entities = json.loads(jf.read_text(encoding="utf-8"))
            except:
                continue
            if not isinstance(entities, list):
                continue
            
            codes_in_file = set()
            for ent in entities:
                for c in ent.get("candidates", []):
                    if c in dtd_codes:
                        codes_in_file.add(c)
            
            if len(codes_in_file) == 3:
                triple_count += 1
            elif len(codes_in_file) == 2:
                double_count += 1
            elif len(codes_in_file) == 1:
                single_count += 1
    
    print(f"  Files có cả 3 mã (E12.9 + E13 + E13.0): {triple_count}")
    print(f"  Files có 2/3 mã: {double_count}")
    print(f"  Files có 1/3 mã: {single_count}")
    
    # 4. Phân tích nhóm Z35: Z35.0 vs Z35.1 vs Z35.3
    print("\n── 4. PHÂN TÍCH CHÉO: CÁC FILE CÓ ĐỒNG THỜI Z35.0 + Z35.1 + Z35.3 ──\n")
    z35_codes = {"Z35.0", "Z35.1", "Z35.3"}
    z_triple = 0
    for s_dir in SAMPLE_DIRS:
        output_root = BASE_DIR / s_dir / "output"
        if not output_root.exists():
            continue
        for jf in sorted(output_root.rglob("*.json")):
            try:
                entities = json.loads(jf.read_text(encoding="utf-8"))
            except:
                continue
            if not isinstance(entities, list):
                continue
            codes_in_file = set()
            for ent in entities:
                for c in ent.get("candidates", []):
                    if c in z35_codes:
                        codes_in_file.add(c)
            if len(codes_in_file) >= 2:
                z_triple += 1
    print(f"  Files có >= 2 mã Z35.x đồng thời: {z_triple}")

if __name__ == "__main__":
    main()

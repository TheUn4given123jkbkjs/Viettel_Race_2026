import os
import json
import sqlite3
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "db" / "medical_codes.db"

# Import smart_icd10_lookup
sys.path.append(str(BASE_DIR / "scratch"))
from icd10_mapper import smart_icd10_lookup

def compact_json_format(data):
    s = json.dumps(data, ensure_ascii=False, indent=2)
    s = re.sub(r'\[\s*\n\s*(\d+),\s*\n\s*(\d+)\s*\n\s*\]', r'[\1, \2]', s)
    s = re.sub(r'\[\s*\n\s*\]', r'[]', s)
    s = re.sub(r'\[\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1"]', s)
    s = re.sub(r'\[\s*\n\s*"([^"]+)",\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1", "\2"]', s)
    return s

def clean_drug_term(text):
    """Normalize drug names by removing dosages, units, and cleaning whitespace."""
    term = text.strip().lower()
    
    # Custom spelling corrections / fallback rules
    if "valsaan" in term:
        term = term.replace("valsaan", "valsartan")
    if "thuốcdigoxin" in term:
        term = "digoxin"
    if "tiêm hyaluronic" in term:
        term = "hyaluronic acid"
    if "ser***ine" in term:
        term = "sertraline"
        
    # Strip common dosage units and numbers (e.g. "10mg", "2.5mg", "50mcg")
    term = re.sub(r'\b\d+[\.,]?\d*\s*(mg|mcg|ml|g|%|iu|u)\b', '', term)
    term = re.sub(r'\b\d+\s*(mg|mcg|ml|g|%|iu|u)\b', '', term)
    term = re.sub(r'\b\d+\s*viên\b', '', term)
    term = re.sub(r'\b\d+\b', '', term)
    
    # Remove punctuation
    term = re.sub(r'[^\w\s]', ' ', term)
    term = re.sub(r'\s+', ' ', term).strip()
    return term

def query_rxnorm_from_db(cursor, text):
    """Query RxNorm CUI for a drug text, handling synonyms and cleanups."""
    term = clean_drug_term(text)
    if not term:
        return []
        
    # Standard resolution mappings for special abbreviations
    if term == "hrze":
        return ["104894"]
        
    match_term = re.sub(r'[^\w\s]', ' ', term).strip()
    candidates = []
    
    if match_term:
        cursor.execute("SELECT rxcui FROM rxnorm_fts WHERE name MATCH ? LIMIT 3", (match_term,))
        candidates = [row[0] for row in cursor.fetchall()]
        
    if not candidates:
        cursor.execute("SELECT rxcui FROM rxnorm WHERE name LIKE ? LIMIT 3", (f"%{term}%",))
        candidates = [row[0] for row in cursor.fetchall()]
        
    return candidates

def main():
    if not DB_PATH.exists():
        print(f"Error: Database {DB_PATH} not found.")
        sys.exit(1)
        
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    print("=" * 80)
    print("  QUY TRÌNH SỬA VÀ CẬP NHẬT CANDIDATES CHO TẬP DỮ LIỆU: SAMPLE D")
    print("=" * 80)
    
    output_dir = BASE_DIR / "sample_D" / "output"
    if not output_dir.exists():
        print(f"Error: {output_dir} does not exist.")
        sys.exit(1)
        
    json_files = sorted(list(output_dir.rglob("*.json")))
    print(f"Tìm thấy {len(json_files)} file JSON cần xử lý.")
    
    modified_files = 0
    fixed_icd = 0
    fixed_rx = 0
    
    for idx, jf in enumerate(json_files):
        try:
            entities = json.loads(jf.read_text(encoding="utf-8"))
        except:
            entities = json.loads(jf.read_text(encoding="utf-8-sig", errors="replace"))
            
        file_modified = False
        
        for ent in entities:
            etype = ent.get("type", "")
            text = ent.get("text", "")
            candidates = ent.get("candidates", [])
            
            if etype == "CHẨN_ĐOÁN":
                new_candidates = smart_icd10_lookup(cursor, text)
                if new_candidates != candidates:
                    ent["candidates"] = new_candidates
                    file_modified = True
                    fixed_icd += 1
                    
            elif etype == "THUỐC":
                new_candidates = query_rxnorm_from_db(cursor, text)
                if new_candidates != candidates:
                    ent["candidates"] = new_candidates
                    file_modified = True
                    fixed_rx += 1
                    
        if file_modified:
            formatted = compact_json_format(entities)
            jf.write_text(formatted, encoding="utf-8")
            modified_files += 1
            
    print(f"\n{'=' * 80}")
    print("  KẾT QUẢ CẬP NHẬT CHUNG")
    print(f"{'=' * 80}")
    print(f"Tổng số file JSON đã duyệt: {len(json_files)}")
    print(f"Tổng số file JSON đã sửa:   {modified_files}")
    print(f"Số lượng mã ICD-10 đã sửa:  {fixed_icd}")
    print(f"Số lượng mã RxNorm đã sửa:  {fixed_rx}")
    
    conn.close()

if __name__ == "__main__":
    main()

"""
Script hậu xử lý (post-processing) quét toàn bộ 5,995 file JSON của các tập dữ liệu,
tự động làm sạch thực thể và điền bổ sung mã candidates (ICD-10 / RxNorm) 
cho các thực thể đang bị thiếu (candidates rỗng []).
"""
import os
import json
import sqlite3
import re
import sys
from pathlib import Path

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIRS = ["sample_A", "sample_C", "sample_Long"]
DB_PATH = BASE_DIR / "db" / "medical_codes.db"

ACRONYMS = {
    "tha": "tăng huyết áp",
    "đtđ": "đái tháo đường",
    "copd": "phổi tắc nghẽn mãn tính",
    "vp": "viêm phổi",
    "tbmmn": "tai biến mạch máu não",
    "nmct": "nhồi máu cơ tim",
    "gút": "gout",
    "hp": "helicobacter pylori"
}

def clean_entity_text(text, etype):
    term = text.strip().lower()
    
    # 1. Bỏ dấu sao che thuốc (************)
    term = re.sub(r'\*+', '', term).strip()
    
    # 2. Xử lý viết tắt ngoặc đơn
    match_paren = re.search(r'\((.*?)\)', term)
    if match_paren:
        inside = match_paren.group(1).strip()
        outside = re.sub(r'\(.*?\)', '', term).strip()
        term = inside if len(inside) > len(outside) else outside
        
    # 3. Loại bỏ đơn vị/liều lượng thuốc
    if etype == "THUỐC":
        term = re.sub(r'\b\d+\s*(mg|g|ml|mcg|iu|%)\b', '', term).strip()
        term = re.sub(r'\b\d+\b', '', term).strip()
        
    # 4. Thay thế viết tắt phổ biến ngoài ngoặc
    for acr, full_name in ACRONYMS.items():
        term = re.sub(rf'\b{acr}\b', full_name, term)
        
    return term.strip()

def query_smart(cursor, entity_text, entity_type):
    cleaned = clean_entity_text(entity_text, entity_type)
    if not cleaned:
        return []
        
    candidates = []
    
    try:
        if entity_type == "CHẨN_ĐOÁN":
            # Thử 1: FTS MATCH
            match_term = re.sub(r'[^\w\s]', ' ', cleaned).strip()
            if match_term:
                cursor.execute("SELECT code FROM icd10_fts WHERE name_vi MATCH ? LIMIT 3", (match_term,))
                candidates = [row[0] for row in cursor.fetchall()]
                
            # Thử 2: LIKE
            if not candidates:
                cursor.execute("SELECT code FROM icd10 WHERE name_vi LIKE ? LIMIT 3", (f"%{cleaned}%",))
                candidates = [row[0] for row in cursor.fetchall()]
                
            # Thử 3: Cụm từ quá dài -> lấy 2 từ đầu
            if not candidates and len(cleaned.split()) > 3:
                short_term = " ".join(cleaned.split()[:2])
                cursor.execute("SELECT code FROM icd10_fts WHERE name_vi MATCH ? LIMIT 3", (short_term,))
                candidates = [row[0] for row in cursor.fetchall()]
                
        elif entity_type == "THUỐC":
            # Thử 1: FTS MATCH
            match_term = re.sub(r'[^\w\s]', ' ', cleaned).strip()
            if match_term:
                cursor.execute("SELECT rxcui FROM rxnorm_fts WHERE name MATCH ? LIMIT 3", (match_term,))
                candidates = [row[0] for row in cursor.fetchall()]
            
            # Thử 2: LIKE
            if not candidates:
                cursor.execute("SELECT rxcui FROM rxnorm WHERE name LIKE ? LIMIT 3", (f"%{cleaned}%",))
                candidates = [row[0] for row in cursor.fetchall()]
                
            # Thử 3: Tách từ thứ nhất
            if not candidates and len(cleaned.split()) > 1:
                first_word = cleaned.split()[0]
                cursor.execute("SELECT rxcui FROM rxnorm WHERE name LIKE ? LIMIT 3", (f"%{first_word}%",))
                candidates = [row[0] for row in cursor.fetchall()]
                
    except Exception:
        pass
        
    return candidates

def compact_json_format(data):
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    json_str = re.sub(r'\[\s*\n\s*(\d+),\s*\n\s*(\d+)\s*\n\s*\]', r'[\1, \2]', json_str)
    json_str = re.sub(r'\[\s*\n\s*\]', r'[]', json_str)
    json_str = re.sub(r'\[\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1"]', json_str)
    json_str = re.sub(r'\[\s*\n\s*"([^"]+)",\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1", "\2"]', json_str)
    return json_str

def main():
    if not DB_PATH.exists():
        print(f"Lỗi: Không tìm thấy database tại {DB_PATH}")
        sys.exit(1)
        
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    total_processed = 0
    total_modified = 0
    total_fixed_entities = 0
    
    print("======================================================================")
    print("  BẮT ĐẦU SỬA LỖI THIẾU CANDIDATES TRÊN TOÀN BỘ TẬP DỮ LIỆU")
    print("======================================================================")
    
    for s_dir in SAMPLE_DIRS:
        print(f"\n📂 Đang quét tập mẫu: {s_dir}...")
        output_root = BASE_DIR / s_dir / "output"
        if not output_root.exists():
            print(f" -> Thư mục output không tồn tại, bỏ qua.")
            continue
            
        json_files = list(output_root.rglob("*.json"))
        print(f" -> Tìm thấy {len(json_files)} file JSON.")
        
        modified_in_set = 0
        fixed_in_set = 0
        
        for fpath in json_files:
            total_processed += 1
            
            try:
                content = fpath.read_text(encoding="utf-8")
                entities = json.loads(content)
            except Exception as e:
                try:
                    content = fpath.read_text(encoding="utf-8-sig")
                    entities = json.loads(content)
                except Exception as e:
                    # Bỏ qua nếu lỗi định dạng file
                    continue
                    
            if not isinstance(entities, list):
                continue
                
            file_modified = False
            for ent in entities:
                etype = ent.get("type", "")
                candidates = ent.get("candidates", [])
                
                # Chỉ xử lý các thực thể CHẨN_ĐOÁN hoặc THUỐC bị rỗng candidates
                if etype in ["CHẨN_ĐOÁN", "THUỐC"] and not candidates:
                    text = ent.get("text", "")
                    if text:
                        res_codes = query_smart(cursor, text, etype)
                        if res_codes:
                            ent["candidates"] = res_codes
                            file_modified = True
                            fixed_in_set += 1
                            total_fixed_entities += 1
                            
            if file_modified:
                # Ghi lại file JSON với định dạng gọn gàng ban đầu
                formatted = compact_json_format(entities)
                try:
                    fpath.write_text(formatted, encoding="utf-8")
                    modified_in_set += 1
                    total_modified += 1
                except Exception as e:
                    print(f"Lỗi khi ghi file {fpath.name}: {e}")
                    
        print(f" -> Hoàn tất {s_dir}: sửa đổi {modified_in_set} files, bổ sung {fixed_in_set} nhãn candidates.")
        
    conn.close()
    
    print("\n======================================================================")
    print("  HOÀN TẤT HẬU XỬ LÝ SỬA CANDIDATES")
    print("======================================================================")
    print(f" - Tổng số file JSON đã quét: {total_processed}")
    print(f" - Tổng số file JSON được cập nhật: {total_modified}")
    print(f" - Tổng số thực thể được bổ sung candidates thành công: {total_fixed_entities}")
    print("======================================================================")

if __name__ == "__main__":
    main()

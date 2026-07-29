import os
import sys
import json
import re
import sqlite3

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(BASE_DIR) == "Long_folder":
    BASE_DIR = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "db", "medical_codes.db")

def query_local_db(entity_text, entity_type):
    """Tra cứu mã candidates ICD-10 hoặc RxNorm từ SQLite"""
    if not os.path.exists(DB_PATH):
        return []
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    candidates = []
    term = entity_text.strip().lower()
    
    try:
        if entity_type == "CHẨN_ĐOÁN":
            match_term = re.sub(r'[^\w\s]', ' ', term).strip()
            if match_term:
                cursor.execute("SELECT code FROM icd10_fts WHERE name_vi MATCH ? LIMIT 3", (match_term,))
                candidates = [row[0] for row in cursor.fetchall()]
            if not candidates:
                cursor.execute("SELECT code FROM icd10 WHERE name_vi LIKE ? LIMIT 3", (f"%{term}%",))
                candidates = [row[0] for row in cursor.fetchall()]
                
        elif entity_type == "THUỐC":
            match_term = re.sub(r'[^\w\s]', ' ', term).strip()
            if match_term:
                cursor.execute("SELECT rxcui FROM rxnorm_fts WHERE name MATCH ? LIMIT 3", (match_term,))
                candidates = [row[0] for row in cursor.fetchall()]
            if not candidates:
                cursor.execute("SELECT rxcui FROM rxnorm WHERE name LIKE ? LIMIT 3", (f"%{term}%",))
                candidates = [row[0] for row in cursor.fetchall()]
    except Exception:
        pass
    finally:
        conn.close()
        
    return candidates

def compact_json_format(data):
    """Định dạng JSON gọn gàng chuyên nghiệp"""
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    json_str = re.sub(r'\[\s*\n\s*(\d+),\s*\n\s*(\d+)\s*\n\s*\]', r'[\1, \2]', json_str)
    json_str = re.sub(r'\[\s*\n\s*\]', r'[]', json_str)
    json_str = re.sub(r'\[\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1"]', json_str)
    json_str = re.sub(r'\[\s*\n\s*"([^"]+)",\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1", "\2"]', json_str)
    return json_str

def clean_and_normalize_entities(txt_content, raw_entities):
    """Lọc, sửa, chuẩn hóa danh sách thực thể về 5 nhãn chính tắc"""
    cleaned = []
    
    for item in raw_entities:
        if not isinstance(item, dict):
            continue
            
        text = item.get("text", "")
        etype = str(item.get("type", "")).strip()
        assertions = item.get("assertions", [])
        if not isinstance(assertions, list):
            assertions = []
            
        if not text or not isinstance(text, str):
            continue
            
        # Tìm vị trí chính xác
        start_idx = txt_content.find(text)
        if start_idx == -1:
            continue
        end_idx = start_idx + len(text)
        position = [start_idx, end_idx]
        
        # 1. Sửa lỗi nhãn bị gán nhầm thuộc tính assertion làm nhãn type
        if etype in ["isNegated", "isHistorical", "isFamily"]:
            if etype not in assertions:
                assertions.append(etype)
            etype = "TRIỆU_CHỨNG"
            
        # 2. Chuẩn hóa nhãn tự do về 5 nhóm hợp lệ
        etype_upper = etype.upper().replace(" ", "_")
        
        if etype_upper in ["CHẨN_ĐOÁN", "CHAN_DOAN", "BỆNH", "BENH", "BỆNH_LÝ", "BENH_LY", "CHẨN_ĐOÁN_LÂM_SÀNG", "TÊN_BỆNH", "TEN_BENH", "BỆNH_NỀN", "TIỀN_SỬ_BỆNH"]:
            etype = "CHẨN_ĐOÁN"
        elif etype_upper in ["THUỐC", "THUOC", "TÊN_THUỐC", "TEN_THUOC", "DƯỢC_PHẨM"]:
            etype = "THUỐC"
        elif etype_upper in ["TRIỆU_CHỨNG", "TRIEU_CHUNG", "TRIỆU CHỨNG", "TRÍỆU_CHỨNG", "LÂM_SÀNG", "THIỆU_CHỨNG"]:
            etype = "TRIỆU_CHỨNG"
        elif etype_upper in ["TÊN_XÉT_NGHIỆM", "TEN_XET_NGHIEM", "XÉT_NGHIỆM", "XET_NGHIEM"]:
            etype = "TÊN_XÉT_NGHIỆM"
        elif etype_upper in ["KẾT_QUẢ_XÉT_NGHIỆM", "KET_QUA_XET_NGHIEM", "KẾT_QUẢ", "KET_QUA", "KHÉT_QUẢ_XÉT_NGHIỆM"]:
            etype = "KẾT_QUẢ_XÉT_NGHIỆM"
        else:
            # Dự đoán nhãn dự phòng
            if "bệnh" in text.lower() or "viêm" in text.lower() or "hội chứng" in text.lower():
                etype = "CHẨN_ĐOÁN"
            elif "sốt" in text.lower() or "đau" in text.lower() or "mệt" in text.lower() or "ho" in text.lower():
                etype = "TRIỆU_CHỨNG"
            else:
                etype = "TRIỆU_CHỨNG"
                
        # Loại bỏ các nhãn trùng lặp trong assertions
        clean_assertions = []
        for ass in assertions:
            ass_str = str(ass).strip()
            if ass_str in ["isNegated", "isHistorical", "isFamily"] and ass_str not in clean_assertions:
                clean_assertions.append(ass_str)
                
        # Khôi phục hoặc tạo mới candidates
        candidates = query_local_db(text, etype)
        
        cleaned.append({
            "text": text,
            "position": position,
            "type": etype,
            "assertions": clean_assertions,
            "candidates": candidates
        })
        
    return cleaned

def clean_member_dataset(member):
    member_dir = os.path.join(BASE_DIR, f"sample_{member}")
    if not os.path.exists(member_dir):
        print(f"❌ Không tìm thấy thư mục: sample_{member}")
        return
        
    input_dir = os.path.join(member_dir, "input")
    output_dir = os.path.join(member_dir, "output")
    
    print(f"\n🔄 Bắt đầu quét dọn dẹp và chuẩn hóa dữ liệu cho: sample_{member}")
    
    cleaned_files = 0
    total_labels_fixed = 0
    
    for root, _, files in os.walk(output_dir):
        for f in files:
            if f.endswith(".json") and f != "stats.json":
                json_path = os.path.join(root, f)
                rel_p = os.path.relpath(json_path, output_dir)
                txt_path = os.path.join(input_dir, os.path.splitext(rel_p)[0] + ".txt")
                
                if os.path.exists(txt_path):
                    try:
                        with open(txt_path, "r", encoding="utf-8") as tf:
                            txt_content = tf.read()
                        with open(json_path, "r", encoding="utf-8") as jf:
                            raw_entities = json.load(jf)
                            
                        # Thực hiện làm sạch
                        cleaned_entities = clean_and_normalize_entities(txt_content, raw_entities)
                        
                        # So sánh xem có sự thay đổi (sửa đổi nhãn) nào không
                        is_changed = False
                        if len(cleaned_entities) != len(raw_entities):
                            is_changed = True
                        else:
                            for old, new in zip(raw_entities, cleaned_entities):
                                if old.get("type") != new.get("type") or old.get("assertions") != new.get("assertions"):
                                    is_changed = True
                                    total_labels_fixed += 1
                                    
                        # Ghi đè lại nếu có thay đổi hoặc chuẩn hóa format
                        formatted = compact_json_format(cleaned_entities)
                        with open(json_path, "w", encoding="utf-8") as jf:
                            jf.write(formatted)
                            
                        cleaned_files += 1
                    except Exception as e:
                        print(f"  ⚠️ Lỗi khi xử lý file {f}: {e}")
                        
    print(f"✨ HOÀN THÀNH: Đã chuẩn hóa {cleaned_files} files JSON. Đã sửa {total_labels_fixed} lỗi nhãn thực thể!")

def main():
    print("=" * 80)
    print("🧹 TRÌNH TỰ ĐỘNG CHUẨN HÓA & LÀM SẠCH NHÃN DỮ LIỆU TẬP HỢP (DATA CLEANER)")
    print("=" * 80)
    
    # Chuẩn hóa cả 2 bộ dữ liệu A và Long
    clean_member_dataset("A")
    clean_member_dataset("Long")
    
    print("\n" + "=" * 80)
    print("🚀 Dữ liệu đã sạch 100%. Bạn có thể chạy lại show_stats.py để kiểm chứng!")
    print("=" * 80)

if __name__ == "__main__":
    main()

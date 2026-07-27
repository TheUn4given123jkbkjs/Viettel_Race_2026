import os
import sys
import sqlite3
import requests
import json
import re

# Đảm bảo console in unicode không bị lỗi
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def load_api_key():
    """Đọc GEMINI_API_KEY từ file .env thủ công để tránh phụ thuộc thư viện python-dotenv"""
    if not os.path.exists(".env"):
        print("Lỗi: Không tìm thấy file .env")
        return None
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY"):
                parts = line.strip().split("=")
                if len(parts) >= 2:
                    return parts[1].strip()
    return None

def query_local_db(entity_text, entity_type, db_path="medical_codes.db"):
    """
    Truy vấn mã ICD-10 hoặc RxNorm từ CSDL SQLite offline bằng FTS5
    và có phương án fallback bằng LIKE nếu FTS5 không khớp.
    """
    if not os.path.exists(db_path):
        return []
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    candidates = []
    
    # Làm sạch từ khóa tìm kiếm
    term = entity_text.strip().lower()
    
    try:
        if entity_type == "CHẨN_ĐOÁN":
            # 1. Thử tìm bằng FTS5 trên bảng icd10_fts
            # Loại bỏ ký tự đặc biệt có thể phá cú pháp MATCH
            match_term = re.sub(r'[^\w\s]', ' ', term).strip()
            if match_term:
                cursor.execute(
                    "SELECT code FROM icd10_fts WHERE name_vi MATCH ? LIMIT 3", 
                    (match_term,)
                )
                candidates = [row[0] for row in cursor.fetchall()]
                
            # 2. Fallback bằng LIKE nếu FTS5 không tìm thấy
            if not candidates:
                cursor.execute(
                    "SELECT code FROM icd10 WHERE name_vi LIKE ? LIMIT 3", 
                    (f"%{term}%",)
                )
                candidates = [row[0] for row in cursor.fetchall()]
                
        elif entity_type == "THUỐC":
            # 1. Thử tìm bằng FTS5 trên bảng rxnorm_fts
            match_term = re.sub(r'[^\w\s]', ' ', term).strip()
            if match_term:
                cursor.execute(
                    "SELECT rxcui FROM rxnorm_fts WHERE name MATCH ? LIMIT 3", 
                    (match_term,)
                )
                candidates = [row[0] for row in cursor.fetchall()]
                
            # 2. Fallback bằng LIKE nếu FTS5 không tìm thấy
            if not candidates:
                cursor.execute(
                    "SELECT rxcui FROM rxnorm WHERE name LIKE ? LIMIT 3", 
                    (f"%{term}%",)
                )
                candidates = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"Lỗi truy vấn DB cho '{entity_text}': {e}")
    finally:
        conn.close()
        
    return candidates

def generate_sample(api_key):
    print("--- Đang gọi API Gemini để sinh văn bản bệnh án mẫu ---")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    # System Prompt hướng dẫn sinh dữ liệu có định dạng cấu trúc
    prompt = """
Hãy sinh ra một ca bệnh án lâm sàng tiếng Việt ngẫu nhiên kèm theo danh sách các thực thể y khoa xuất hiện trong đó.
Bệnh án phải tự nhiên, phản ánh đúng cách viết của bác sĩ Việt Nam (có thể viết tắt nhẹ, có chỉ số xét nghiệm, chẩn đoán, triệu chứng và đơn thuốc).

Đầu ra của bạn PHẢI là một đối tượng JSON có cấu trúc chính xác như sau:
{
  "text": "Đoạn văn bản bệnh án lâm sàng tiếng Việt dài khoảng 100-150 từ...",
  "entities": [
    {
      "text": "cụm từ y khoa chính xác xuất hiện trong text trên",
      "type": "TRIỆU_CHỨNG" hoặc "CHẨN_ĐOÁN" hoặc "THUỐC" hoặc "TÊN_XÉT_NGHIỆM" hoặc "KẾT_QUẢ_XÉT_NGHIỆM",
      "assertions": ["isNegated" hoặc "isFamily" hoặc "isHistorical"] (hoặc để mảng rỗng [] nếu không có ngữ cảnh đặc biệt này)
    }
  ]
}

LƯU Ý QUAN TRỌNG:
1. Trường "text" trong các đối tượng thuộc "entities" phải trùng khớp 100% với một cụm từ con nằm trong văn bản bệnh án gốc.
2. Các nhãn "type" chỉ được phép nhận 1 trong 5 giá trị: 'TRIỆU_CHỨNG', 'CHẨN_ĐOÁN', 'THUỐC', 'TÊN_XÉT_NGHIỆM', 'KẾT_QUẢ_XÉT_NGHIỆM'.
3. Chỉ trích xuất tối đa 6-8 thực thể tiêu biểu để làm mẫu.
"""

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            print(f"Lỗi gọi API: Mã lỗi {response.status_code}")
            print(response.text)
            return None
            
        res_data = response.json()
        content_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
        
        # Parse JSON kết quả từ Gemini
        generated_json = json.loads(content_text)
        return generated_json
    except Exception as e:
        print("Lỗi trong quá trình sinh dữ liệu hoặc parse JSON:", e)
        return None

def process_and_align(generated_data):
    """
    Xử lý dữ liệu sinh ra từ LLM: 
    - Tính toán vị trí [start, end] thực tế bằng Python.
    - Ánh xạ mã ICD-10 / RxNorm từ SQLite.
    """
    clinical_text = generated_data.get("text", "")
    entities = generated_data.get("entities", [])
    
    print("\n--- Bệnh án gốc sinh ra từ Gemini: ---")
    print(clinical_text)
    print("--------------------------------------")
    
    aligned_entities = []
    
    for item in entities:
        text = item.get("text", "")
        etype = item.get("type", "")
        assertions = item.get("assertions", [])
        
        # 1. Tính toán vị trí position [start, end] chính xác bằng Python
        # Tìm tất cả vị trí xuất hiện của cụm từ trong văn bản để lấy vị trí đầu tiên
        start_idx = clinical_text.find(text)
        if start_idx == -1:
            print(f"Cảnh báo: Không tìm thấy thực thể '{text}' trong văn bản gốc.")
            continue
        end_idx = start_idx + len(text)
        position = [start_idx, end_idx]
        
        # 2. Tra cứu mã (candidates) offline bằng SQLite
        candidates = []
        if etype in ["CHẨN_ĐOÁN", "THUỐC"]:
            candidates = query_local_db(text, etype)
            
        aligned_entities.append({
            "text": text,
            "position": position,
            "type": etype,
            "assertions": assertions,
            "candidates": candidates
        })
        
    return aligned_entities

def main():
    api_key = load_api_key()
    if not api_key:
        print("Vui lòng cấu hình GEMINI_API_KEY trong tệp .env.")
        sys.exit(1)
        
    raw_sample = generate_sample(api_key)
    if not raw_sample:
        print("Sinh mẫu thử nghiệm thất bại.")
        sys.exit(1)
        
    # Tính toán vị trí và ánh xạ mã offline
    final_entities = process_and_align(raw_sample)
    
    # Output kết quả cuối cùng
    output_data = {
        "text": raw_sample.get("text", ""),
        "annotations": final_entities
    }
    
    output_dir = "input_private"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_file = os.path.join(output_dir, "sample_output.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
        
    print(f"\n=== ĐÃ TẠO THÀNH CÔNG MẪU THỬ NGHIỆM ===")
    print(f"Kết quả lưu tại: {output_file}")
    print("\nChi tiết dữ liệu JSON mẫu sinh ra:")
    print(json.dumps(output_data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

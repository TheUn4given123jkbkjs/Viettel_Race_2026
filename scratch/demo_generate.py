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
    
    # System Prompt hướng dẫn sinh dữ liệu mô phỏng chính xác 3 loại văn phong trong đề thi
    prompt = """
Hãy sinh ra một văn bản y khoa tiếng Việt ngẫu nhiên mô phỏng theo một trong ba phong cách thực tế dưới đây (chọn ngẫu nhiên một phong cách):

PHONG CÁCH 1: Bệnh án lâm sàng bán cấu trúc (Case Report)
Định dạng mẫu:
1.  Tiền sử bệnh
    Các bệnh lý mạn tính:
    - [Tên bệnh hoặc thuốc]
2.  Bệnh sử hiện tại / Tiền sử bệnh hiện tại
    Lý do nhập viện: [Lý do]
    Triệu chứng hiện tại:
    - [Triệu chứng]
    Diễn biến bệnh:
    - ...
    Triệu chứng khi nhập viện:
    - ...
3.  Đánh giá tại bệnh viện / Điều trị

PHONG CÁCH 2: Diễn đàn Q&A y khoa (Hỏi & Trả lời tư vấn)
Định dạng mẫu:
Hỏi : [Câu hỏi của người bệnh, kể về triệu chứng, thuốc đang dùng, tình trạng mang thai...]
Trả lời : Chào em, [Lời khuyên của bác sĩ, giải thích thuốc, tác dụng phụ...]

PHONG CÁCH 3: Bài viết thông tin y khoa giáo dục
Định dạng mẫu:
[TÊN BỆNH] LÀ GÌ?
1. [Tên bệnh] là bệnh gì?
[Đoạn văn mô tả...]
2. Dấu hiệu và triệu chứng
- [Dấu hiệu 1]
- [Dấu hiệu 2]

--- YÊU CẦU ĐẦU RA ---
Đầu ra của bạn PHẢI là một đối tượng JSON có cấu trúc chính xác như sau:
{
  "text": "Đoạn văn bản y khoa thô sinh ra (giữ nguyên toàn bộ các dấu xuống dòng \\n, dấu đầu dòng • hoặc -, căn lề khoảng trắng thụt lề thụ động giống hệt định dạng thực tế của phong cách đã chọn)",
  "entities": [
    {
      "text": "cụm từ y khoa trích xuất chính xác 100% từng ký tự xuất hiện trong text trên",
      "type": "TRIỆU_CHỨNG" hoặc "CHẨN_ĐOÁN" hoặc "THUỐC" hoặc "TÊN_XÉT_NGHIỆM" hoặc "KẾT_QUẢ_XÉT_NGHIỆM",
      "assertions": ["isNegated" hoặc "isFamily" hoặc "isHistorical"] (hoặc để mảng rỗng [] nếu không có ngữ cảnh đặc biệt này)
    }
  ]
}

LƯU Ý LỚN:
1. Văn phong tiếng Việt tự nhiên, có thể chứa một số thuật ngữ tiếng Anh viết tắt (ví dụ: THA, ĐTĐ, COPD, WBC, ct sọ, ran ẩm, x-quang, paracetamol, amlodipine...) y hệt thực tế lâm sàng Việt Nam.
2. Trường 'text' trong 'entities' phải khớp hoàn hảo (phân biệt cả hoa thường) với cụm từ con trong trường 'text' gốc của bệnh án để tránh lỗi không tìm thấy.
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

def compact_json_format(data):
    """Định dạng JSON thụt lề nhưng giữ các mảng ngắn trên cùng một dòng (như position, assertions, candidates)"""
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    # Gộp mảng số (ví dụ: [79, 113])
    json_str = re.sub(r'\[\s*\n\s*(\d+),\s*\n\s*(\d+)\s*\n\s*\]', r'[\1, \2]', json_str)
    # Gộp mảng rỗng []
    json_str = re.sub(r'\[\s*\n\s*\]', r'[]', json_str)
    # Gộp mảng chuỗi 1 phần tử (ví dụ: ["isHistorical"] hoặc ["1191"])
    json_str = re.sub(r'\[\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1"]', json_str)
    # Gộp mảng chuỗi 2 phần tử (ví dụ: ["K21.0", "K21.9"])
    json_str = re.sub(r'\[\s*\n\s*"([^"]+)",\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1", "\2"]', json_str)
    return json_str

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
    
    # Tách biệt tệp đầu ra tương tự như định dạng của cuộc thi
    output_dir = "input_private"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    text_content = raw_sample.get("text", "").strip()
    
    # 1. Ghi tệp .txt chứa văn bản thô (giữ nguyên xuống dòng)
    txt_file = os.path.join(output_dir, "sample_output.txt")
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(text_content)
        
    # 2. Ghi tệp .json chứa danh sách phẳng (flat list) của annotations y hệt định dạng Question.md
    json_file = os.path.join(output_dir, "sample_output.json")
    formatted_json = compact_json_format(final_entities)
    with open(json_file, "w", encoding="utf-8") as f:
        f.write(formatted_json)
        
    print(f"\n=== ĐÃ TẠO THÀNH CÔNG MẪU THỬ NGHIỆM ===")
    print(f"1. Văn bản bệnh án thô (LF) lưu tại: {txt_file}")
    print(f"2. Thực thể phẳng mẫu lưu tại: {json_file}")
    print("\nChi tiết danh sách thực thể JSON phẳng:")
    print(formatted_json)

if __name__ == "__main__":
    main()

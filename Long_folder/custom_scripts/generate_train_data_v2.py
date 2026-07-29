import os
import sys
import sqlite3
import requests
import json
import re
import time
import random
import argparse

# Đảm bảo in unicode không lỗi
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Xác định thư mục gốc của dự án (d:\AI Race\Viettel_Race_2026) dựa trên vị trí file script
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_api_key():
    """Đọc GEMINI_API_KEY từ biến môi trường OS trước, sau đó là file .env"""
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        return env_key.strip()
        
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        print(f"Lỗi: Không tìm thấy file .env tại '{env_path}'")
        return None
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY"):
                parts = line.strip().split("=")
                if len(parts) >= 2:
                    return parts[1].strip()
    return None

def query_local_db(entity_text, entity_type, db_path=None):
    """Truy vấn mã ICD-10 hoặc RxNorm từ SQLite"""
    if db_path is None:
        db_path = os.path.join(BASE_DIR, "db", "medical_codes.db")
        
    if not os.path.exists(db_path):
        return []
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    candidates = []
    
    term = entity_text.strip().lower()
    
    try:
        if entity_type == "CHẨN_ĐOÁN":
            # 1. Tìm bằng FTS5
            match_term = re.sub(r'[^\w\s]', ' ', term).strip()
            if match_term:
                cursor.execute(
                    "SELECT code FROM icd10_fts WHERE name_vi MATCH ? LIMIT 3", 
                    (match_term,)
                )
                candidates = [row[0] for row in cursor.fetchall()]
                
            # 2. Fallback bằng LIKE
            if not candidates:
                cursor.execute(
                    "SELECT code FROM icd10 WHERE name_vi LIKE ? LIMIT 3", 
                    (f"%{term}%",)
                )
                candidates = [row[0] for row in cursor.fetchall()]
                
        elif entity_type == "THUỐC":
            # 1. Tìm bằng FTS5
            match_term = re.sub(r'[^\w\s]', ' ', term).strip()
            if match_term:
                cursor.execute(
                    "SELECT rxcui FROM rxnorm_fts WHERE name MATCH ? LIMIT 3", 
                    (match_term,)
                )
                candidates = [row[0] for row in cursor.fetchall()]
                
            # 2. Fallback bằng LIKE
            if not candidates:
                cursor.execute(
                    "SELECT rxcui FROM rxnorm WHERE name LIKE ? LIMIT 3", 
                    (f"%{term}%",)
                )
                candidates = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        pass
    finally:
        conn.close()
        
    return candidates

def load_drugs_list():
    """Tải danh sách 348 hoạt chất từ db/rxnorm_mapped.json"""
    mapping_file = os.path.join(BASE_DIR, "db", "rxnorm_mapped.json")
    if not os.path.exists(mapping_file):
        return []
    try:
        with open(mapping_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Lọc danh sách hoạt chất duy nhất
            drugs = list(set([item.get("original_name") for item in data if item.get("original_name")]))
            return sorted(drugs)
    except Exception as e:
        print("Lỗi tải danh mục thuốc:", e)
        return []

def load_icd10_partition(member_flag, db_path=None):
    """Tải và phân vùng mã ICD-10 dựa trên ký tự bắt đầu của mã bệnh"""
    if db_path is None:
        db_path = os.path.join(BASE_DIR, "db", "medical_codes.db")

    if not os.path.exists(db_path):
        print(f"Lỗi: Không tìm thấy CSDL '{db_path}'")
        return [], []
        
    # Xác định bộ lọc ký tự bắt đầu dựa trên phân vùng thành viên
    member_upper = str(member_flag).upper()
    if member_upper == "A":
        letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
    elif member_upper in ["B", "LONG"]:
        letters = ["I", "J", "K", "L", "M", "N", "O", "P"]
    elif member_upper == "C":
        letters = ["Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
    else:
        # Mặc định cho các tên tùy chỉnh khác
        letters = ["I", "J", "K", "L", "M", "N", "O", "P"]
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    all_partition_codes = []
    common_partition_codes = []
    
    try:
        # Đọc tất cả mã bệnh trong phân vùng
        placeholders = ",".join(["?"] * len(letters))
        query = f"""
            SELECT code, name_vi, "Thường gập"
            FROM icd10 
            WHERE substr(code, 1, 1) IN ({placeholders})
        """
        cursor.execute(query, letters)
        rows = cursor.fetchall()
        
        for row in rows:
            code_info = {"code": row[0], "name": row[1]}
            all_partition_codes.append(code_info)
            if row[2] == "Có":
                common_partition_codes.append(code_info)
                
    except Exception as e:
        print("Lỗi đọc CSDL ICD-10:", e)
    finally:
        conn.close()
        
    return all_partition_codes, common_partition_codes

def compact_json_format(data):
    """Định dạng JSON thụt lề nhưng giữ các mảng ngắn trên cùng một dòng (như position, assertions, candidates)"""
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    json_str = re.sub(r'\[\s*\n\s*(\d+),\s*\n\s*(\d+)\s*\n\s*\]', r'[\1, \2]', json_str)
    json_str = re.sub(r'\[\s*\n\s*\]', r'[]', json_str)
    json_str = re.sub(r'\[\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1"]', json_str)
    json_str = re.sub(r'\[\s*\n\s*"([^"]+)",\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1", "\2"]', json_str)
    return json_str

def generate_llm_call(api_key, scenario_id, style_id, disease, drugs_list):
    """Sinh prompt theo kịch bản lâm sàng và phong cách được chỉ định, sau đó gọi API Gemini"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={api_key}"
    
    # 1. Định nghĩa phong cách văn bản
    # Pool tiêu đề section ngẫu nhiên để tránh lặp lại đồng nhất
    sec1_titles = ["Tiền sử bệnh", "Tiền sử bệnh nội khoa", "Bệnh nền", "Các bệnh mãn tính"]
    sec2_titles = ["Tiền sử bệnh hiện tại", "Bệnh sử hiện tại", "Bệnh sử", "Diễn biến bệnh"]
    sec3_titles = ["Đánh giá tại bệnh viện", "Khám lúc vào viện", "Đã xử trí thuốc và thủ thuật", "Y lệnh Điều trị", "Điều trị tại bệnh viện"]
    s1 = random.choice(sec1_titles)
    s2 = random.choice(sec2_titles)
    s3 = random.choice(sec3_titles)

    if style_id == 1:
        prompt_style = f"""
PHONG CÁCH YÊU CẦU: Bệnh án lâm sàng bán cấu trúc (Case Report).
Văn bản PHẢI được định dạng theo cấu trúc từng phần (giữ nguyên tiêu đề và dấu xuống dòng). Sử dụng các tiêu đề sau:
1.  {s1}
    - [Tên bệnh hoặc thuốc]
2.  {s2}
    Lý do nhập viện: [Lý do]
    Triệu chứng hiện tại:
    - [Triệu chứng]
    Diễn biến bệnh:
    - ...
3.  {s3}
"""
    elif style_id == 2:
        prompt_style = """
PHONG CÁCH YÊU CẦU: Diễn đàn Q&A y khoa (Hỏi & Trả lời tư vấn).
Văn bản PHẢI được định dạng theo cấu trúc đối thoại sau:
Hỏi : [Câu hỏi của người bệnh, kể về triệu chứng, thuốc đang dùng, tình trạng bệnh...]
Trả lời : Chào bạn, [Lời khuyên của bác sĩ, giải thích thuốc, chẩn đoán, tác dụng phụ...]
"""
    elif style_id == 3:
        prompt_style = """
PHONG CÁCH YÊU CẦU: Bài viết thông tin y khoa giáo dục (Medical Article).
Văn bản PHẢI được định dạng theo cấu trúc chia sẻ kiến thức sau:
[TÊN BỆNH/CHỦ ĐỀ] LÀ GÌ?
1. Định nghĩa khái niệm
[Đoạn văn mô tả khái niệm bệnh hoặc thuốc liên quan...]
2. Dấu hiệu và triệu chứng / Cách điều trị và thuốc sử dụng
- [Gạch đầu dòng dấu hiệu hoặc thuốc sử dụng]
"""
    elif style_id == 4:
        prompt_style = f"""
PHONG CÁCH YÊU CẦU: Văn bản y khoa hỗn hợp (Hybrid/Mixed Document).
Văn bản PHẢI ghép nối ít nhất 2 phong cách khác nhau trong cùng 1 đoạn văn, giống y hệt thực tế hồ sơ bệnh viện bị dán chồng dữ liệu từ nhiều nguồn. Ví dụ:
- Phần đầu là đoạn Hỏi & Đáp giữa bệnh nhân và bác sĩ trên diễn đàn (Câu hỏi từ người dùng: ... / Câu trả lời của bác sĩ: ...)
- Phần sau đột ngột chuyển sang ghi chú bệnh án cấu trúc (1. {s1} ... 2. {s2} ... 3. {s3})
- Hoặc ngược lại: bệnh án cấu trúc rồi ghép thêm đoạn bài viết giáo dục.
- Cho phép chèn 1 đoạn văn mô tả bệnh lý KHÔNG LIÊN QUAN đến bệnh chính, giống như dữ liệu bị dán nhầm.
Đây là phong cách văn bản lộn xộn thực tế, KHÔNG cần mạch lạc logic giữa các phần.
"""
    else:  # style_id == 5
        prompt_style = f"""
PHONG CÁCH YÊU CẦU: Bệnh án lâm sàng dịch từ tiếng Anh (Translated Clinical Note).
Văn bản này giả lập một hồ sơ bệnh án gốc tiếng Anh được dịch sang tiếng Việt (bằng máy hoặc bán thủ công).
Đặc điểm BẮT BUỘC:
- Dùng các placeholder ẩn danh: [Date], [Ngày], [Tên bác sĩ], [Số], [Tên cuộc họp], [Tên bệnh viện].
- Tên thuốc và chỉ số xét nghiệm GIỮ NGUYÊN tiếng Anh gốc: aspirin, ceftriaxone, albuterol, troponin, BNP, lactate, SpO2...
- Cách hành văn mang dấu vết dịch từ tiếng Anh: "phủ nhận buồn nôn" (denies nausea), "chủ quan sốt" (subjective fever), "ban đỏ" (erythema), "dung nạp tốt" (tolerated well).
- Viết tắt y khoa tiếng Anh giữ nguyên: EMS, NRB, IV, IM, PO, BID, TID, PRN, SpO2, RNY, RL (Right Leg), LL (Left Leg).
- Cấu trúc bệnh án theo thứ tự:
1.  {s1}
2.  {s2}
3.  {s3}
"""

    # 2. Định nghĩa kịch bản lâm sàng
    inject_negation = random.random() < 0.30
    inject_historical = random.random() < 0.20
    assertion_hint = ""
    if inject_negation:
        assertion_hint += "\nYÊU CẦU BỔ SUNG VỀ ASSERTIONS: Văn bản PHẢI chứa ít nhất 1 thực thể bị phủ định (isNegated). Ví dụ: 'phủ nhận buồn nôn', 'không sốt', 'không ho', 'chưa ghi nhận co giật'. Thực thể bị phủ định vẫn phải được trích xuất với assertions=['isNegated']."
    if inject_historical and scenario_id != 4:
        assertion_hint += "\nYÊU CẦU BỔ SUNG VỀ ASSERTIONS: Văn bản PHẢI nhắc đến ít nhất 1 bệnh lý hoặc thuốc trong tiền sử bệnh nhân (isHistorical). Ví dụ: 'tiền sử THA 5 năm', 'có tiền sử hen suyễn', 'đang dùng methadone'. Thực thể tiền sử phải được trích xuất với assertions=['isHistorical']."

    if scenario_id == 1:
        prompt_scenario = f"""
KỊCH BẢN LÂM SÀNG: Sơ khám & cận lâm sàng. 
Yêu cầu văn bản sinh ra kể về một bệnh nhân mới đến khám vì một số triệu chứng (triệu chứng cơ năng/thực thể). Bác sĩ chỉ định làm xét nghiệm cận lâm sàng (chỉ số xét nghiệm, chẩn đoán hình ảnh như siêu âm, X-quang, CT sọ...) nhưng ĐANG ĐỢI KẾT QUẢ hoặc có kết quả xét nghiệm nhưng CHƯA kết luận chẩn đoán xác định bệnh và CHƯA kê đơn thuốc.

Kết quả xét nghiệm phải ĐA DẠNG FORMAT, ngẫu nhiên chọn trong các dạng sau:
- Dạng 1: Chỉ tên + số, không đơn vị: "bạch cầu 26.7", "kali 3.2", "troponin 0.01"
- Dạng 2: Tên + số + đơn vị: "CRP: 227.0 mg/L", "Creatinin : 46 µmol/L", "Kali +: 3.6 mmol/L"
- Dạng 3: Dấu hiệu sinh tồn: "Huyết áp: 130/70 mmHg", "Mạch: 93 l/p", "SPO2: 99 %", "Nhiệt độ: 37°C"
- Dạng 4: Nhiều chỉ số liệt kê nối liền trên 1 dòng (không xuống dòng)

Trong phần trích xuất thực thể 'entities':
- CHỈ trích xuất các loại: 'TRIỆU_CHỨNG', 'TÊN_XÉT_NGHIỆM', 'KẾT_QUẢ_XÉT_NGHIỆM'.
- TUYỆT ĐỐI không trích xuất loại 'CHẨN_ĐOÁN' hay 'THUỐC'.
{assertion_hint}
"""
    elif scenario_id == 2:
        prompt_scenario = f"""
KỊCH BẢN LÂM SÀNG: Có chẩn đoán bệnh nhưng không điều trị bằng thuốc.
Yêu cầu văn bản sinh ra kết luận bệnh nhân mắc bệnh sau: '{disease["name"]}'. 
Tuy nhiên, bệnh nhân không được kê đơn thuốc điều trị trong ca này. Lý do có thể là: bệnh nhân có chỉ định phẫu thuật ngoại khoa khẩn/chương trình (nhập viện mổ), hoặc chỉ cần theo dõi lối sống/chế độ ăn uống, hoặc đây là bệnh di truyền bẩm sinh chỉ phát hiện chứ chưa có thuốc điều trị đặc trị.
Trong phần trích xuất thực thể 'entities':
- Bắt buộc trích xuất bệnh '{disease["name"]}' với nhãn 'CHẨN_ĐOÁN'.
- TUYỆT ĐỐI không trích xuất thực thể loại 'THUỐC'.
{assertion_hint}
"""
    elif scenario_id == 3:
        prompt_scenario = f"""
KỊCH BẢN LÂM SÀNG: Chẩn đoán bệnh kèm đơn thuốc điều trị nội khoa hợp lý.
Yêu cầu văn bản sinh ra kết luận bệnh nhân mắc bệnh sau: '{disease["name"]}'.
Đồng thời, bác sĩ kê đơn thuốc điều trị phù hợp cho bệnh này. Bạn hãy sử dụng tri thức y khoa để LỰA CHỌN ra 1-2 loại thuốc phù hợp nhất điều trị bệnh này từ danh sách 348 hoạt chất được hỗ trợ dưới đây:
{", ".join(drugs_list)}

Khi ghi thuốc trong văn bản, ngẫu nhiên chọn 1 trong các format sau:
- Tên thuốc + liều: "aspirin 325mg"
- Tên thuốc + liều + đường dùng vắn tắt: "methylprednisolone 125mg iv", "Ceftriaxone 1 gram dùng 1 liều"
- Tên thuốc + liều + tần suất + đường dùng chi tiết: "Ceftriaxone 1g: 2 lọ/ngày, truyền tĩnh mạch"

Trong phần trích xuất thực thể 'entities':
- Bắt buộc trích xuất bệnh '{disease["name"]}' với nhãn 'CHẨN_ĐOÁN'.
- Trích xuất 1-2 loại thuốc bạn đã chọn để điều trị bệnh đó với nhãn 'THUỐC'.
{assertion_hint}
"""
    else:
        hist_drug = random.choice(drugs_list)
        prompt_scenario = f"""
KỊCH BẢN LÂM SÀNG: Ghi nhận tiền sử dùng thuốc dài hạn.
Yêu cầu văn bản sinh ra ghi nhận bệnh nhân có tiền sử đang sử dụng dài hạn hoạt chất thuốc sau: '{hist_drug}'. Lưu ý ở phần kết luận bệnh án hiện tại, bác sĩ khám vì lý do khác và không kết luận chẩn đoán bệnh liên quan đến thuốc này.
Trong phần trích xuất thực thể 'entities':
- Bắt buộc trích xuất thuốc '{hist_drug}' với nhãn 'THUỐC' và thuộc tính assertions chứa nhãn 'isHistorical'.
{assertion_hint}
"""

    # Quyết định độ dài văn bản
    rand_len = random.random()
    if rand_len < 0.20:
        length_hint = "ĐỘ DÀI: NGẮN (3-5 dòng, khoảng 50-100 từ). Ghi chú vắn tắt, cô đọng."
    elif rand_len < 0.70:
        length_hint = "ĐỘ DÀI: TRUNG BÌNH (10-25 dòng, khoảng 200-400 từ)."
    else:
        length_hint = "ĐỘ DÀI: DÀI (25-40 dòng, khoảng 400-800 từ). Chi tiết, đầy đủ."

    # Quyết định có che thuốc bằng dấu sao **** không (20% mẫu)
    mask_drug_hint = ""
    if random.random() < 0.20:
        mask_drug_hint = """
5. MÔ PHỎNG ẨN DANH HÓA THUỐC: Ngẫu nhiên che 1-2 tên thuốc xuất hiện trong văn bản bằng chuỗi dấu sao (************) với số lượng sao tương đương độ dài từ gốc. Ví dụ: "thuốc ************ sử dụng mỗi tối", "*************** có thể hệ sau không gây buồn ngủ". Các thuốc bị che KHÔNG được trích xuất trong phần entities."""

    # Quyết định có bơm lỗi đánh máy không (20% mẫu)
    typo_hint = ""
    if random.random() < 0.20:
        typo_hint = """
6. BƠM NHIỄU LỖI GÕ: Cố tình tạo ra 1-2 lỗi gõ nhỏ trong văn bản: thiếu khoảng trắng giữa 2 từ (ví dụ: "bạch cầuvài" thay vì "bạch cầu vài"), lỗi dấu tiếng Việt (ví dụ: "hồngi" thay vì "hồng"), hoặc câu bị cắt cụt thiếu dấu đóng ngoặc (ví dụ: "đỡ đau  (có thể ngủ" thay vì "đỡ đau (có thể ngủ được)"). Các thực thể trích xuất vẫn phải khớp chính xác với cụm từ chứa lỗi trong text."""

    prompt = f"""
Hãy sinh ra một văn bản y khoa tiếng Việt theo phong cách y khoa được chỉ định dưới đây:

{length_hint}

{prompt_style}

{prompt_scenario}

--- YÊU CẦU ĐẦU RA ---
Đầu ra của bạn PHẢI là một đối tượng JSON có cấu trúc chính xác như sau:
{{
  "text": "Đoạn văn bản y khoa thô sinh ra (giữ nguyên toàn bộ các dấu xuống dòng \\n, dấu đầu dòng • hoặc -, căn lề khoảng trắng thụt lề giống hệt định dạng thực tế của phong cách đã chọn)",
  "entities": [
    {{
      "text": "cụm từ y khoa trích xuất chính xác 100% từng ký tự xuất hiện trong text trên",
      "type": "TRIỆU_CHỨNG" hoặc "CHẨN_ĐOÁN" hoặc "THUỐC" hoặc "TÊN_XÉT_NGHIỆM" hoặc "KẾT_QUẢ_XÉT_NGHIỆM",
      "assertions": ["isNegated" hoặc "isFamily" hoặc "isHistorical"] (hoặc để mảng rỗng [] nếu không có ngữ cảnh đặc biệt này)
    }}
  ]
}}

LƯU Ý LỚN:
1. Văn phong tiếng Việt tự nhiên, có thể chứa một số thuật ngữ tiếng Anh viết tắt (ví dụ: THA, ĐTĐ, COPD, WBC, ct sọ, ran ẩm, x-quang, paracetamol, amlodipine...) y hệt thực tế lâm sàng Việt Nam.
2. Trường 'text' trong 'entities' phải khớp hoàn hảo (phân biệt cả hoa thường) với cụm từ con trong trường 'text' gốc của bệnh án để tránh lỗi không tìm thấy.
3. Chỉ trích xuất tối đa 5-8 thực thể tiêu biểu nhất xuất hiện trong văn bản.
4. Nếu văn bản có nhắc đến bệnh lý hoặc thuốc của NGƯỜI THÂN (bố, mẹ, anh chị em bệnh nhân), thực thể đó phải gắn assertions=['isFamily'].
{mask_drug_hint}
{typo_hint}
"""

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    for attempt in range(5):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 429:
                wait = 25 * (attempt + 1) + random.randint(5, 15)
                print(f"  ⚠️ Dính nhịp Rate Limit (429). Tự động chờ {wait}s để nhả quota rồi thử lại (lần {attempt+1}/5)...")
                time.sleep(wait)
                continue
            if response.status_code != 200:
                print(f"  ❌ Lỗi gọi API Gemini: Mã lỗi {response.status_code} - {response.text[:200]}")
                return None
                
            res_data = response.json()
            content_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(content_text)
        except Exception as e:
            print(f"  ❌ Lỗi gọi LLM hoặc parse JSON (lần {attempt+1}/5):", e)
            time.sleep(random.uniform(6.0, 9.0))
    return None

def process_and_align(generated_data):
    """Tính toán position và tra cứu mã candidates offline từ CSDL SQLite"""
    clinical_text = generated_data.get("text", "")
    entities = generated_data.get("entities", [])
    aligned_entities = []
    
    for item in entities:
        text = item.get("text", "")
        etype = item.get("type", "")
        assertions = item.get("assertions", [])
        
        # Tính position [start, end]
        start_idx = clinical_text.find(text)
        if start_idx == -1:
            continue
        end_idx = start_idx + len(text)
        position = [start_idx, end_idx]
        
        # Tra cứu mã offline
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
    parser = argparse.ArgumentParser(description="Script sinh dữ liệu huấn luyện y khoa phân tầng (Phiên bản v2 nâng cấp)")
    parser.add_argument("--member", type=str, required=True, help="Mã thành viên (Ví dụ: Long, A, B, C)")
    parser.add_argument("--num_samples", type=int, default=2000, help="Số lượng mẫu cần sinh (mặc định 2000, bị bỏ qua nếu dùng --start_idx/--end_idx)")
    parser.add_argument("--start_idx", type=int, default=None, help="Chỉ số file bắt đầu (dùng cho chạy song song, ví dụ: 1)")
    parser.add_argument("--end_idx", type=int, default=None, help="Chỉ số file kết thúc (dùng cho chạy song song, ví dụ: 200)")
    args = parser.parse_args()
    
    api_key = load_api_key()
    if not api_key:
        print("Vui lòng cấu hình GEMINI_API_KEY trong tệp .env.")
        sys.exit(1)
        
    print(f"--- KHỞI ĐỘNG TIẾN TRÌNH SINH DỮ LIỆU V2 ---")
    print(f" * Thành viên / Tên thư mục: sample_{args.member}")
    
    # Tải danh mục thuốc và phân vùng bệnh
    drugs_list = load_drugs_list()
    all_codes, common_codes = load_icd10_partition(args.member)
    
    if not all_codes or not drugs_list:
        print("Lỗi: Không tải được danh mục bệnh hoặc danh mục thuốc. Hãy kiểm tra các file CSDL.")
        sys.exit(1)
        
    print(f" * Phân vùng nạp thành công cho '{args.member}':")
    print(f"   - Tổng số mã bệnh: {len(all_codes)}")
    print(f"   - Mã bệnh phổ biến: {len(common_codes)}")
    print(f"   - Số lượng hoạt chất hỗ trợ gợi ý: {len(drugs_list)}")
    
    # Định nghĩa cấu trúc thư mục lưu trữ chia theo thành viên (đường dẫn tuyệt đối)
    input_dir = os.path.join(BASE_DIR, f"sample_{args.member}", "input")
    output_dir = os.path.join(BASE_DIR, f"sample_{args.member}", "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    # Xác định dải chỉ số cần sinh dựa trên chế độ chạy
    if args.start_idx is not None and args.end_idx is not None:
        range_start = args.start_idx
        range_end = args.end_idx
        print(f" * Chế độ: SONG SONG (dải chỉ số [{range_start}, {range_end}])")
    else:
        range_start = 1
        range_end = args.num_samples
        print(f" * Chế độ: TUẦN TỰ (sinh {args.num_samples} mẫu)")
    
    # Quét file đã có trong dải chỉ số để checkpoint
    indices_to_generate = []
    already_done = 0
    for idx in range(range_start, range_end + 1):
        txt_path = os.path.join(input_dir, f"{idx}.txt")
        if os.path.exists(txt_path):
            already_done += 1
        else:
            indices_to_generate.append(idx)
    
    total_in_range = range_end - range_start + 1
    remaining = len(indices_to_generate)
    
    if already_done > 0:
        print(f"\n * [CHECKPOINT] Đã phát hiện {already_done}/{total_in_range} mẫu đã sinh trong dải [{range_start}, {range_end}].")
        print(f" * Tiếp tục sinh {remaining} mẫu còn thiếu.")
    
    if remaining == 0:
        print(f"\n=== Đã đủ {total_in_range} mẫu trong dải [{range_start}, {range_end}]. Không cần sinh thêm. ===")
        sys.exit(0)
    
    success_count = 0
    fail_count = 0
    consecutive_fails = 0
    MAX_CONSECUTIVE_FAILS = 15
    gen_pointer = 0
    
    # Chạy vòng lặp sinh dữ liệu
    while gen_pointer < len(indices_to_generate):
        current_file_idx = indices_to_generate[gen_pointer]
        total_done = already_done + success_count
        print(f"[{total_done + 1}/{total_in_range}] Đang sinh mẫu #{current_file_idx}...")
        
        if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
            print(f"\n⚠️  ĐÃ THẤT BẠI LIÊN TỤC {MAX_CONSECUTIVE_FAILS} LẦN. Có thể hết quota API.")
            print(f"    Đã lưu checkpoint: {already_done + success_count} mẫu.")
            print(f"    Chạy lại lệnh tương tự để tiếp tục từ checkpoint.")
            break
        
        # 1. Quyết định kịch bản lâm sàng
        rand_val = random.random()
        if rand_val < 0.20:
            scenario_id = 1
        elif rand_val < 0.45:
            scenario_id = 2
        elif rand_val < 0.85:
            scenario_id = 3
        else:
            scenario_id = 4
            
        # 1.5. Quyết định phong cách văn bản (Phong cách 5 chiếm 30%)
        rand_style = random.random()
        if rand_style < 0.25:
            style_id = 1
        elif rand_style < 0.40:
            style_id = 2
        elif rand_style < 0.55:
            style_id = 3
        elif rand_style < 0.70:
            style_id = 4
        else:
            style_id = 5
            
        # 2. Quyết định chọn bệnh
        target_disease = None
        if scenario_id in [2, 3]:
            if common_codes and random.random() < 0.30:
                target_disease = random.choice(common_codes)
            else:
                target_disease = random.choice(all_codes)
                
        # 3. Gọi LLM sinh mẫu
        raw_sample = generate_llm_call(api_key, scenario_id, style_id, target_disease, drugs_list)
        if not raw_sample:
            print(f" -> Thất bại ở bước gọi LLM hoặc parse JSON. Đang bỏ qua...")
            fail_count += 1
            consecutive_fails += 1
            time.sleep(10)
            continue
            
        # 4. Xử lý căn chỉnh vị trí và candidates offline
        final_entities = process_and_align(raw_sample)
        text_content = raw_sample.get("text", "").strip()
        
        if not text_content:
            print(f" -> Tệp văn bản sinh ra bị rỗng. Đang bỏ qua...")
            fail_count += 1
            consecutive_fails += 1
            continue
            
        # 5. Ghi tệp kết quả
        txt_path = os.path.join(input_dir, f"{current_file_idx}.txt")
        json_path = os.path.join(output_dir, f"{current_file_idx}.json")
        
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text_content)
            
        formatted_json = compact_json_format(final_entities)
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(formatted_json)
            
        success_count += 1
        gen_pointer += 1
        consecutive_fails = 0
        
        if success_count % 50 == 0:
            total_done = already_done + success_count
            print(f"\n📊 [CHECKPOINT] {total_done}/{total_in_range} mẫu hoàn tất.\n")
        
        time.sleep(5)
        
    total_done = already_done + success_count
    print(f"\n=== HOÀN TẤT TIẾN TRÌNH SINH DỮ LIỆU V2 ===")
    print(f" - Dải chỉ số: [{range_start}, {range_end}] ({total_in_range} mẫu)")
    print(f" - Tổng mẫu đã có (bao gồm checkpoint trước): {total_done}/{total_in_range}")
    print(f" - Mẫu sinh mới trong phiên này: {success_count}")
    print(f" - Số lần thất bại/bỏ qua: {fail_count}")
    print(f" - Dữ liệu thô lưu tại: {input_dir}")
    print(f" - Dữ liệu thực thể lưu tại: {output_dir}")

if __name__ == "__main__":
    main()

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

def load_api_key():
    """Đọc GEMINI_API_KEY từ biến môi trường OS trước, sau đó là file .env"""
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        return env_key
        
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

def query_local_db(entity_text, entity_type, db_path=os.path.join("db", "medical_codes.db")):
    """Truy vấn mã ICD-10 hoặc RxNorm từ SQLite"""
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
    mapping_file = os.path.join("db", "rxnorm_mapped.json")
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

def load_icd10_partition(member_flag, db_path=os.path.join("db", "medical_codes.db")):
    """Tải và phân vùng mã ICD-10 dựa trên ký tự bắt đầu của mã bệnh"""
    if not os.path.exists(db_path):
        print(f"Lỗi: Không tìm thấy CSDL '{db_path}'")
        return [], []
        
    # Xác định bộ lọc ký tự bắt đầu dựa trên phân vùng thành viên
    if member_flag == "A":
        letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
    elif member_flag == "B":
        letters = ["I", "J", "K", "L", "M", "N", "O", "P"]
    elif member_flag == "C":
        letters = ["Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
    else:
        letters = []
        
    if not letters:
        print("Lỗi: Phân vùng thành viên không hợp lệ (Chỉ chấp nhận A, B, hoặc C).")
        return [], []
        
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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    # 1. Định nghĩa phong cách văn bản
    sec1_titles = ["Tiền sử bệnh", "Tiền sử bệnh nội khoa", "Bệnh nền", "Các bệnh mãn tính"]
    sec2_titles = ["Tiền sử bệnh hiện tại", "Bệnh sử hiện tại", "Bệnh sử", "Diễn biến bệnh"]
    sec3_titles = ["Đánh giá tại bệnh viện", "Khám lúc vào viện", "Đã xử trí thuốc và thủ thuật", "Y lệnh Điều trị", "Điều trị tại bệnh viện"]
    s1, s2, s3 = random.choice(sec1_titles), random.choice(sec2_titles), random.choice(sec3_titles)

    if style_id == 1:
        prompt_style = f"PHONG CÁCH YÊU CẦU: Bệnh án lâm sàng bán cấu trúc (Case Report) chi tiết.\n1. {s1}\n2. {s2}\n3. {s3}"
    elif style_id == 2:
        prompt_style = "PHONG CÁCH YÊU CẦU: Diễn đàn Q&A y khoa (Hỏi & Trả lời tư vấn chuyên sâu).\nHỏi : [Nội dung câu hỏi dài của người bệnh mô tả đầy đủ triệu chứng, tiền sử]\nTrả lời : Chào bạn, [Nội dung tư vấn chi tiết từ bác sĩ giải thích cặn kẽ]"
    elif style_id == 3:
        prompt_style = "PHONG CÁCH YÊU CẦU: Bài viết thông tin y khoa giáo dục sức khỏe (Medical Article).\n[TÊN BỆNH] LÀ GÌ?\n1. Khái niệm và nguyên nhân gây bệnh\n2. Triệu chứng lâm sàng và các phương án điều trị tây y"
    elif style_id == 4:
        prompt_style = f"PHONG CÁCH YÊU CẦU: Văn bản y khoa hỗn hợp (Hybrid/Mixed Document).\nGhép nối đoạn Hỏi & Đáp với ghi chú bệnh án cấu trúc (1. {s1} ... 2. {s2} ... 3. {s3}). Có thể chèn 1 đoạn dán nhầm không liên quan để tạo độ nhiễu thực tế."
    else:
        prompt_style = f"PHONG CÁCH YÊU CẦU: Bệnh án lâm sàng dịch từ tiếng Anh (Translated Clinical Note).\nDùng placeholder [Date], [Ngày], [Tên bác sĩ]. Giữ nguyên tên thuốc tiếng Anh (aspirin, ceftriaxone, troponin...). Hành văn dịch gượng ('phủ nhận buồn nôn', 'chủ quan sốt').\n1. {s1}\n2. {s2}\n3. {s3}"

    # 2. Định nghĩa kịch bản lâm sàng & thuộc tính bổ sung
    inject_negation = random.random() < 0.30
    inject_historical = random.random() < 0.20
    assertion_hint = ""
    if inject_negation:
        assertion_hint += "\nVăn bản PHẢI chứa ít nhất 1 thực thể bị phủ định (isNegated), ví dụ: 'phủ nhận buồn nôn', 'không sốt', 'không đau đầu'."
    if inject_historical and scenario_id != 4:
        assertion_hint += "\nVăn bản PHẢI chứa ít nhất 1 thực thể tiền sử (isHistorical), ví dụ: 'tiền sử THA 5 năm', 'đã mổ ruột thừa cách đây 2 năm'."

    if scenario_id == 1:
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Sơ khám & cận lâm sàng. Bác sĩ chỉ định xét nghiệm cận lâm sàng. CHƯA có chẩn đoán bệnh xác định, CHƯA kê đơn thuốc. Định dạng xét nghiệm đa dạng.\nEntities: CHỈ trích xuất 'TRIỆU_CHỨNG', 'TÊN_XÉT_NGHIỆM', 'KẾT_QUẢ_XÉT_NGHIỆM'. TUYỆT ĐỐI không trích xuất CHẨN_ĐOÁN hay THUỐC.\n{assertion_hint}"
    elif scenario_id == 2:
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Có chẩn đoán bệnh '{disease['name']}' nhưng KHÔNG kê đơn thuốc (chỉ định phẫu thuật/theo dõi lối sống).\nEntities: Bắt buộc trích xuất '{disease['name']}' nhãn CHẨN_ĐOÁN. TUYỆT ĐỐI không trích xuất THUỐC.\n{assertion_hint}"
    elif scenario_id == 3:
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Chẩn đoán bệnh '{disease['name']}' kèm đơn thuốc điều trị nội khoa hợp lý chọn từ: {', '.join(drugs_list)}.\nEntities: Trích xuất '{disease['name']}' nhãn CHẨN_ĐOÁN và 1-2 thuốc chọn nhãn THUỐC.\n{assertion_hint}"
    else:
        hist_drug = random.choice(drugs_list)
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Ghi nhận tiền sử dùng thuốc dài hạn '{hist_drug}'.\nEntities: Trích xuất '{hist_drug}' nhãn THUỐC với assertions=['isHistorical'].\n{assertion_hint}"

    # Tăng độ dài để giống turn2 thực tế (trung bình 436 từ)
    rand_len = random.random()
    length_hint = "ĐỘ DÀI: TRUNG BÌNH (300-500 từ)" if rand_len < 0.40 else "ĐỘ DÀI: DÀI (500-800 từ)"

    mask_drug_hint = "\nMÔ PHỎNG ẨN DANH HÓA THUỐC: Ngẫu nhiên che 1-2 tên thuốc bằng dấu sao (************). Thuốc bị che KHÔNG trích xuất." if random.random() < 0.20 else ""
    typo_hint = "\nBƠM NHIỄU LỖI GÕ: Tạo 1-2 lỗi gõ (dính chữ, lỗi dấu). Cụm trích xuất phải khớp chính xác text chứa lỗi." if random.random() < 0.20 else ""

    prompt = f"""
Hãy sinh ra một văn bản y khoa tiếng Việt theo phong cách y khoa được chỉ định dưới đây:

{length_hint}

{prompt_style}

{prompt_scenario}

--- YÊU CẦU ĐẦU RA BẮT BUỘC ---
Đầu ra PHẢI là một đối tượng JSON chuẩn (chỉ trả về duy nhất chuỗi JSON, không kèm bất kỳ lời giải thích markdown nào khác):
{{
  "text": "Nội dung đoạn văn bản y khoa thô sinh ra (giữ nguyên toàn bộ các dấu xuống dòng \\n)",
  "entities": [
    {{
      "text": "cụm từ y khoa trích xuất chính xác 100% từng ký tự xuất hiện trong text",
      "type": "TRIỆU_CHỨNG" hoặc "CHẨN_ĐOÁN" hoặc "THUỐC" hoặc "TÊN_XÉT_NGHIỆM" hoặc "KẾT_QUẢ_XÉT_NGHIỆM",
      "assertions": ["isNegated" hoặc "isFamily" hoặc "isHistorical"] (hoặc mảng rỗng [])
    }}
  ]
}}

🛑 LƯU Ý QUAN TRỌNG VỀ NHÃN (ENTITIES):
1. Trường 'type' của thực thể CHỈ ĐƯỢC PHÉP chứa 1 trong 5 giá trị: 'CHẨN_ĐOÁN', 'THUỐC', 'TRIỆU_CHỨNG', 'TÊN_XÉT_NGHIỆM', 'KẾT_QUẢ_XÉT_NGHIỆM'.
2. TUYỆT ĐỐI không tự tạo nhãn mới (như 'BỆNH', 'TÊN_BỆNH', 'isNegated', 'isHistorical').
3. Các thuộc tính như 'isNegated', 'isHistorical', 'isFamily' PHẢI đặt trong danh sách 'assertions', TUYỆT ĐỐI không đặt vào trường 'type'.
4. Trích xuất tối đa 5-8 thực thể tiêu biểu nhất xuất hiện trong văn bản.
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
    
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            if response.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"Lỗi 429 Rate Limit. Đợi {wait}s rồi thử lại (lần {attempt+1}/3)...")
                time.sleep(wait)
                continue
            if response.status_code != 200:
                print(f"Lỗi gọi API Gemini: Mã lỗi {response.status_code}")
                return None
                
            res_data = response.json()
            content_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
            
            # Parse JSON siêu bền bỉ bằng regex bóc tách khối {...}
            match = re.search(r'\{.*\}', content_text, re.DOTALL)
            if match:
                cleaned_text = match.group(0)
            else:
                cleaned_text = content_text.strip()
                
            return json.loads(cleaned_text)
        except Exception as e:
            print(f"Lỗi gọi LLM hoặc parse JSON (lần {attempt+1}/3):", e)
            if attempt < 2:
                time.sleep(10)
    return None

def process_and_align(generated_data):
    """Tính toán position, chuẩn hóa nhãn thực thể và tra cứu mã candidates offline"""
    if not generated_data or not isinstance(generated_data, dict):
        return []
    clinical_text = generated_data.get("text", "")
    if not isinstance(clinical_text, str):
        clinical_text = ""
    entities = generated_data.get("entities", [])
    if not isinstance(entities, list):
        entities = []
    aligned_entities = []
    
    for item in entities:
        if not item or not isinstance(item, dict):
            continue
        text = item.get("text", "")
        etype = str(item.get("type", "")).strip()
        assertions = item.get("assertions", [])
        if not isinstance(assertions, list):
            assertions = []
            
        if not text or not isinstance(text, str):
            continue
            
        # Tìm vị trí trong văn bản thô
        start_idx = clinical_text.find(text)
        if start_idx == -1:
            continue
        end_idx = start_idx + len(text)
        position = [start_idx, end_idx]
        
        # 1. Sửa lỗi nhãn bị gán nhầm thuộc tính assertion (isNegated, isHistorical, isFamily) làm nhãn type
        if etype in ["isNegated", "isHistorical", "isFamily"]:
            if etype not in assertions:
                assertions.append(etype)
            etype = "TRIỆU_CHỨNG"  # default fallback
            
        # 2. Chuẩn hóa nhãn tự do về 5 nhóm hợp lệ theo đề bài
        etype_upper = etype.upper().replace(" ", "_")
        
        if etype_upper in ["CHẨN_ĐOÁN", "CHAN_DOAN", "BỆNH", "BENH", "BỆNH_LÝ", "BENH_LY", "CHẨN_ĐOÁN_LÂM_SÀNG", "TÊN_BỆNH", "TEN_BENH"]:
            etype = "CHẨN_ĐOÁN"
        elif etype_upper in ["THUỐC", "THUOC", "TÊN_THUỐC", "TEN_THUOC", "DƯỢC_PHẨM"]:
            etype = "THUỐC"
        elif etype_upper in ["TRIỆU_CHỨNG", "TRIEU_CHUNG", "TRIỆU CHỨNG", "TRÍỆU_CHỨNG", "LÂM_SÀNG"]:
            etype = "TRIỆU_CHỨNG"
        elif etype_upper in ["TÊN_XÉT_NGHIỆM", "TEN_XET_NGHIEM", "XÉT_NGHIỆM", "XET_NGHIEM"]:
            etype = "TÊN_XÉT_NGHIỆM"
        elif etype_upper in ["KẾT_QUẢ_XÉT_NGHIỆM", "KET_QUA_XET_NGHIEM", "KẾT_QUẢ", "KET_QUA"]:
            etype = "KẾT_QUẢ_XÉT_NGHIỆM"
        else:
            # Đoán nhãn sơ bộ
            if "bệnh" in text.lower() or "viêm" in text.lower() or "hội chứng" in text.lower():
                etype = "CHẨN_ĐOÁN"
            elif "sốt" in text.lower() or "đau" in text.lower() or "mệt" in text.lower() or "ho" in text.lower():
                etype = "TRIỆU_CHỨNG"
            else:
                etype = "TRIỆU_CHỨNG"  # Fallback
                
        # Loại bỏ các nhãn trùng lặp trong assertions
        clean_assertions = []
        for ass in assertions:
            ass_str = str(ass).strip()
            if ass_str in ["isNegated", "isHistorical", "isFamily"] and ass_str not in clean_assertions:
                clean_assertions.append(ass_str)
                
        # Tra cứu mã candidates
        candidates = []
        if etype in ["CHẨN_ĐOÁN", "THUỐC"]:
            candidates = query_local_db(text, etype)
            
        aligned_entities.append({
            "text": text,
            "position": position,
            "type": etype,
            "assertions": clean_assertions,
            "candidates": candidates
        })
        
    return aligned_entities

def main():
    parser = argparse.ArgumentParser(description="Script sinh dữ liệu huấn luyện y khoa phân tầng")
    parser.add_argument("--member", type=str, required=True, choices=["A", "B", "C"], help="Mã thành viên (A, B, hoặc C)")
    parser.add_argument("--num_samples", type=int, default=2000, help="Số lượng mẫu cần sinh (mặc định 2000)")
    args = parser.parse_args()
    
    api_key = load_api_key()
    if not api_key:
        print("Vui lòng cấu hình GEMINI_API_KEY trong tệp .env.")
        sys.exit(1)
        
    print(f"--- KHỞI ĐỘNG TIẾN TRÌNH SINH DỮ LIỆU ---")
    print(f" * Thành viên: {args.member}")
    print(f" * Số lượng cần sinh: {args.num_samples}")
    
    # Tải danh mục thuốc và phân vùng bệnh
    drugs_list = load_drugs_list()
    all_codes, common_codes = load_icd10_partition(args.member)
    
    if not all_codes or not drugs_list:
        print("Lỗi: Không tải được danh mục bệnh hoặc danh mục thuốc. Hãy kiểm tra các file CSDL.")
        sys.exit(1)
        
    print(f" * Phân vùng thành viên {args.member} nạp thành công:")
    print(f"   - Tổng số mã bệnh: {len(all_codes)}")
    print(f"   - Mã bệnh phổ biến: {len(common_codes)}")
    print(f"   - Số lượng hoạt chất hỗ trợ gợi ý: {len(drugs_list)}")
    
    # Định nghĩa cấu trúc thư mục lưu trữ chia theo thành viên (tránh xung đột ghi đè khi chạy song song)
    input_dir = os.path.join(f"sample_{args.member}", "input")
    output_dir = os.path.join(f"sample_{args.member}", "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    # Đếm số lượng tệp hiện có để bắt đầu đánh số (quét cả subfolder part_1, part_2...)
    existing_indices = []
    for root, _, files in os.walk(input_dir):
        for f in files:
            if f.endswith(".txt"):
                name = f[:-4]
                if name.isdigit():
                    existing_indices.append(int(name))
    start_idx = max(existing_indices) + 1 if existing_indices else 1
    already_done = len(existing_indices)
    remaining = max(0, args.num_samples - already_done)
    
    if already_done > 0:
        print(f"\n * [CHECKPOINT] Đã phát hiện {already_done} mẫu đã sinh (file 1..{start_idx - 1}).")
        print(f" * Tiếp tục sinh {remaining} mẫu còn lại (bắt đầu từ file #{start_idx}).")
    
    if remaining == 0:
        print(f"\n=== Đã đủ {args.num_samples} mẫu. Không cần sinh thêm. ===")
        sys.exit(0)
    
    success_count = 0
    fail_count = 0
    consecutive_fails = 0
    MAX_CONSECUTIVE_FAILS = 15  # Dừng sớm nếu liên tục thất bại (hết quota)
    
    # Chạy vòng lặp sinh dữ liệu
    for i in range(remaining):
        current_file_idx = start_idx + success_count
        total_done = already_done + success_count
        print(f"[{total_done + 1}/{args.num_samples}] Đang sinh mẫu #{current_file_idx}...")
        
        # Kiểm tra liên tục thất bại → dừng sớm
        if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
            print(f"\n⚠️  ĐÃ THẤT BẠI LIÊN TỤC {MAX_CONSECUTIVE_FAILS} LẦN. Có thể hết quota API.")
            print(f"    Đã lưu checkpoint: {already_done + success_count} mẫu.")
            print(f"    Chạy lại lệnh tương tự để tiếp tục từ checkpoint.")
            break
        
        # 1. Quyết định kịch bản lâm sàng (Phân bổ tỷ lệ)
        # Kịch bản 1: 20%, Kịch bản 2: 25%, Kịch bản 3: 40%, Kịch bản 4: 15%
        rand_val = random.random()
        if rand_val < 0.20:
            scenario_id = 1
        elif rand_val < 0.45:
            scenario_id = 2
        elif rand_val < 0.85:
            scenario_id = 3
        else:
            scenario_id = 4
            
        # 1.5. Quyết định phong cách văn bản (Phân bổ tỷ lệ)
        # Phong cách 1: 40%, Phong cách 2: 25%, Phong cách 3: 20%, Phong cách 4: 15% (Hybrid)
        rand_style = random.random()
        if rand_style < 0.40:
            style_id = 1
        elif rand_style < 0.65:
            style_id = 2
        elif rand_style < 0.85:
            style_id = 3
        else:
            style_id = 4
            
        # 2. Quyết định chọn bệnh (70% ngẫu nhiên/hiếm, 30% phổ biến)
        target_disease = None
        if scenario_id in [2, 3]:
            # Chọn bệnh
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
            
        # 5. Ghi tệp kết quả theo subfolder part_N (mỗi folder 500 file)
        part_num = (current_file_idx - 1) // 500 + 1
        part_input_dir = os.path.join(input_dir, f"part_{part_num}")
        part_output_dir = os.path.join(output_dir, f"part_{part_num}")
        os.makedirs(part_input_dir, exist_ok=True)
        os.makedirs(part_output_dir, exist_ok=True)
        
        txt_path = os.path.join(part_input_dir, f"{current_file_idx}.txt")
        json_path = os.path.join(part_output_dir, f"{current_file_idx}.json")
        
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text_content)
            
        formatted_json = compact_json_format(final_entities)
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(formatted_json)
            
        success_count += 1
        consecutive_fails = 0  # Reset khi thành công
        
        # In checkpoint mỗi 50 mẫu
        if success_count % 50 == 0:
            total_done = already_done + success_count
            print(f"\n📊 [CHECKPOINT] {total_done}/{args.num_samples} mẫu hoàn tất. Có thể dừng và chạy lại bất cứ lúc nào.\n")
        
        # Tránh vượt quá giới hạn API Gemini (Free Tier: 15 RPM -> Sleep 5 giây giữa các yêu cầu)
        time.sleep(5)
        
    total_done = already_done + success_count
    print(f"\n=== HOÀN TẤT TIẾN TRÌNH SINH DỮ LIỆU ===")
    print(f" - Tổng mẫu đã có (bao gồm checkpoint trước): {total_done}/{args.num_samples}")
    print(f" - Mẫu sinh mới trong phiên này: {success_count}")
    print(f" - Số lần thất bại/bỏ qua: {fail_count}")
    print(f" - Dữ liệu thô lưu tại: {input_dir}")
    print(f" - Dữ liệu thực thể lưu tại: {output_dir}")
    if total_done < args.num_samples:
        print(f"\n💡 Chạy lại lệnh tương tự để sinh tiếp {args.num_samples - total_done} mẫu còn lại.")

if __name__ == "__main__":
    main()


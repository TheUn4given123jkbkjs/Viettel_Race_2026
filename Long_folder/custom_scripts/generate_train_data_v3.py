import os
import sys
import sqlite3
import requests
import json
import re
import time
import random
import argparse
import threading

# Đảm bảo in unicode không lỗi
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(BASE_DIR) == "Long_folder":
    BASE_DIR = os.path.dirname(BASE_DIR)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, "scratch"))

from key_manager import key_manager

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

def load_drugs_list():
    """Tải danh sách 348 hoạt chất từ db/rxnorm_mapped.json"""
    mapping_file = os.path.join(BASE_DIR, "db", "rxnorm_mapped.json")
    if not os.path.exists(mapping_file):
        return []
    try:
        with open(mapping_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            drugs = list(set([item.get("original_name") for item in data if item.get("original_name")]))
            return sorted(drugs)
    except Exception as e:
        print("Lỗi tải danh mục thuốc:", e)
        return []

def load_icd10_partition(member_flag, db_path=None):
    """Tải phân vùng ICD-10"""
    if db_path is None:
        db_path = os.path.join(BASE_DIR, "db", "medical_codes.db")
    if not os.path.exists(db_path):
        return [], []
        
    member_upper = str(member_flag).upper()
    if member_upper == "A":
        letters = ["A", "B", "C", "D", "E", "F", "G", "H"]
    elif member_upper in ["B", "LONG"]:
        letters = ["I", "J", "K", "L", "M", "N", "O", "P"]
    elif member_upper == "C":
        letters = ["Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
    else:
        letters = ["I", "J", "K", "L", "M", "N", "O", "P"]
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    all_partition_codes, common_partition_codes = [], []
    
    try:
        placeholders = ",".join(["?"] * len(letters))
        query = f"""
            SELECT code, name_vi, "Thường gập"
            FROM icd10 
            WHERE substr(code, 1, 1) IN ({placeholders})
        """
        cursor.execute(query, letters)
        for row in cursor.fetchall():
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
    """Định dạng JSON thụt lề nhưng giữ các mảng ngắn trên cùng một dòng"""
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    json_str = re.sub(r'\[\s*\n\s*(\d+),\s*\n\s*(\d+)\s*\n\s*\]', r'[\1, \2]', json_str)
    json_str = re.sub(r'\[\s*\n\s*\]', r'[]', json_str)
    json_str = re.sub(r'\[\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1"]', json_str)
    json_str = re.sub(r'\[\s*\n\s*"([^"]+)",\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1", "\2"]', json_str)
    return json_str

def build_prompt_text(scenario_id, style_id, disease, drugs_list):
    """Xây dựng nội dung prompt chỉ thị chi tiết (V4 - Tăng độ dài, đa dạng từ vựng & nhãn xét nghiệm)"""
    sec1_titles = ["Tiền sử bệnh", "Tiền sử bệnh nội khoa", "Bệnh nền", "Các bệnh mãn tính"]
    sec2_titles = ["Tiền sử bệnh hiện tại", "Bệnh sử hiện tại", "Bệnh sử", "Diễn biến bệnh lý"]
    sec3_titles = ["Đánh giá tại bệnh viện", "Khám lúc vào viện", "Cận lâm sàng & Y lệnh", "Điều trị tại bệnh viện"]
    s1, s2, s3 = random.choice(sec1_titles), random.choice(sec2_titles), random.choice(sec3_titles)

    contexts = [
        "BỐI CẢNH LÂM SÀNG: Hồ sơ bệnh án điều trị nội trú chi tiết tại Bệnh viện Đa khoa.",
        "BỐI CẢNH LÂM SÀNG: Phiếu khám bệnh ngoại trú và tư vấn y khoa chuyên sâu.",
        "BỐI CẢNH LÂM SÀNG: Tóm tắt hồ sơ bệnh án chuyển viện / Biên bản hội chẩn lâm sàng.",
        "BỐI CẢNH LÂM SÀNG: Tờ điều trị hàng ngày và ghi chú diễn tiến bệnh lý của bác sĩ.",
        "BỐI CẢNH LÂM SÀNG: Báo cáo ca bệnh lâm sàng phức tạp (Complex Case Report)."
    ]
    clinical_context = random.choice(contexts)

    if style_id == 1:
        prompt_style = f"PHONG CÁCH YÊU CẦU: Bệnh án lâm sàng bán cấu trúc (Case Report) chi tiết.\n1. {s1}\n2. {s2}\n3. {s3}"
    elif style_id == 2:
        prompt_style = "PHONG CÁCH YÊU CẦU: Diễn đàn Q&A y khoa (Hỏi & Trả lời tư vấn chuyên sâu).\nHỏi : [Nội dung câu hỏi dài của người bệnh mô tả đầy đủ triệu chứng, tiền sử]\nTrả lời : Chào bạn, [Nội dung tư vấn chi tiết từ bác sĩ giải thích cặn kẽ]"
    elif style_id == 3:
        prompt_style = "PHONG CÁCH YÊU CẦU: Bài viết thông tin y khoa giáo dục sức khỏe (Medical Article).\n[TÊN BỆNH] LÀ GÌ?\n1. Khái niệm và nguyên nhân gây bệnh\n2. Triệu chứng lâm sàng, xét nghiệm chẩn đoán và hướng điều trị tây y"
    elif style_id == 4:
        prompt_style = f"PHONG CÁCH YÊU CẦU: Văn bản y khoa hỗn hợp (Hybrid/Mixed Document).\nGhép nối đoạn Hỏi & Đáp với ghi chú bệnh án cấu trúc (1. {s1} ... 2. {s2} ... 3. {s3}). Có thể chèn 1 đoạn dán nhầm không liên quan để tạo độ nhiễu thực tế."
    else:
        prompt_style = f"PHONG CÁCH YÊU CẦU: Bệnh án lâm sàng dịch từ tiếng Anh (Translated Clinical Note).\nDùng placeholder [Date], [Ngày], [Tên bác sĩ]. Giữ nguyên tên thuốc tiếng Anh (aspirin, ceftriaxone, troponin...). Hành văn dịch gượng ('phủ nhận buồn nôn', 'chủ quan sốt').\n1. {s1}\n2. {s2}\n3. {s3}"

    inject_negation = random.random() < 0.30
    inject_historical = random.random() < 0.25
    inject_family = random.random() < 0.25
    assertion_hint = ""
    if inject_negation:
        assertion_hint += "\nVăn bản PHẢI chứa ít nhất 1 thực thể bị phủ định (isNegated), ví dụ: 'phủ nhận buồn nôn', 'không sốt', 'không đau đầu'."
    if inject_historical and scenario_id != 4:
        assertion_hint += "\nVăn bản PHẢI chứa ít nhất 1 thực thể tiền sử bản thân (isHistorical), ví dụ: 'tiền sử THA 5 năm', 'đã mổ ruột thừa cách đây 2 năm'."
    if inject_family:
        assertion_hint += "\nVăn bản PHẢI chứa ít nhất 1 thực thể tiền sử gia đình (isFamily), ví dụ: 'bố đẻ tiền sử Đái tháo đường týp 2', 'mẹ có tiền sử Tăng huyết áp'."

    if scenario_id == 1:
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Sơ khám & chỉ định cận lâm sàng. Bác sĩ chỉ định các xét nghiệm cận lâm sàng (công thức máu, sinh hóa, X-quang, siêu âm, ECG). CHƯA có chẩn đoán bệnh xác định, CHƯA kê đơn thuốc.\nEntities: CHỈ trích xuất 'TRIỆU_CHỨNG', 'TÊN_XÉT_NGHIỆM', 'KẾT_QUẢ_XÉT_NGHIỆM'. Bắt buộc mô tả cụ thể tên xét nghiệm kèm chỉ số/kết quả xét nghiệm.\n{assertion_hint}"
    elif scenario_id == 2:
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Có chẩn đoán bệnh '{disease['name']}' nhưng KHÔNG kê đơn thuốc (chỉ định phẫu thuật/theo dõi lối sống). Mô tả chi tiết kết quả cận lâm sàng khẳng định chẩn đoán.\nEntities: Bắt buộc trích xuất '{disease['name']}' nhãn CHẨN_ĐOÁN, kèm 'TRIỆU_CHỨNG', 'TÊN_XÉT_NGHIỆM', 'KẾT_QUẢ_XÉT_NGHIỆM'. TUYỆT ĐỐI không trích xuất THUỐC.\n{assertion_hint}"
    elif scenario_id == 3:
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Chẩn đoán bệnh '{disease['name']}' kèm đơn thuốc điều trị nội khoa hợp lý chọn từ: {', '.join(drugs_list)}.\nEntities: Trích xuất '{disease['name']}' nhãn CHẨN_ĐOÁN, 1-3 thuốc chọn nhãn THUỐC, kèm triệu chứng và xét nghiệm cận lâm sàng.\n{assertion_hint}"
    else:
        hist_drug = random.choice(drugs_list)
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Ghi nhận tiền sử dùng thuốc dài hạn '{hist_drug}'.\nEntities: Trích xuất '{hist_drug}' nhãn THUỐC với assertions=['isHistorical'].\n{assertion_hint}"

    # BẮT BUỘC ĐỘ DÀI LỚN TỪ 600 - 900 TỪ (ĐỂ KÉO TRUNG BÌNH >= 450 TỪ)
    length_hint = """🛑 BẮT BUỘC VỀ ĐỘ DÀI VĂN BẢN (STRICT LENGTH REQUIREMENT):
- Trường 'text' BẮT BUỘC ĐẠT ĐỘ DÀI TỪ 600 ĐẾN 900 TỪ (TUYỆT ĐỐI KHÔNG ĐƯỢC NGẮN HƠN 550 TỪ). 
- PHẢI viết cực kỳ chi tiết và kéo dài văn bản: mô tả tỉ mỉ từng mốc thời gian diễn biến bệnh lý từ 5-7 ngày trước, liệt kê tiền sử bản thân & gia đình đầy đủ, kết quả khám chi tiết từng cơ quan (tuần hoàn, hô hấp, tiêu hóa, thần kinh, cơ xương khớp), các bảng chỉ số xét nghiệm cận lâm sàng (công thức máu, sinh hóa, X-quang, ECG) kèm đơn thuốc chi tiết (tên thuốc, liều dùng, đường dùng, tần suất)."""

    mask_drug_hint = "\nMÔ PHỎNG ẨN DANH HÓA THUỐC: Ngẫu nhiên che 1-2 tên thuốc bằng dấu sao (************). Thuốc bị che KHÔNG trích xuất." if random.random() < 0.20 else ""
    typo_hint = "\nBƠM NHIỄU LỖI GÕ: Tạo 1-2 lỗi gõ (dính chữ, lỗi dấu). Cụm trích xuất phải khớp chính xác text chứa lỗi." if random.random() < 0.20 else ""

    prompt = f"""
Hãy sinh ra một văn bản y khoa tiếng Việt theo thông tin được chỉ định dưới đây:

{clinical_context}

{length_hint}

{prompt_style}

{prompt_scenario}

--- YÊU CẦU ĐẦU RA BẮT BUỘC ---
Đầu ra PHẢI là một đối tượng JSON chuẩn (chỉ trả về duy nhất chuỗi JSON, không kèm bất kỳ lời giải thích markdown nào khác):
{{
  "text": "Nội dung đoạn văn bản y khoa thô sinh ra (BẮT BUỘC dài từ 600-900 từ, giữ nguyên toàn bộ các dấu xuống dòng \\n)",
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
4. Trích xuất tối đa 6-10 thực thể tiêu biểu nhất xuất hiện trong văn bản (ưu tiên trích xuất cả TÊN_XÉT_NGHIỆM và KẾT_QUẢ_XÉT_NGHIỆM nếu có).
{mask_drug_hint}
{typo_hint}
"""
    return prompt

def generate_call_gemini(api_key, prompt, model_name=None):
    """Gọi API Google AI Studio (Gemini) với xoay vòng Model"""
    if not model_name:
        model_name = key_manager.get_next_gemini_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8}
    }
    res = requests.post(url, headers=headers, json=payload, timeout=90)
    return res, model_name

def generate_call_groq(api_key, prompt, model_name=None):
    """Gọi API Groq Cloud"""
    if not model_name:
        m_info = key_manager.get_next_model("groq")
        model_name = m_info["id"] if m_info else "llama-3.3-70b-versatile"
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a helpful medical data generator. Always output raw JSON only."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.8
    }
    res = requests.post(url, headers=headers, json=payload, timeout=90)
    return res, model_name

def generate_call_sambanova(api_key, prompt, model_name=None):
    """Gọi API SambaNova"""
    if not model_name:
        m_info = key_manager.get_next_model("sambanova")
        model_name = m_info["id"] if m_info else "DeepSeek-V3.1"
    url = "https://api.sambanova.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a helpful medical data generator. Always output raw JSON only."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.8
    }
    res = requests.post(url, headers=headers, json=payload, timeout=90)
    return res, model_name

def generate_call_ninerouter(api_key, prompt, model_name=None):
    """Gọi API Local Proxy 9router"""
    if not model_name:
        m_info = key_manager.get_next_model("ninerouter")
        model_name = m_info["id"] if m_info else "medical-gen"
    url = "http://localhost:20128/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a helpful medical data generator. Always output raw JSON only."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.8
    }
    res = requests.post(url, headers=headers, json=payload, timeout=120)
    return res, model_name

global_provider_toggle = "groq"

def generate_with_smart_rotation(provider, prompt, max_attempts=15):
    """Cơ chế xoay vòng Key thông minh (Gemini / Groq / 9router)"""
    global global_provider_toggle
    
    for attempt in range(max_attempts):
        if provider == "auto":
            # Lấy danh sách nhà cung cấp có key khả dụng
            available_providers = []
            for p in ["groq", "gemini", "sambanova", "ninerouter"]:
                if p in key_manager.keys_by_provider:
                    total_keys = sum(len(keys) for keys in key_manager.keys_by_provider[p].values())
                    if total_keys >= 2:
                        available_providers.append(p)
                    
            if not available_providers:
                available_providers = ["groq"]
                
            if global_provider_toggle not in available_providers:
                global_provider_toggle = available_providers[0]
                
            current_provider = global_provider_toggle
            # Xoay toggle sang provider tiếp theo trong danh sách sẵn có
            next_idx = (available_providers.index(current_provider) + 1) % len(available_providers)
            global_provider_toggle = available_providers[next_idx]
        else:
            current_provider = provider

        key_res = key_manager.get_next_key(current_provider)
        
        if not key_res:
            for fallback in available_providers:
                if fallback != current_provider:
                    key_res = key_manager.get_next_key(fallback)
                    if key_res:
                        current_provider = fallback
                        break
                        
            if not key_res:
                print(f"  ⚠️ Tất cả các Key thuộc nhóm [{', '.join(available_providers).upper()}] đều đang Cooldown. Tạm nghỉ 5s...")
                time.sleep(5)
                continue
                
        api_key, account_id, key_info = key_res
        
        try:
            # Đọc trực tiếp thời gian dãn cách rpm_delay_seconds từ models_registry.json
            m_list = key_manager.models_by_provider.get(current_provider, [])
            delay_sec = m_list[0].get("rpm_delay_seconds", 4.0) if m_list else 2.0
            time.sleep(random.uniform(delay_sec * 0.8, delay_sec * 1.2))
            
            if current_provider == "gemini":
                res, used_model = generate_call_gemini(api_key, prompt)
            elif current_provider == "groq":
                res, used_model = generate_call_groq(api_key, prompt)
            elif current_provider == "sambanova":
                res, used_model = generate_call_sambanova(api_key, prompt)
            else:
                res, used_model = generate_call_ninerouter(api_key, prompt)

            print(f"  👉 [THỬ LẦN {attempt+1}] Gửi API -> Nhà cung cấp: [{current_provider.upper()} ({used_model})] | TK: [{account_id.upper()}] (Key: {api_key[:10]}...)")

            # Xử lý khi bị Rate Limit (429)
            if res.status_code == 429:
                print(f"  🛑 Key [{api_key[:12]}...] (TK: {account_id.upper()}) dính Rate Limit 429 với Model [{used_model}]. Đang đóng băng Key 120s...")
                key_manager.mark_rate_limited(key_info, cooldown_seconds=120.0)
                if "limit: 0" in res.text or "Quota exceeded" in res.text:
                    key_manager.mark_model_out_of_quota(current_provider, used_model)
                continue
                
            if res.status_code != 200:
                print(f"  ❌ Lỗi API {res.status_code} (TK: {account_id.upper()}): {res.text[:150]}")
                time.sleep(2)
                continue
                
            # Đã gọi thành công 200 OK
            key_manager.mark_success(key_info)
            
            if res.text.strip().startswith("data: "):
                # Giải mã luồng SSE Stream (dành cho các model dạng Stream như kr/qwen3-coder-next)
                full_content = []
                for line in res.text.split('\n'):
                    line = line.strip()
                    if line.startswith("data: "):
                        json_str = line[len("data: "):].strip()
                        if json_str == "[DONE]":
                            continue
                        try:
                            chunk = json.loads(json_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                full_content.append(delta["content"])
                        except Exception:
                            pass
                content_text = "".join(full_content)
            else:
                try:
                    res_data = res.json()
                except Exception:
                    match_res = re.search(r'\{.*\}', res.text)
                    if match_res:
                        res_data = json.loads(match_res.group(0))
                    else:
                        res_data = json.loads(res.text.strip().split('\n')[0])
                
                if current_provider == "gemini":
                    content_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    content_text = res_data["choices"][0]["message"]["content"]
                
            # Parse JSON siêu bền bỉ bằng regex bóc tách khối {...}
            match = re.search(r'\{.*\}', content_text, re.DOTALL)
            if match:
                cleaned_text = match.group(0)
            else:
                cleaned_text = content_text.strip()
                
            return json.loads(cleaned_text), account_id, current_provider

        except requests.exceptions.Timeout:
            print(f"  ⚠️ [THỬ LẠI] Mạng nghẽn Timeout 90s với TK {account_id.upper()} (lần {attempt+1}) -> Đang tự động đổi sang Key/Model khác...")
            time.sleep(1)
        except json.JSONDecodeError:
            print(f"  ⚠️ [THỬ LẠI] Server trả về nội dung rỗng/lỗi JSON với TK {account_id.upper()} (lần {attempt+1}) -> Đang tự động đổi sang Key/Model khác...")
            time.sleep(1)
        except Exception as e:
            print(f"  ⚠️ [THỬ LẠI] Lỗi tạm thời ({type(e).__name__}: {e}) với TK {account_id.upper()} (lần {attempt+1}) -> Đang đổi Key...")
            time.sleep(1)
            
    return None, None, None

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
            
        raw_text = text.strip(" \t\n\r,.;")
        if not raw_text:
            continue
        start_idx = clinical_text.find(raw_text)
        if start_idx == -1:
            start_idx = clinical_text.find(text)
            if start_idx == -1:
                continue
            raw_text = text
        end_idx = start_idx + len(raw_text)
        position = [start_idx, end_idx]
        text = raw_text
        
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

stats_lock = threading.Lock()

def record_sample_stats(member, file_idx, provider, account):
    """Cập nhật trực tiếp file stats.json tổng hợp của member mà không cần ghi file metadata lẻ"""
    member_dir = os.path.join(BASE_DIR, f"sample_{member}")
    stats_file = os.path.join(member_dir, "stats.json")
    os.makedirs(member_dir, exist_ok=True)
    
    provider_up = provider.upper()
    account_up = account.upper()
    
    with stats_lock:
        stats_data = {
            "member": member,
            "total_samples_with_metadata": 0,
            "by_provider": {},
            "by_account": {},
            "last_updated": ""
        }
        if os.path.exists(stats_file):
            try:
                with open(stats_file, "r", encoding="utf-8") as f:
                    stats_data = json.load(f)
            except Exception:
                pass

        stats_data["total_samples_with_metadata"] = stats_data.get("total_samples_with_metadata", 0) + 1
        
        bp = stats_data.get("by_provider", {})
        bp[provider_up] = bp.get(provider_up, 0) + 1
        stats_data["by_provider"] = bp
        
        ba = stats_data.get("by_account", {})
        ba[account_up] = ba.get(account_up, 0) + 1
        stats_data["by_account"] = ba
        
        stats_data["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return stats_data

def main():
    parser = argparse.ArgumentParser(description="Script sinh dữ liệu huấn luyện y khoa V3 (Account-Level Key Rotation)")
    parser.add_argument("--member", type=str, required=True, help="Mã thành viên/Tên thư mục (Ví dụ: Long, A, B, C)")
    parser.add_argument("--provider", type=str, default="auto", choices=["auto", "gemini", "groq", "sambanova", "ninerouter"], help="Nhà cung cấp AI (auto: đan xen liên tục giữa Gemini, Groq, SambaNova và 9router)")
    parser.add_argument("--num_samples", type=int, default=2000, help="Số lượng mẫu cần sinh")
    parser.add_argument("--start_idx", type=int, default=None, help="Chỉ số bắt đầu (chạy song song)")
    parser.add_argument("--end_idx", type=int, default=None, help="Chỉ số kết thúc (chạy song song)")
    args = parser.parse_args()
    
    print(f"--- KHỞI ĐỘNG TIẾN TRÌNH SINH DỮ LIỆU V3 ---")
    print(f" * Nhà cung cấp: {args.provider.upper()}")
    print(f" * Thư mục đầu ra: sample_{args.member}")
    
    drugs_list = load_drugs_list()
    all_codes, common_codes = load_icd10_partition(args.member)
    
    if not all_codes or not drugs_list:
        print("Lỗi: Không tải được CSDL y khoa. Hãy kiểm tra các file CSDL.")
        sys.exit(1)
        
    input_dir = os.path.join(BASE_DIR, f"sample_{args.member}", "input")
    output_dir = os.path.join(BASE_DIR, f"sample_{args.member}", "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    if args.start_idx is not None and args.end_idx is not None:
        range_start = args.start_idx
        range_end = args.end_idx
        print(f" * Chế độ: SONG SONG (dải chỉ số [{range_start}, {range_end}])")
    else:
        range_start = 1
        range_end = args.num_samples
        print(f" * Chế độ: TUẦN TỰ (sinh {args.num_samples} mẫu)")
        
    indices_to_generate = []
    already_done = 0
    for idx in range(range_start, range_end + 1):
        part_num = (idx - 1) // 500 + 1
        txt_path = os.path.join(input_dir, f"part_{part_num}", f"{idx}.txt")
        legacy_txt_path = os.path.join(input_dir, f"{idx}.txt")
        if os.path.exists(txt_path) or os.path.exists(legacy_txt_path):
            already_done += 1
        else:
            indices_to_generate.append(idx)
            
    total_in_range = range_end - range_start + 1
    remaining = len(indices_to_generate)
    
    if already_done > 0:
        print(f"\n * [CHECKPOINT] Đã phát hiện {already_done}/{total_in_range} mẫu đã sinh.")
        print(f" * Tiếp tục sinh {remaining} mẫu còn thiếu.")
        
    if remaining == 0:
        print(f"\n=== Đã đủ {total_in_range} mẫu trong dải [{range_start}, {range_end}]. ===")
        sys.exit(0)
        
    success_count = 0
    fail_count = 0
    gen_pointer = 0
    provider_counts_session = {}
    
    while gen_pointer < len(indices_to_generate):
        current_file_idx = indices_to_generate[gen_pointer]
        total_done = already_done + success_count
        print(f"[{total_done + 1}/{total_in_range}] Đang sinh mẫu #{current_file_idx}...")
        
        # Chọn kịch bản & phong cách
        scenario_id = random.choices([1, 2, 3, 4], weights=[0.20, 0.25, 0.40, 0.15])[0]
        style_id = random.choices([1, 2, 3, 4, 5], weights=[0.25, 0.15, 0.15, 0.15, 0.30])[0]
        
        target_disease = None
        if scenario_id in [2, 3]:
            target_disease = random.choice(common_codes) if (common_codes and random.random() < 0.30) else random.choice(all_codes)
            
        prompt = build_prompt_text(scenario_id, style_id, target_disease, drugs_list)
        
        raw_sample, used_acc, used_provider = generate_with_smart_rotation(args.provider, prompt)
        
        if not raw_sample:
            print(" -> Thất bại sau nhiều lần xoay Key. Tạm nghỉ 10s...")
            fail_count += 1
            time.sleep(10)
            continue
            
        final_entities = process_and_align(raw_sample)
        text_val = raw_sample.get("text", "")
        text_content = text_val.strip() if isinstance(text_val, str) else ""
        
        if not text_content:
            print(" -> Cảnh báo: Mô hình trả về mẫu có 'text' rỗng hoặc None. Bỏ qua.")
            fail_count += 1
            continue
            
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
        gen_pointer += 1
        
        p_name = used_provider.upper() if used_provider else "UNKNOWN"
        acc_name = used_acc.upper() if used_acc else "UNKNOWN"
        
        provider_counts_session[p_name] = provider_counts_session.get(p_name, 0) + 1
        
        # Lưu metadata & ghi file stats.json chung
        cumul_provider, cumul_account, cumul_total = record_sample_stats(args.member, current_file_idx, p_name, acc_name)
        
        session_summary = " | ".join([f"{k}: {v}" for k, v in sorted(provider_counts_session.items())])
        cumul_summary = " | ".join([f"{k}: {v}" for k, v in sorted(cumul_provider.items())])
        
        sleep_sec = random.uniform(6.0, 10.0)
        print(f" ->  Thành công mẫu #{current_file_idx} [{p_name} - TK: {acc_name}]")
        print(f"     📊 Đợt này: [{session_summary}] | 🏆 Lũy kế stats.json (sample_{args.member}): [{cumul_summary}] (Nghỉ {sleep_sec:.1f}s)...")
        
        time.sleep(sleep_sec)

    print(f"\n=== HOÀN TẤT TIẾN TRÌNH V3 (Thành viên: {args.member}) ===")
    print(f" - Tổng đã hoàn thành trong dải: {already_done + success_count}/{total_in_range}")
    cumul_p, cumul_a, cumul_tot = update_aggregated_stats(args.member)
    print(f" - Báo cáo lưu trữ trong sample_{args.member}/stats.json:")
    for k, v in sorted(cumul_p.items()):
        print(f"    * {k}: {v} mẫu")

if __name__ == "__main__":
    main()


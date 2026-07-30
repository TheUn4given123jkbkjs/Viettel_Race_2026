"""
Module Ánh xạ ICD-10 Thông minh & Chuẩn hóa Y khoa (Smart ICD-10 Mapper).
Khắc phục triệt để các lỗi của FTS5 SQLite (như THA -> Y06, ĐTĐ -> E12.9/E13, Viêm phổi -> A50.04/giang mai).
"""
import re, sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "db" / "medical_codes.db"

# Từ điển ánh xạ trực tiếp các thuật ngữ lâm sàng thông dụng
EXACT_CLINICAL_MAP = {
    # Tăng huyết áp
    "tăng huyết áp": ["I10"],
    "tăng huyết áp vô căn": ["I10"],
    "tăng huyết áp nguyên phát": ["I10"],
    "tăng huyết áp độ 1": ["I10"],
    "tăng huyết áp độ 2": ["I10"],
    "tăng huyết áp độ 3": ["I10"],
    "tha": ["I10"],
    "tha vô căn": ["I10"],
    "bệnh tăng huyết áp": ["I10"],
    
    # Đái tháo đường / Tiểu đường
    "đái tháo đường": ["E11.9"],
    "đái tháo đường týp 2": ["E11.9"],
    "đái tháo đường tuýp 2": ["E11.9"],
    "đái tháo đường type 2": ["E11.9"],
    "đái tháo đường típ 2": ["E11.9"],
    "đái tháo đường loại 2": ["E11.9"],
    "đtđ": ["E11.9"],
    "đtđ týp 2": ["E11.9"],
    "đtđ tuýp 2": ["E11.9"],
    "đtđ type 2": ["E11.9"],
    "tiểu đường": ["E11.9"],
    "tiểu đường type 2": ["E11.9"],
    "tiểu đường tuýp 2": ["E11.9"],
    "tiểu đường loại 2": ["E11.9"],
    "tiểu đường típ 2": ["E11.9"],
    "đái tháo đường týp 1": ["E10.9"],
    "đái tháo đường tuýp 1": ["E10.9"],
    "đái tháo đường type 1": ["E10.9"],
    "đtđ týp 1": ["E10.9"],
    "tiểu đường thai kỳ": ["O24.4"],
    "đái tháo đường thai kỳ": ["O24.4"],
    
    # Hô hấp
    "viêm phổi": ["J18.9"],
    "viêm phổi cộng đồng": ["J18.1"],
    "viêm phổi cấp tính": ["J18.9"],
    "viêm phổi kẽ": ["J84.9"],
    "phổi tắc nghẽn mãn tính": ["J44.9"],
    "phổi tắc nghẽn mạn tính": ["J44.9"],
    "copd": ["J44.9"],
    "hen": ["J45.9"],
    "hen phế quản": ["J45.9"],
    "viêm phế quản": ["J20.9"],
    "viêm phế quản cấp": ["J20.9"],
    "viêm phế quản mạn": ["J42"],
    "viêm họng": ["J02.9"],
    "viêm họng cấp": ["J02.9"],
    "viêm amidan": ["J03.9"],
    "suy hô hấp": ["J96.9"],
    "suy hô hấp cấp": ["J96.0"],
    "suy hô hấp mạn": ["J96.1"],
    
    # Tim mạch / Mạch máu
    "bệnh tim": ["I51.9"],
    "bệnh tim mạch": ["I51.9"],
    "bệnh mạch vành": ["I25.1"],
    "bệnh tim thiếu máu cục bộ": ["I25.9"],
    "bệnh tim thiếu máu cục bộ mạn tính": ["I25.9"],
    "thiếu máu cơ tim": ["I25.9"],
    "nhồi máu cơ tim": ["I21.9"],
    "nmct": ["I21.9"],
    "suy tim": ["I50.9"],
    "suy tim độ 1": ["I50.9"],
    "suy tim độ 2": ["I50.9"],
    "suy tim độ 3": ["I50.9"],
    "suy tim độ 4": ["I50.9"],
    "suy tim mạn": ["I50.9"],
    "suy tim mạn tính": ["I50.9"],
    "suy tim cấp": ["I50.9"],
    "tai biến mạch máu não": ["I64"],
    "tbmmn": ["I64"],
    "đột quỵ": ["I64"],
    "đột quỵ não": ["I64"],
    "nhồi máu não": ["I63.9"],
    "xuất huyết não": ["I61.9"],
    "thiếu máu não": ["I67.8"],
    "rối loạn nhịp tim": ["I49.9"],
    "rung nhĩ": ["I48"],
    "xơ vữa động mạch": ["I70.9"],
    
    # Tiêu hóa
    "viêm dạ dày": ["K29.7"],
    "viêm dạ dày tá tràng": ["K29.9"],
    "viêm loét dạ dày": ["K25.9"],
    "viêm loét dạ dày tá tràng": ["K27.9"],
    "trào ngược dạ dày thực quản": ["K21.9"],
    "gerd": ["K21.9"],
    "viêm gan": ["K75.9"],
    "viêm gan b": ["B18.1"],
    "viêm gan b mạn tính": ["B18.1"],
    "viêm gan c": ["B18.2"],
    "xơ gan": ["K74.6"],
    "viêm túi mật": ["K81.9"],
    "viêm ruột thừa": ["K37"],
    "viêm ruột thừa cấp": ["K35.8"],
    
    # Cơ xương khớp
    "thoái hóa khớp": ["M19.9"],
    "thoái hóa khớp gối": ["M17.9"],
    "thoái hóa cột sống": ["M47.9"],
    "thoái hóa cột sống thắt lưng": ["M47.8"],
    "thoái hóa cột sống cổ": ["M47.8"],
    "gút": ["M10.9"],
    "gout": ["M10.9"],
    "bệnh gout": ["M10.9"],
    "bệnh gút": ["M10.9"],
    "viêm khớp dạng thấp": ["M06.9"],
    "thoát vị đĩa đệm": ["M51.2"],
    "đau lưng": ["M54.5"],
    "đau thắt lưng": ["M54.5"],
    
    # Thần kinh / Tâm thần
    "trầm cảm": ["F32.9"],
    "rối loạn trầm cảm": ["F32.9"],
    "rối loạn lo âu": ["F41.9"],
    "mất ngủ": ["G47.0"],
    "mất ngủ mạn tính": ["G47.0"],
    "rối loạn giấc ngủ": ["G47.9"],
    "động kinh": ["G40.9"],
    "parkinson": ["G20"],
    "bệnh parkinson": ["G20"],
    "alzheimer": ["G30.9"],
    
    # Thận - Tiết niệu
    "suy thận": ["N18.9"],
    "suy thận mạn": ["N18.9"],
    "suy thận mạn tính": ["N18.9"],
    "suy thận cấp": ["N17.9"],
    "sỏi thận": ["N20.0"],
    "sỏi tiết niệu": ["N20.9"],
    "viêm bàng quang": ["N30.9"],
    "nhiễm trùng đường tiết niệu": ["N39.0"],
    
    # Nội tiết / Khác
    "rối loạn lipid máu": ["E78.5"],
    "tăng lipid máu": ["E78.5"],
    "tăng cholesterol": ["E78.0"],
    "béo phì": ["E66.9"],
    "suy giáp": ["E03.9"],
    "cường giáp": ["E05.9"],
    "bướu cổ": ["E04.9"],
    "sốt xuất huyết": ["A91"],
    "dengue": ["A90"],
    "sốt xuất huyết dengue": ["A91"],
    "quai bị": ["B26.9"],
    "thủy đậu": ["B01.9"],
    "sởi": ["B05.9"],
    "covid-19": ["U07.1"],
    
    # Bệnh hiếm (V6.0+ Cân bằng dịch tễ)
    "loạn dưỡng cơ duchenne": ["G71.0"],
    "hội chứng down": ["Q90.9"],
    "hội chứng down (trisomy 21)": ["Q90.9"],
    "tiêu chảy nhiễm trùng": ["A09.0"],
    "giảm gammaglobulin di truyền (bruton)": ["D80.0"],
    "giảm gammaglobulin di truyền": ["D80.0"],
    "phenylketonuria (pku)": ["E70.0"],
    "phenylketonuria": ["E70.0"],
    "hội chứng hurler (mps i)": ["E76.0"],
    "hội chứng hurler": ["E76.0"],
    "nhược cơ (myasthenia gravis)": ["G70.0"],
    "nhược cơ": ["G70.0"],
    "thông liên thất bẩm sinh (vsd)": ["Q21.0"],
    "thông liên thất bẩm sinh": ["Q21.0"],
    "scid (suy giảm miễn dịch kết hợp nặng)": ["D81.9"],
    "scid": ["D81.9"],
    "bệnh nước tiểu mùi sirô phong (msud)": ["E71.0"],
    "bệnh nước tiểu mùi sirô phong": ["E71.0"],
    "nhiễm hp": ["B96.81"],
    "gan nhiễm mỡ độ ii": ["K76.0"],
    "gan nhiễm mỡ độ 2": ["K76.0"],
    "viêm tuyến giáp tự miễn hashimoto": ["E06.3"],
    "viêm tuyến giáp hashimoto": ["E06.3"],
    "hashimoto": ["E06.3"],
    "dày thất trái": ["I51.7"],
    "nhiểm khuẩn phổi": ["J18.9"],
    "co giật toàn thể": ["G40.9"],
    "sỏi mật": ["K80"],
    "sỏi mậ": ["K80"],
    "béo phì độ ii": ["E66.9"],
    "béo phì độ 2": ["E66.9"],
    "loét dạ dày cấp tính": ["K25.3"],
    "ung thư phổi": ["C34.9"],
    "ung thư phổi giai đoạn 3a": ["C34.9"],
    "loét dạ dày tá tràng": ["K27.9"],
    "bệnh loét dạ dày tá tràng": ["K27.9"]
}

# Danh sách các mã nhạy cảm/đặc biệt không bao giờ trả về bừa bãi qua FTS
EXCLUDED_CHAPTERS_PATTERN = re.compile(r'^(A50|A51|A52|A53|A54|B06|O0|O1|O2|O3|O4|O5|O6|O7|O8|O9|Z35|Y06)')

def normalize_text(text):
    """Chuẩn hóa văn bản thực thể."""
    t = text.strip().lower()
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def extract_actual_disease_from_prefix(text):
    """Xử lý các thực thể dạng tiền tố y khoa -> trả về cụm từ bệnh sạch."""
    # Remove parentheses contents (e.g., "(Trisomy 21)", "(MPS I)") on the raw text first!
    raw_clean = re.sub(r'\s*\([^)]*\)', '', text).strip()
    
    # Strip "ICD-10: " prefix if present
    raw_clean = re.sub(r'^icd-10:\s*', '', raw_clean, flags=re.IGNORECASE).strip()
    
    # Strip suffix details like "đã phẫu thuật..."
    raw_clean = re.sub(r'\s+đã\s+(phẫu thuật|mổ|cắt).*$', '', raw_clean, flags=re.IGNORECASE).strip()
    raw_clean = re.sub(r'\s+(đã\s+)?được\s+(phẫu thuật|mổ|cắt).*$', '', raw_clean, flags=re.IGNORECASE).strip()
    
    t = normalize_text(raw_clean)
    
    # Loại bỏ tiền tố tiền sử / gia đình / điều trị bằng một regex hợp nhất
    t = re.sub(r'^(mẹ đẻ|bố đẻ|cha đẻ|cha|mẹ|ông|bà|anh|chị|em|gia đình|bản thân)\s+(của tôi\s+|của bệnh nhân\s+)?(có\s+)?(tiền sử\s+)?', '', t).strip()
    t = re.sub(r'^(tiền sử điều trị|tiền sử|tiền căn|điều trị ổn định|điều trị|mắc|chẩn đoán|theo dõi|bị|nghi ngờ|có tiền sử)\s+', '', t).strip()
    
    # Loại bỏ thông tin số năm ở cuối (vd "5 năm", "10 năm")
    t = re.sub(r'\s+\d+\s*năm$', '', t).strip()
    
    return t

def smart_icd10_lookup(cursor, text):
    """
    Tra cứu mã ICD-10 thông minh & an sau cho văn bản chẩn đoán.
    Trả về danh sách 1-3 mã ICD-10 chuẩn xác nhất.
    """
    if not text or not text.strip():
        return []
        
    # Clean ICD-10 prefix if present
    clean_text = re.sub(r'^icd-10:\s*', '', text.strip(), flags=re.IGNORECASE).strip()
    
    # Rule 0: If the text contains any valid ICD-10 code anywhere, extract and return it directly
    code_match = re.search(r'\b([A-Z]\d{2}(?:\.\d{1,2})?)\b', clean_text.upper())
    if code_match:
        return [code_match.group(1)]
        
    norm = normalize_text(text)
    
    # Rule 1: Handle composites connected by " và ", "/" or " kèm "
    delimiters = [r'\s+và\s+', r'\s*/\s*', r'\s+kèm\s+']
    for delim in delimiters:
        if re.search(delim, clean_text, re.IGNORECASE):
            parts = re.split(delim, clean_text, flags=re.IGNORECASE)
            res = []
            for p in parts:
                p_res = smart_icd10_lookup(cursor, p)
                for c in p_res:
                    if c not in res:
                        res.append(c)
            if res:
                return res[:3]
            
    # 2. Tra cứu tiền sử / gia đình trước
    extracted = extract_actual_disease_from_prefix(text)
    if extracted in EXACT_CLINICAL_MAP:
        return EXACT_CLINICAL_MAP[extracted]
        
    # 3. Tra cứu trực tiếp từ điển lâm sàng
    if norm in EXACT_CLINICAL_MAP:
        return EXACT_CLINICAL_MAP[norm]
        
    # 4. Phân tích cụm từ chính
    # ĐTĐ
    if any(k in norm for k in ["đái tháo đường", "tiểu đường", "dtd"]):
        if "1" in norm:
            return ["E10.9"]
        elif "thai kỳ" in norm:
            return ["O24.4"]
        else:
            return ["E11.9"]
            
    # THA
    if any(k in norm for k in ["tăng huyết áp", "tha"]):
        if any(k in norm for k in ["tim", "suy tim"]):
            return ["I11"]
        elif any(k in norm for k in ["não", "đột quỵ", "tai biến"]):
            return ["I67.4"]
        else:
            return ["I10"]
            
    # Viêm phổi
    if "viêm phổi" in norm:
        if "cộng đồng" in norm:
            return ["J18.1"]
        elif "giang mai" in norm:
            return ["A50.04"]
        elif "rubella" in norm:
            return ["B06.81"]
        elif "lậu" in norm:
            return ["A54.84"]
        else:
            return ["J18.9"]
            
    # 5. Fallback SQL FTS nhưng lọc bỏ mã nhạy cảm (Giang mai, Lậu, Phá thai, Thai sản, Y06)
    if cursor:
        try:
            # Clean term for SQLite
            clean_fts = re.sub(r'[^\w\s]', ' ', extracted if extracted else norm).strip()
            if clean_fts:
                cursor.execute("SELECT code, name_vi FROM icd10_fts WHERE name_vi MATCH ? LIMIT 10", (clean_fts,))
                rows = cursor.fetchall()
                
                filtered = []
                for code, name in rows:
                    if EXCLUDED_CHAPTERS_PATTERN.match(code):
                        if any(kw in norm for kw in ["giang mai", "lậu", "rubella", "phá thai", "sẩy thai", "chửa", "thai phụ", "vô sinh", "cẩu thả"]):
                            filtered.append(code)
                    else:
                        filtered.append(code)
                        
                if filtered:
                    return filtered[:3]
        except Exception:
            pass
            
    return []

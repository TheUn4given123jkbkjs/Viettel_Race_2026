"""
═══════════════════════════════════════════════════════════════
  GENERATE_TRAIN_DATA_V3.py — Sinh dữ liệu y khoa chuẩn hóa V6.0
  Cân bằng ma trận bệnh lý + Smart ICD-10 Mapper + Ràng buộc thuốc
  Tương thích 100% với hạ tầng Long_folder (key_manager, multi-provider)
═══════════════════════════════════════════════════════════════
"""
import os, sys, sqlite3, requests, json, re, time, random, argparse, threading
from pathlib import Path

# Đảm bảo in unicode không lỗi
if sys.stdout.encoding != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(BASE_DIR) == "Long_folder":
    BASE_DIR = os.path.dirname(BASE_DIR)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, "scratch"))

from key_manager import key_manager
from icd10_mapper import smart_icd10_lookup

# ══════════════════════════════════════════════════════════
#  MA TRẬN PHÂN BỔ BỆNH MỤC TIÊU (theo dịch tễ VN + bệnh hiếm)
# ══════════════════════════════════════════════════════════

DISEASE_DISTRIBUTION = [
    # --- NHÓM PHỔ BIẾN (85% tổng mẫu) ---
    # (weight, icd_prefix, disease_name_vi, disease_context_hint)
    
    # Tim mạch (25%)
    (0.08, "I10",   "Tăng huyết áp", "bệnh nhân tăng huyết áp vô căn, dùng thuốc hạ áp lâu dài"),
    (0.04, "I25.9", "Bệnh tim thiếu máu cục bộ mạn tính", "bệnh mạch vành, đau thắt ngực, stent"),
    (0.04, "I50.9", "Suy tim", "suy tim mạn, phù chi dưới, khó thở khi gắng sức"),
    (0.03, "I21.9", "Nhồi máu cơ tim cấp", "NMCT cấp, đau ngực dữ dội, troponin tăng cao"),
    (0.03, "I64",   "Đột quỵ não", "tai biến mạch máu não, liệt nửa người, CT scan"),
    (0.03, "I48",   "Rung nhĩ", "rung nhĩ, loạn nhịp hoàn toàn, chống đông"),
    
    # Tiêu hóa (15%)
    (0.04, "K29.7", "Viêm dạ dày", "viêm dạ dày mạn, nhiễm HP, nội soi dạ dày"),
    (0.03, "K25.9", "Loét dạ dày", "loét dạ dày tá tràng, đau thượng vị, xuất huyết tiêu hóa"),
    (0.02, "K21.9", "Trào ngược dạ dày thực quản", "GERD, trào ngược acid, ợ nóng"),
    (0.02, "K74.6", "Xơ gan", "xơ gan do rượu/viêm gan B, cổ trướng, giãn tĩnh mạch thực quản"),
    (0.02, "K80.2", "Sỏi mật", "sỏi túi mật, đau hạ sườn phải, siêu âm"),
    (0.02, "K37",   "Viêm ruột thừa", "viêm ruột thừa cấp, đau hố chậu phải, phẫu thuật"),
    
    # Hô hấp (15%)
    (0.04, "J18.9", "Viêm phổi", "viêm phổi cộng đồng, sốt ho đờm, X-quang phổi"),
    (0.03, "J44.9", "COPD", "bệnh phổi tắc nghẽn mạn tính, khó thở, FEV1 giảm"),
    (0.03, "J45.9", "Hen phế quản", "hen phế quản, khò khè, khó thở về đêm"),
    (0.02, "J20.9", "Viêm phế quản cấp", "viêm phế quản cấp, ho đờm xanh, kháng sinh"),
    (0.02, "J02.9", "Viêm họng", "viêm họng cấp, đau họng, nuốt đau, amoxicillin"),
    (0.01, "J96.0", "Suy hô hấp cấp", "suy hô hấp cấp, SpO2 giảm, thở máy"),

    # Nội tiết & chuyển hóa (12%)
    (0.05, "E11.9", "Đái tháo đường type 2", "ĐTĐ type 2, HbA1c tăng, metformin"),
    (0.02, "E10.9", "Đái tháo đường type 1", "ĐTĐ type 1, insulin, tự miễn"),
    (0.02, "E78.5", "Rối loạn lipid máu", "tăng cholesterol, tăng triglyceride, statin"),
    (0.01, "E05.9", "Cường giáp", "basedow, run tay, nhịp tim nhanh, PTU"),
    (0.01, "E03.9", "Suy giáp", "suy giáp, mệt mỏi, tăng cân, levothyroxine"),
    (0.01, "E66.9", "Béo phì", "béo phì, BMI > 30, chế độ ăn giảm cân"),

    # Cơ xương khớp (10%)
    (0.03, "M17.9", "Thoái hóa khớp gối", "thoái hóa khớp gối, đau khi đi lại, tiêm hyaluronic"),
    (0.02, "M47.9", "Thoái hóa cột sống", "thoái hóa cột sống thắt lưng/cổ, đau lưng mạn tính"),
    (0.02, "M10.9", "Bệnh gút", "gút, sưng nóng đỏ đau khớp bàn chân, acid uric tăng"),
    (0.01, "M06.9", "Viêm khớp dạng thấp", "viêm khớp dạng thấp, sưng khớp đối xứng, RF dương tính"),
    (0.01, "M51.2", "Thoát vị đĩa đệm", "thoát vị đĩa đệm thắt lưng, đau lan chân, MRI"),
    (0.01, "M54.5", "Đau thắt lưng", "đau lưng dưới, co cứng cơ cạnh sống"),

    # Thần kinh - Tâm thần (8%)
    (0.02, "F32.9", "Trầm cảm", "trầm cảm, buồn bã kéo dài, mất ngủ, SSRI"),
    (0.02, "F41.9", "Rối loạn lo âu", "lo âu lan tỏa, hồi hộp, khó tập trung"),
    (0.01, "G40.9", "Động kinh", "động kinh, co giật toàn thể, valproate"),
    (0.01, "G20",   "Bệnh Parkinson", "run khi nghỉ, cứng cơ, chậm vận động, levodopa"),
    (0.01, "G47.0", "Mất ngủ", "mất ngủ mạn tính, khó vào giấc"),
    (0.01, "G30.9", "Alzheimer", "sa sút trí tuệ, quên gần, mất định hướng"),

    # Nhiễm trùng (7%)
    (0.02, "A91",   "Sốt xuất huyết Dengue", "SXH, giảm tiểu cầu, thoát huyết tương, truyền dịch"),
    (0.01, "B18.1", "Viêm gan B mạn", "viêm gan B mạn, HBV DNA, tenofovir"),
    (0.01, "B18.2", "Viêm gan C mạn", "viêm gan C, HCV RNA, sofosbuvir"),
    (0.01, "A09",   "Tiêu chảy nhiễm trùng", "tiêu chảy cấp, phân lỏng, mất nước, bù dịch"),
    (0.01, "N39.0", "Nhiễm trùng tiết niệu", "viêm bàng quang, tiểu buốt, tiểu rắt, kháng sinh"),
    (0.01, "A15.0", "Lao phổi", "lao phổi, ho máu, BK đờm dương tính, HRZE"),

    # Thận & Ung thư (8%)
    (0.02, "N18.9", "Suy thận mạn", "suy thận mạn, lọc máu, creatinine tăng"),
    (0.01, "N20.0", "Sỏi thận", "sỏi thận, đau quặn thận, siêu âm, tán sỏi"),
    (0.02, "C34.9", "Ung thư phổi", "ung thư phổi, ho ra máu, CT ngực, hóa trị"),
    (0.01, "C22.0", "Ung thư gan", "HCC, AFP tăng cao, viêm gan B, TACE"),
    (0.01, "C50.9", "Ung thư vú", "ung thư vú, u cục vú, mammography, phẫu thuật"),
    (0.01, "C16.9", "Ung thư dạ dày", "ung thư dạ dày, nội soi sinh thiết, hóa trị"),

    # --- BỆNH HIẾM GẶP (5% tổng mẫu) ---
    (0.005, "E70.0", "Phenylketonuria (PKU)", "phenyl-ceton niệu, sàng lọc sơ sinh, chế độ ăn đặc biệt"),
    (0.005, "E71.0", "Bệnh nước tiểu mùi sirô phong (MSUD)", "maple syrup urine disease, rối loạn acid amin chuỗi nhánh"),
    (0.005, "E75.2", "Bệnh Gaucher", "bệnh Gaucher, lách to, thiếu men glucocerebrosidase"),
    (0.005, "E76.0", "Hội chứng Hurler (MPS I)", "mucopolysaccharidosis type I, khuôn mặt thô, gan lách to"),
    (0.005, "G71.0", "Loạn dưỡng cơ Duchenne", "DMD, yếu cơ tiến triển, CK tăng rất cao, xe lăn"),
    (0.005, "G70.0", "Nhược cơ (Myasthenia Gravis)", "nhược cơ, sụp mi, yếu cơ giao động, neostigmine"),
    (0.005, "D80.0", "Giảm gammaglobulin di truyền (Bruton)", "agammaglobulinemia, nhiễm trùng tái phát, IVIG"),
    (0.005, "D81.0", "SCID (Suy giảm miễn dịch kết hợp nặng)", "SCID, nhiễm trùng nặng sơ sinh, ghép tủy"),
    (0.005, "Q21.0", "Thông liên thất bẩm sinh (VSD)", "tim bẩm sinh VSD, tiếng thổi tâm thu, siêu âm tim"),
    (0.005, "Q90.9", "Hội chứng Down (Trisomy 21)", "Down syndrome, chậm phát triển, xét nghiệm nhiễm sắc thể"),
]

# ══════════════════════════════════════════════════════════
#  MA TRẬN RÀNG BUỘC BỆNH → THUỐC (Clinical Drug Matrix)
# ══════════════════════════════════════════════════════════

CLINICAL_DRUG_MATRIX = {
    # Tim mạch
    "I10":   ["Amlodipine", "Losartan", "Perindopril", "Telmisartan", "Hydrochlorothiazide", "Nifedipine"],
    "I25.9": ["Aspirin", "Clopidogrel", "Atorvastatin", "Bisoprolol", "Nitroglycerin", "Isosorbide dinitrate"],
    "I50.9": ["Furosemide", "Spironolactone", "Enalapril", "Carvedilol", "Digoxin", "Sacubitril/Valsartan"],
    "I21.9": ["Aspirin", "Clopidogrel", "Heparin", "Atorvastatin", "Morphine", "Nitroglycerin"],
    "I64":   ["Aspirin", "Clopidogrel", "Atorvastatin", "Mannitol", "Citicoline", "Enoxaparin"],
    "I48":   ["Warfarin", "Rivaroxaban", "Amiodarone", "Digoxin", "Bisoprolol", "Apixaban"],
    
    # Tiêu hóa
    "K29.7": ["Omeprazole", "Pantoprazole", "Esomeprazole", "Aluminum Hydroxide", "Rebamipide", "Bismuth"],
    "K25.9": ["Omeprazole", "Pantoprazole", "Esomeprazole", "Clarithromycin", "Amoxicillin", "Metronidazole"],
    "K21.9": ["Omeprazole", "Pantoprazole", "Esomeprazole", "Domperidone", "Gaviscon", "Rabeprazole"],
    "K74.6": ["Spironolactone", "Furosemide", "Lactulose", "Propranolol", "Albumin", "Vitamin K"],
    "K80.2": ["Ursodeoxycholic acid", "Paracetamol", "Hyoscine", "Ceftriaxone"],
    "K37":   ["Ceftriaxone", "Metronidazole", "Paracetamol", "Tramadol"],
    
    # Hô hấp
    "J18.9": ["Amoxicillin", "Cefuroxime", "Ceftriaxone", "Azithromycin", "Paracetamol", "Levofloxacin"],
    "J44.9": ["Salbutamol", "Tiotropium", "Budesonide", "Formoterol", "Prednisolone", "Theophylline"],
    "J45.9": ["Salbutamol", "Budesonide", "Fluticasone", "Montelukast", "Ipratropium", "Prednisolone"],
    "J20.9": ["Amoxicillin", "Azithromycin", "Acetylcysteine", "Bromhexine", "Dextromethorphan"],
    "J02.9": ["Amoxicillin", "Paracetamol", "Ibuprofen", "Chlorhexidine"],
    "J96.0": ["Dexamethasone", "Epinephrine", "Midazolam", "Fentanyl"],
    
    # Nội tiết
    "E11.9": ["Metformin", "Gliclazide", "Empagliflozin", "Sitagliptin", "Insulin Glargine", "Dapagliflozin"],
    "E10.9": ["Insulin Lispro", "Insulin Glargine", "Insulin Aspart", "Glucagon"],
    "E78.5": ["Atorvastatin", "Rosuvastatin", "Fenofibrate", "Ezetimibe"],
    "E05.9": ["Methimazole", "Propylthiouracil", "Propranolol", "Lugol"],
    "E03.9": ["Levothyroxine"],
    "E66.9": ["Orlistat", "Metformin"],
    
    # Cơ xương khớp
    "M17.9": ["Paracetamol", "Meloxicam", "Celecoxib", "Glucosamine", "Hyaluronic acid"],
    "M47.9": ["Paracetamol", "Meloxicam", "Eperisone", "Gabapentin", "Prednisolone"],
    "M10.9": ["Colchicine", "Allopurinol", "Febuxostat", "Meloxicam", "Prednisolone"],
    "M06.9": ["Methotrexate", "Hydroxychloroquine", "Sulfasalazine", "Prednisolone", "Leflunomide"],
    "M51.2": ["Paracetamol", "Meloxicam", "Gabapentin", "Pregabalin", "Methylprednisolone"],
    "M54.5": ["Paracetamol", "Diclofenac", "Eperisone", "Thiocolchicoside"],
    
    # Thần kinh
    "F32.9": ["Sertraline", "Escitalopram", "Fluoxetine", "Amitriptyline", "Mirtazapine"],
    "F41.9": ["Sertraline", "Escitalopram", "Buspirone", "Alprazolam", "Hydroxyzine"],
    "G40.9": ["Valproate", "Carbamazepine", "Levetiracetam", "Lamotrigine", "Phenobarbital"],
    "G20":   ["Levodopa/Carbidopa", "Pramipexole", "Trihexyphenidyl", "Entacapone", "Rasagiline"],
    "G47.0": ["Zolpidem", "Melatonin", "Hydroxyzine", "Trazodone"],
    "G30.9": ["Donepezil", "Memantine", "Rivastigmine", "Galantamine"],
    
    # Nhiễm trùng
    "A91":   ["Paracetamol", "Ringer Lactate", "Dextrose 5%"],
    "B18.1": ["Tenofovir", "Entecavir", "Peginterferon alfa-2a"],
    "B18.2": ["Sofosbuvir", "Daclatasvir", "Ledipasvir", "Ribavirin"],
    "A09":   ["ORS", "Zinc", "Loperamide", "Ciprofloxacin"],
    "N39.0": ["Ciprofloxacin", "Nitrofurantoin", "Cefixime", "Fosfomycin"],
    "A15.0": ["Isoniazid", "Rifampicin", "Pyrazinamide", "Ethambutol"],
    
    # Thận & Ung thư
    "N18.9": ["Erythropoietin", "Calcium Carbonate", "Calcitriol", "Kayexalate", "Iron"],
    "N20.0": ["Tamsulosin", "Ketorolac", "Paracetamol", "Ciprofloxacin"],
    "C34.9": ["Cisplatin", "Carboplatin", "Paclitaxel", "Bevacizumab", "Erlotinib"],
    "C22.0": ["Sorafenib", "Lenvatinib", "Doxorubicin", "Cisplatin"],
    "C50.9": ["Tamoxifen", "Letrozole", "Trastuzumab", "Cyclophosphamide", "Doxorubicin"],
    "C16.9": ["Cisplatin", "Fluorouracil", "Oxaliplatin", "Capecitabine"],
    
    # Bệnh hiếm
    "E70.0": ["Sapropterin"],
    "E75.2": ["Imiglucerase", "Miglustat"],
    "G71.0": ["Prednisolone", "Deflazacort"],
    "G70.0": ["Pyridostigmine", "Prednisolone", "Azathioprine", "IVIG"],
    "Q21.0": ["Furosemide", "Captopril", "Digoxin"],
}

SEC1 = ["Tiền sử bệnh", "Tiền sử bệnh nội khoa", "Bệnh nền", "Các bệnh mãn tính"]
SEC2 = ["Tiền sử bệnh hiện tại", "Bệnh sử hiện tại", "Bệnh sử", "Diễn biến bệnh lý"]
SEC3 = ["Đánh giá tại bệnh viện", "Khám lúc vào viện", "Cận lâm sàng & Y lệnh", "Điều trị tại bệnh viện"]

CONTEXTS = [
    "BỐI CẢNH LÂM SÀNG: Hồ sơ bệnh án điều trị nội trú chi tiết tại Bệnh viện Đa khoa.",
    "BỐI CẢNH LÂM SÀNG: Phiếu khám bệnh ngoại trú và tư vấn y khoa chuyên sâu.",
    "BỐI CẢNH LÂM SÀNG: Tóm tắt hồ sơ bệnh án chuyển viện / Biên bản hội chẩn lâm sàng.",
    "BỐI CẢNH LÂM SÀNG: Tờ điều trị hàng ngày và ghi chú diễn tiến bệnh lý của bác sĩ.",
    "BỐI CẢNH LÂM SÀNG: Báo cáo ca bệnh lâm sàng phức tạp (Complex Case Report).",
]

def select_disease_weighted():
    """Chọn ngẫu nhiên một bệnh theo phân bổ trọng số."""
    weights = [d[0] for d in DISEASE_DISTRIBUTION]
    return random.choices(DISEASE_DISTRIBUTION, weights=weights, k=1)[0]

def query_local_db(entity_text, entity_type, db_path=None):
    """Truy vấn mã ICD-10 (Smart Mapper) hoặc RxNorm từ SQLite"""
    if db_path is None:
        db_path = os.path.join(BASE_DIR, "db", "medical_codes.db")
        
    if not os.path.exists(db_path):
        return []
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    candidates = []
    
    try:
        if entity_type == "CHẨN_ĐOÁN":
            candidates = smart_icd10_lookup(cursor, entity_text)
        elif entity_type == "THUỐC":
            term = entity_text.strip().lower()
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

def build_prompt_text(scenario_id, style_id, disease_entry, drugs_list):
    """Xây dựng nội dung prompt V6.0 kết hợp Cân bằng Ma trận & Ràng buộc Thuốc"""
    s1, s2, s3 = random.choice(SEC1), random.choice(SEC2), random.choice(SEC3)
    ctx = random.choice(CONTEXTS)
    
    if isinstance(disease_entry, tuple):
        icd_code = disease_entry[1]
        disease_name = disease_entry[2]
        disease_hint = disease_entry[3]
    else:
        icd_code = disease_entry.get("code", "I10")
        disease_name = disease_entry.get("name", "Tăng huyết áp")
        disease_hint = "bệnh lý tim mạch"

    # Lấy danh sách thuốc phù hợp từ ma trận lâm sàng
    specific_drugs = CLINICAL_DRUG_MATRIX.get(icd_code, [])
    if not specific_drugs:
        specific_drugs = random.sample(drugs_list, min(5, len(drugs_list))) if drugs_list else ["Paracetamol", "Aspirin"]

    # 1. Assertion hints
    inject_negation = random.random() < 0.30
    inject_historical = random.random() < 0.25
    inject_family = random.random() < 0.25
    assertion_hint = ""
    if inject_negation:
        assertion_hint += "\nVăn bản PHẢI chứa ít nhất 1 thực thể bị phủ định (isNegated), ví dụ: 'phủ nhận buồn nôn', 'không sốt', 'không đau đầu'."
    if inject_historical and scenario_id != 4:
        assertion_hint += "\nVăn bản PHẢI chứa ít nhất 1 thực thể tiền sử bản thân (isHistorical), ví dụ: 'tiền sử tăng huyết áp 5 năm', 'đã mổ ruột thừa cách đây 2 năm'."
    if inject_family:
        assertion_hint += "\nVăn bản PHẢI chứa ít nhất 1 thực thể tiền sử gia đình (isFamily), ví dụ: 'bố đẻ tiền sử đái tháo đường tuýp 2', 'mẹ đẻ có tiền sử tăng huyết áp'."

    # 2. Scenario specific instructions
    if scenario_id == 1:
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Sơ khám & chỉ định cận lâm sàng. Bác sĩ chỉ định các xét nghiệm cận lâm sàng (công thức máu, sinh hóa, X-quang, siêu âm, ECG). Bệnh nhân đang nghi ngờ mắc bệnh '{disease_name}' nhưng CHƯA có chẩn đoán bệnh xác định, CHƯA kê đơn thuốc.\nEntities: CHỈ trích xuất 'TRIỆU_CHỨNG', 'TÊN_XÉT_NGHIỆM', 'KẾT_QUẢ_XÉT_NGHIỆM'. Tuyệt đối không trích xuất 'CHẨN_ĐOÁN' hay 'THUỐC'.\n{assertion_hint}"
    elif scenario_id == 2:
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Có chẩn đoán bệnh xác định là '{disease_name}' (ICD-10: {icd_code}) nhưng KHÔNG kê đơn thuốc (bệnh nhân được chỉ định phẫu thuật, can thiệp ngoại khoa hoặc thay đổi lối sống). Mô tả chi tiết kết quả cận lâm sàng khẳng định chẩn đoán.\nEntities: Bắt buộc trích xuất '{disease_name}' nhãn CHẨN_ĐOÁN, kèm 'TRIỆU_CHỨNG', 'TÊN_XÉT_NGHIỆM', 'KẾT_QUẢ_XÉT_NGHIỆM'. TUYỆT ĐỐI không trích xuất 'THUỐC'.\n{assertion_hint}"
    elif scenario_id == 3:
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Chẩn đoán bệnh xác định là '{disease_name}' (ICD-10: {icd_code}) kèm đơn thuốc điều trị nội khoa hợp lý chọn từ danh mục thuốc gợi ý dưới đây.\nDANH MỤC THUỐC GỢI Ý (chỉ sử dụng các thuốc trong danh sách này): {', '.join(specific_drugs)}.\nEntities: Trích xuất '{disease_name}' nhãn CHẨN_ĐOÁN, và 1-3 thuốc chỉ định nhãn THUỐC (đối chiếu chính xác danh mục trên), kèm triệu chứng và xét nghiệm cận lâm sàng.\n{assertion_hint}"
    else: # scenario_id == 4
        hist_drug = specific_drugs[0] if specific_drugs else "Aspirin"
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Ghi nhận tiền sử hoặc bệnh nền của bệnh nhân. Bệnh nhân có tiền sử điều trị bệnh '{disease_name}' (ICD-10: {icd_code}) và có dùng thuốc dài hạn là '{hist_drug}'.\nEntities: Trích xuất '{disease_name}' nhãn CHẨN_ĐOÁN với assertions=['isHistorical'], và trích xuất '{hist_drug}' nhãn THUỐC với assertions=['isHistorical'].\n{assertion_hint}"

    # 3. Prompt style
    if style_id == 1:
        style = f"PHONG CÁCH YÊU CẦU: Bệnh án lâm sàng bán cấu trúc (Case Report) chi tiết.\n1. {s1}\n2. {s2}\n3. {s3}"
    elif style_id == 2:
        style = "PHONG CÁCH YÊU CẦU: Diễn đàn Q&A y khoa (Hỏi & Trả lời tư vấn chuyên sâu).\nHỏi : [Nội dung câu hỏi dài của người bệnh mô tả đầy đủ triệu chứng, tiền sử]\nTrả lời : Chào bạn, [Nội dung tư vấn chi tiết từ bác sĩ giải thích cặn kẽ]"
    elif style_id == 3:
        style = f"PHONG CÁCH YÊU CẦU: Bài viết thông tin y khoa giáo dục sức khỏe (Medical Article).\n[{disease_name.upper()}] LÀ GÌ?\n1. Khái niệm và nguyên nhân gây bệnh\n2. Triệu chứng lâm sàng, xét nghiệm chẩn đoán và hướng điều trị tây y"
    elif style_id == 4:
        style = f"PHONG CÁCH YÊU CẦU: Ghi chú lâm sàng tự do (Free-form Clinical Notes), bao gồm kết quả xét nghiệm, hình ảnh, diễn biến."
    else:
        style = f"PHONG CÁCH YÊU CẦU: Văn bản y khoa hỗn hợp (Hybrid Document), ghép nối ghi chú bệnh án cấu trúc với phần tư vấn bác sĩ."

    # 4. Length hint
    length_hint = """⚠️ BẮT BUỘC VỀ ĐỘ DÀI VĂN BẢN (STRICT LENGTH REQUIREMENT):
- Trường 'text' BẮT BUỘC đạt độ dài từ 600 đến 900 từ (Tuyệt đối không ngắn hơn 550 từ).
- Phải viết cực kỳ chi tiết và kéo dài văn bản: mô tả tỉ mỉ từ diễn biến bệnh lý, tiền sử bản thân & gia đình đầy đủ, kết quả khám chi tiết từng cơ quan, các bảng chỉ số xét nghiệm cận lâm sàng (nếu có trong kịch bản)."""

    # 5. Typo and drug masking hints
    mask_drug_hint = "\nMÔ PHỎNG ẨN DANH HÓA THUỐC: Ngẫu nhiên che 1-2 tên thuốc bằng dấu sao (************). Thuốc bị che KHÔNG trích xuất." if (random.random() < 0.20 and scenario_id in [3, 4]) else ""
    typo_hint = "\nBƠM NHIỄU LỖI GÕ: Tạo 1-2 lỗi gõ (dính chữ, lỗi dấu). Cụm trích xuất phải khớp chính xác text chứa lỗi." if random.random() < 0.20 else ""

    prompt = f"""Bạn là chuyên gia y khoa sinh dữ liệu huấn luyện NER (Named Entity Recognition) tiếng Việt.

{ctx}

{length_hint}

{style}

{prompt_scenario}
{mask_drug_hint}
{typo_hint}

BỆNH LÝ MỤC TIÊU: {disease_name} (ICD-10: {icd_code})
GỢI Ý LÂM SÀNG: {disease_hint}

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

🚨 LƯU Ý QUAN TRỌNG VỀ NHÃN (ENTITIES):
1. Trường 'type' của thực thể CHỈ ĐƯỢC PHÉP chứa 1 trong 5 giá trị: 'CHẨN_ĐOÁN', 'THUỐC', 'TRIỆU_CHỨNG', 'TÊN_XÉT_NGHIỆM', 'KẾT_QUẢ_XÉT_NGHIỆM'.
2. TUYỆT ĐỐI không tự tạo nhãn mới.
3. Các thuộc tính như 'isNegated', 'isHistorical', 'isFamily' PHẢI đặt trong danh sách 'assertions', TUYỆT ĐỐI không đặt vào trường 'type'.
4. Trích xuất tối đa 6-10 thực thể tiêu biểu nhất xuất hiện trong văn bản.
5. Khi trích xuất, KHÔNG che giấu tên thuốc. Ghi rõ tên hoạt chất/biệt dược.
"""
    return prompt

def generate_call_gemini(api_key, prompt, model_name=None):
    """Gọi API Google AI Studio (Gemini/Gemma) với xoay vòng Model"""
    if not model_name:
        model_name = key_manager.get_next_gemini_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7,
            "maxOutputTokens": 4096
        }
    }
    if "gemma" in model_name.lower():
        payload["systemInstruction"] = {
            "parts": [{"text": "You are a specialized medical JSON generator. You MUST output ONLY valid JSON. Absolutely NO reasoning text, NO bullet points, NO intro text, NO markdown codeblocks."}]
        }
    timeout_val = 90 if "gemma" in model_name.lower() else 60
    res = requests.post(url, headers=headers, json=payload, timeout=timeout_val)
    return res, model_name

def generate_call_groq(api_key, prompt, model_name=None):
    """Gọi API Groq Cloud"""
    if not model_name:
        m_info = key_manager.get_next_model("groq")
        model_name = m_info["id"] if m_info else "llama-3.3-70b-versatile"
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a helpful medical data generator. Always output raw JSON only."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.8,
        "max_tokens": 4096
    }
    res = requests.post(url, headers=headers, json=payload, timeout=60)
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
    res = requests.post(url, headers=headers, json=payload, timeout=60)
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
    res = requests.post(url, headers=headers, json=payload, timeout=60)
    return res, model_name

global_provider_toggle = "groq"

def generate_with_smart_rotation(provider, prompt, target_model=None, max_attempts=15):
    """Cơ chế xoay vòng Key thông minh (Gemini / Groq / 9router) hỗ trợ ép Model cố định (Model Isolation)"""
    global global_provider_toggle
    
    for attempt in range(max_attempts):
        available_providers = []
        if provider == "auto":
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
            next_idx = (available_providers.index(current_provider) + 1) % len(available_providers)
            global_provider_toggle = available_providers[next_idx]
        else:
            current_provider = provider
            available_providers = [provider]

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
            m_list = key_manager.models_by_provider.get(current_provider, [])
            delay_sec = 2.0
            if target_model:
                for m in m_list:
                    if m.get("id") == target_model:
                        delay_sec = m.get("rpm_delay_seconds", 4.0)
                        break
            elif m_list:
                delay_sec = m_list[0].get("rpm_delay_seconds", 4.0)
                
            time.sleep(random.uniform(delay_sec * 0.8, delay_sec * 1.2))
            
            if current_provider == "gemini":
                res, used_model = generate_call_gemini(api_key, prompt, model_name=target_model)
            elif current_provider == "groq":
                res, used_model = generate_call_groq(api_key, prompt, model_name=target_model)
            elif current_provider == "sambanova":
                res, used_model = generate_call_sambanova(api_key, prompt, model_name=target_model)
            else:
                res, used_model = generate_call_ninerouter(api_key, prompt, model_name=target_model)

            print(f"  👉 [THỬ LẦN {attempt+1}] Gửi API -> Nhà cung cấp: [{current_provider.upper()} ({used_model})] | TK: [{account_id.upper()}] (Key: {api_key[:10]}...)")

            if res.status_code == 429:
                cooldown_sec = 10.0  # Tạm dừng ngắn 10s cho mọi lỗi 429, không đóng băng 8 tiếng
                print(f"  🛑 Key [{api_key[:12]}...] (TK: {account_id.upper()}) tạm nghỉ 10s...")
                key_manager.mark_rate_limited(key_info, cooldown_seconds=cooldown_sec)
                
                if "groq" in available_providers and current_provider != "groq":
                    global_provider_toggle = "groq"
                continue
                
            if res.status_code != 200:
                print(f"  ❌ Lỗi API {res.status_code} (TK: {account_id.upper()}): {res.text[:150]}")
                time.sleep(2)
                continue
                
            key_manager.mark_success(key_info)
            
            if res.text.strip().startswith("data: "):
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
                
            if not content_text:
                content_text = ""
                
            if "<think>" in content_text:
                content_text = re.sub(r'<think>.*?</think>', '', content_text, flags=re.DOTALL)

            if "gemma" in used_model.lower():
                lines = content_text.split('\n')
                clean_lines = [l for l in lines if not l.strip().startswith('*')]
                content_text = '\n'.join(clean_lines)

            match = re.search(r'\{.*\}', content_text, re.DOTALL)
            if match:
                cleaned_text = match.group(0)
            else:
                cleaned_text = content_text.strip()
                
            try:
                return json.loads(cleaned_text, strict=False), account_id, current_provider, used_model
            except json.JSONDecodeError:
                sanitized = re.sub(r'[\r\n\t]', ' ', cleaned_text)
                return json.loads(sanitized, strict=False), account_id, current_provider, used_model

        except requests.exceptions.Timeout:
            print(f"  ⚠️ [THỬ LẠI] Mạng nghẽn Timeout 60s với TK {account_id.upper()} (lần {attempt+1}) -> Đang tự động đổi sang Key/Model khác...")
            time.sleep(1)
        except json.JSONDecodeError:
            print(f"  ⚠️ [THỬ LẠI] Server trả về nội dung rỗng/lỗi JSON với TK {account_id.upper()} (lần {attempt+1}) -> Đang tự động đổi sang Key/Model khác...")
            time.sleep(1)
        except Exception as e:
            print(f"  ⚠️ [THỬ LẠI] Lỗi tạm thời ({type(e).__name__}: {e}) với TK {account_id.upper()} (lần {attempt+1}) -> Đang đổi Key...")
            time.sleep(1)
            
    return None, None, None, None

def process_and_align(generated_data):
    """Tính toán position, chuẩn hóa nhãn thực thể và tra cứu mã candidates offline qua Smart ICD-10 Mapper"""
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
            etype = "TRIỆU_CHỨNG"
            
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

def record_sample_stats(member, file_idx, provider, account, model=None):
    """Cập nhật trực tiếp file stats.json tổng hợp của member"""
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
            "by_model": {},
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

        if model:
            bm = stats_data.get("by_model", {})
            model_up = model.upper()
            bm[model_up] = bm.get(model_up, 0) + 1
            stats_data["by_model"] = bm
        
        stats_data["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return stats_data

def main():
    parser = argparse.ArgumentParser(description="Script sinh dữ liệu huấn luyện y khoa V3 Nâng Cấp V6.0 (Bias Reduction & Matrix Balancing)")
    parser.add_argument("--member", type=str, required=True, help="Mã thành viên/Tên thư mục (Ví dụ: Long, A, B, C)")
    parser.add_argument("--provider", type=str, default="auto", choices=["auto", "gemini", "groq", "sambanova", "ninerouter"], help="Nhà cung cấp AI (auto: đan xen liên tục các provider)")
    parser.add_argument("--model", type=str, default=None, help="Ép sử dụng một AI Model cố định (Model Isolation Architecture)")
    parser.add_argument("--num_samples", type=int, default=2000, help="Số lượng mẫu cần sinh")
    parser.add_argument("--start_idx", type=int, default=None, help="Chỉ số bắt đầu (chạy song song)")
    parser.add_argument("--end_idx", type=int, default=None, help="Chỉ số kết thúc (chạy song song)")
    args = parser.parse_args()
    
    print(f"--- KHỞI ĐỘNG TIẾN TRÌNH SINH DỮ LIỆU V3 V6.0 ---")
    print(f" * Thành viên / Thư mục: sample_{args.member}")
    print(f" * Nhà cung cấp AI: {args.provider.upper()}")
    print(f" * Tích hợp: Smart ICD-10 Mapper + Matrix Balancer + Rare Diseases (5%)")
    
    drugs_list = load_drugs_list()
    all_codes, common_codes = load_icd10_partition(args.member)
    
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
        
        # Chọn bệnh theo trọng số dịch tễ học & bệnh hiếm V6.0
        disease_entry = select_disease_weighted()
        
        prompt = build_prompt_text(scenario_id, style_id, disease_entry, drugs_list)
        
        raw_sample, used_acc, used_provider, used_model = generate_with_smart_rotation(args.provider, prompt, target_model=args.model)
        
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
        
        stats_data = record_sample_stats(args.member, current_file_idx, p_name, acc_name, used_model)
        cumul_provider = stats_data.get("by_provider", {})
        
        session_summary = " | ".join([f"{k}: {v}" for k, v in sorted(provider_counts_session.items())])
        cumul_summary = " | ".join([f"{k}: {v}" for k, v in sorted(cumul_provider.items())])
        
        sleep_sec = random.uniform(5.0, 8.0)
        print(f" ->  Thành công mẫu #{current_file_idx} [{p_name} - TK: {acc_name}]")
        print(f"     📊 Đợt này: [{session_summary}] | 🏆 Lũy kế stats.json (sample_{args.member}): [{cumul_summary}] (Nghỉ {sleep_sec:.1f}s)...")
        
        time.sleep(sleep_sec)

    print(f"\n=== HOÀN TẤT TIẾN TRÌNH V3 V6.0 (Thành viên: {args.member}) ===")
    print(f" - Tổng đã hoàn thành trong dải: {already_done + success_count}/{total_in_range}")

if __name__ == "__main__":
    main()

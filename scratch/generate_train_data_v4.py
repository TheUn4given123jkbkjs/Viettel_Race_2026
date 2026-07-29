"""
═══════════════════════════════════════════════════════════════
  GENERATE_TRAIN_DATA_V4.py — Sinh dữ liệu y khoa có cân bằng
  Tương thích 100% với setup Long (key_manager, multi-provider)
  Tích hợp: Matrix Balancer + Smart ICD-10 Mapper + Rare Disease
═══════════════════════════════════════════════════════════════
"""
import os, sys, sqlite3, requests, json, re, time, random, argparse, threading
from pathlib import Path

if sys.stdout.encoding != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(BASE_DIR) == "Long_folder":
    BASE_DIR = os.path.dirname(BASE_DIR)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(BASE_DIR, "scratch"))

# Import Smart ICD-10 Mapper (thay thế hoàn toàn FTS cũ)
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

# ══════════════════════════════════════════════════════════
#  SECTION TITLES & PROMPT TEMPLATE
# ══════════════════════════════════════════════════════════

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

def build_prompt_v4(scenario_id, style_id, disease_entry, drugs_list):
    """
    Xây dựng prompt V4 kết hợp:
    1. Ưu điểm V3 của Long (scenario_id, style_id, assertion_hint, typo_hint, mask_drug_hint).
    2. Logic V4 của chúng ta (Cân bằng Ma trận, Bệnh mục tiêu, Ràng buộc thuốc).
    """
    s1, s2, s3 = random.choice(SEC1), random.choice(SEC2), random.choice(SEC3)
    ctx = random.choice(CONTEXTS)
    
    icd_code = disease_entry[1]
    disease_name = disease_entry[2]
    disease_hint = disease_entry[3]
    
    # 1. Assertion hints (phủ định, tiền sử, gia đình)
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
        prompt_scenario = f"KỊCH BẢN LÂM SÀNG: Chẩn đoán bệnh xác định là '{disease_name}' (ICD-10: {icd_code}) kèm đơn thuốc điều trị nội khoa hợp lý chọn từ danh mục thuốc gợi ý dưới đây.\nDANH MỤC THUỐC GỢI Ý (chỉ sử dụng các thuốc trong danh sách này): {', '.join(drugs_list)}.\nEntities: Trích xuất '{disease_name}' nhãn CHẨN_ĐOÁN, và 1-3 thuốc chỉ định nhãn THUỐC (đối chiếu chính xác danh mục trên), kèm triệu chứng và xét nghiệm cận lâm sàng.\n{assertion_hint}"
    else: # scenario_id == 4
        hist_drug = drugs_list[0] if drugs_list else "Aspirin"
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
        style = f"PHONG CÁCH YÊU CẦU: Bệnh án lâm sàng bán cấu trúc (Case Report) chi tiết.\n1. {s1}\n2. {s2}\n3. {s3}"

    # 4. Length hint
    length_hint = """⚠️ BẮT BUỘC VỀ ĐỘ DÀI VĂN BẢN (STRICT LENGTH REQUIREMENT):
- Trường 'text' BẮT BUỘC đạt độ dài từ 600 đến 900 từ (Tuyệt đối không ngắn hơn 550 từ).
- Phải viết cực kỳ chi tiết và kéo dài văn bản: mô tả tỉ mỉ từ diễn biến bệnh lý, tiền sử bản thân & gia dịch đầy đủ, kết quả khám chi tiết từng cơ quan, các bảng chỉ số xét nghiệm cận lâm sàng (nếu có trong kịch bản)."""

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

def select_disease_weighted():
    """Chọn ngẫu nhiên một bệnh theo phân bổ trọng số."""
    weights = [d[0] for d in DISEASE_DISTRIBUTION]
    return random.choices(DISEASE_DISTRIBUTION, weights=weights, k=1)[0]


def query_local_db_v4(entity_text, entity_type, db_path=None):
    """Tra cứu mã ICD-10 (smart) hoặc RxNorm từ SQLite."""
    if db_path is None:
        db_path = os.path.join(BASE_DIR, "db", "medical_codes.db")
    if not os.path.exists(db_path):
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    candidates = []
    
    try:
        if entity_type == "CHẨN_ĐOÁN":
            # Sử dụng Smart ICD-10 Mapper thay vì FTS cũ
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

# ══════════════════════════════════════════════════════════
#  COMPACT JSON FORMAT
# ══════════════════════════════════════════════════════════

def compact_json_format(data):
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    json_str = re.sub(r'\[\s*\n\s*(\d+),\s*\n\s*(\d+)\s*\n\s*\]', r'[\1, \2]', json_str)
    json_str = re.sub(r'\[\s*\n\s*\]', r'[]', json_str)
    json_str = re.sub(r'\[\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1"]', json_str)
    json_str = re.sub(r'\[\s*\n\s*"([^"]+)",\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1", "\2"]', json_str)
    return json_str

# ══════════════════════════════════════════════════════════
#  PROCESS & ALIGN (sử dụng Smart ICD-10 Mapper)
# ══════════════════════════════════════════════════════════

def process_and_align(generated_data):
    """Tính toán position, chuẩn hóa nhãn và tra cứu mã candidates offline."""
    if not generated_data or not isinstance(generated_data, dict):
        return []
    clinical_text = generated_data.get("text", "")
    if not isinstance(clinical_text, str):
        clinical_text = ""
    entities = generated_data.get("entities", [])
    if not isinstance(entities, list):
        entities = []
    aligned = []
    
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
        
        # Fix assertion-as-type bug
        if etype in ["isNegated", "isHistorical", "isFamily"]:
            if etype not in assertions:
                assertions.append(etype)
            etype = "TRIỆU_CHỨNG"
        
        # Normalize type
        eu = etype.upper().replace(" ", "_")
        if eu in ["CHẨN_ĐOÁN","CHAN_DOAN","BỆNH","BENH","BỆNH_LÝ","BENH_LY","TÊN_BỆNH","TEN_BENH"]:
            etype = "CHẨN_ĐOÁN"
        elif eu in ["THUỐC","THUOC","TÊN_THUỐC","TEN_THUOC","DƯỢC_PHẨM"]:
            etype = "THUỐC"
        elif eu in ["TRIỆU_CHỨNG","TRIEU_CHUNG","LÂM_SÀNG"]:
            etype = "TRIỆU_CHỨNG"
        elif eu in ["TÊN_XÉT_NGHIỆM","TEN_XET_NGHIEM","XÉT_NGHIỆM","XET_NGHIEM"]:
            etype = "TÊN_XÉT_NGHIỆM"
        elif eu in ["KẾT_QUẢ_XÉT_NGHIỆM","KET_QUA_XET_NGHIEM","KẾT_QUẢ","KET_QUA"]:
            etype = "KẾT_QUẢ_XÉT_NGHIỆM"
        else:
            if "bệnh" in text.lower() or "viêm" in text.lower():
                etype = "CHẨN_ĐOÁN"
            elif "sốt" in text.lower() or "đau" in text.lower() or "mệt" in text.lower():
                etype = "TRIỆU_CHỨNG"
            else:
                etype = "TRIỆU_CHỨNG"
        
        clean_assertions = []
        for a in assertions:
            a_str = str(a).strip()
            if a_str in ["isNegated","isHistorical","isFamily"] and a_str not in clean_assertions:
                clean_assertions.append(a_str)
        
        candidates = []
        if etype in ["CHẨN_ĐOÁN", "THUỐC"]:
            candidates = query_local_db_v4(text, etype)
        
        aligned.append({
            "text": text,
            "position": position,
            "type": etype,
            "assertions": clean_assertions,
            "candidates": candidates
        })
    
    return aligned

# ══════════════════════════════════════════════════════════
#  API CALL FUNCTIONS (giống setup Long — multi-provider)
# ══════════════════════════════════════════════════════════

def generate_call_gemini(api_key, prompt, model_name=None):
    models_to_try = [model_name] if model_name else ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-2.0-flash-lite"]
    
    last_res = None
    last_model = None
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.85}
        }
        try:
            res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=60)
            if res.status_code == 200:
                return res, model
            last_res = res
            last_model = model
            if res.status_code == 429:
                print(f"  ⚠️ Model {model} trả về 429 (Hết Quota/Rate Limit). Thử chuyển sang model tiếp theo...")
                continue
            elif res.status_code == 404:
                print(f"  ⚠️ Model {model} không tồn tại (404). Thử chuyển sang model tiếp theo...")
                continue
        except Exception as e:
            print(f"  ⚠️ Lỗi khi gọi model {model}: {e}")
            
    return last_res, last_model

def generate_call_groq(api_key, prompt, model_name=None):
    if not model_name:
        model_name = "llama-3.3-70b-versatile"
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a medical data generator. Output raw JSON only."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.85
    }
    res = requests.post(url, headers=headers, json=payload, timeout=30)
    return res, model_name

# ══════════════════════════════════════════════════════════
#  SMART KEY ROTATION (tương thích key_manager nếu có)
# ══════════════════════════════════════════════════════════

_key_manager_available = False
try:
    from key_manager import key_manager
    _key_manager_available = True
except ImportError:
    pass

def generate_with_rotation(provider, prompt, api_key=None, max_attempts=10):
    """Xoay vòng Key thông minh, fallback nếu không có key_manager."""
    for attempt in range(max_attempts):
        try:
            if _key_manager_available:
                key_res = key_manager.get_next_key(provider)
                if not key_res:
                    time.sleep(3)
                    continue
                api_key_use, account_id, key_info = key_res
            else:
                api_key_use = api_key
                account_id = "default"
                key_info = None
            
            time.sleep(random.uniform(3.0, 6.0))
            
            if provider == "gemini":
                res, model = generate_call_gemini(api_key_use, prompt)
            elif provider == "groq":
                res, model = generate_call_groq(api_key_use, prompt)
            else:
                res, model = generate_call_gemini(api_key_use, prompt)
            
            if res.status_code != 200:
                if res.status_code == 429:
                    sleep_time = random.uniform(35.0, 65.0)
                    print(f"  ⚠️ HTTP 429 (Rate Limit / Quota Exceeded). Tạm dừng {sleep_time:.1f} giây để reset RPM...")
                    time.sleep(sleep_time)
                else:
                    print(f"  ⚠️ HTTP {res.status_code} khi gọi API. Chờ 5s...")
                    time.sleep(5)
                if _key_manager_available and key_info:
                    key_manager.mark_failure(key_info, res.status_code)
                continue
            
            if _key_manager_available and key_info:
                key_manager.mark_success(key_info)
            
            # Parse response
            if provider == "gemini":
                res_data = res.json()
                content_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                res_data = res.json()
                content_text = res_data["choices"][0]["message"]["content"]
            
            match = re.search(r'\{.*\}', content_text, re.DOTALL)
            if match:
                return json.loads(match.group(0)), account_id, provider
                
        except requests.exceptions.Timeout:
            print("  ⚠️ API Request Timeout. Chờ 5s...")
            time.sleep(5)
        except json.JSONDecodeError:
            print("  ⚠️ Lỗi parse JSON từ phản hồi API. Chờ 3s...")
            time.sleep(3)
        except Exception as e:
            print(f"  ⚠️ Lỗi kết nối: {type(e).__name__}: {e} (lần {attempt+1})")
            time.sleep(5)
    
    return None, None, None

# ══════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════

stats_lock = threading.Lock()

def record_stats(member, file_idx, provider, account):
    member_dir = os.path.join(BASE_DIR, f"sample_{member}")
    stats_file = os.path.join(member_dir, "stats.json")
    os.makedirs(member_dir, exist_ok=True)
    
    with stats_lock:
        stats = {"member": member, "total": 0, "by_provider": {}, "by_account": {}}
        if os.path.exists(stats_file):
            try:
                with open(stats_file, "r", encoding="utf-8") as f:
                    stats = json.load(f)
            except: pass
        
        stats["total"] = stats.get("total", 0) + 1
        bp = stats.get("by_provider", {})
        bp[provider] = bp.get(provider, 0) + 1
        stats["by_provider"] = bp
        ba = stats.get("by_account", {})
        ba[account] = ba.get(account, 0) + 1
        stats["by_account"] = ba
        stats["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    return stats

def main():
    parser = argparse.ArgumentParser(description="Script sinh dữ liệu V4 — Cân bằng Ma trận Bệnh-Thuốc")
    parser.add_argument("--member", type=str, required=True, help="Mã thành viên (VD: Long, A, C)")
    parser.add_argument("--provider", type=str, default="gemini", choices=["gemini", "groq", "auto"])
    parser.add_argument("--api_key", type=str, default=None, help="API key (nếu không dùng key_manager)")
    parser.add_argument("--num_samples", type=int, default=2000)
    parser.add_argument("--start_idx", type=int, default=None)
    parser.add_argument("--end_idx", type=int, default=None)
    args = parser.parse_args()
    
    print("═" * 60)
    print("  GENERATE TRAIN DATA V4 — MATRIX BALANCED")
    print("═" * 60)
    print(f"  Provider: {args.provider.upper()}")
    print(f"  Output: sample_{args.member}")
    print(f"  Số bệnh trong ma trận: {len(DISEASE_DISTRIBUTION)}")
    print(f"  Số cặp bệnh-thuốc: {len(CLINICAL_DRUG_MATRIX)}")
    print(f"  Bao gồm bệnh hiếm: {sum(1 for d in DISEASE_DISTRIBUTION if d[0] <= 0.005)} loại")
    
    if not _key_manager_available and not args.api_key:
        env_key = os.environ.get("GEMINI_API_KEY")
        if env_key:
            args.api_key = env_key
        else:
            env_path = os.path.join(BASE_DIR, ".env")
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    for line in f:
                        if line.startswith("GEMINI_API_KEY"):
                            args.api_key = line.strip().split("=",1)[1].strip()
            if not args.api_key:
                print("Lỗi: Cần API key (--api_key hoặc .env)")
                sys.exit(1)
    
    input_dir = os.path.join(BASE_DIR, f"sample_{args.member}", "input")
    output_dir = os.path.join(BASE_DIR, f"sample_{args.member}", "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    if args.start_idx is not None and args.end_idx is not None:
        range_start, range_end = args.start_idx, args.end_idx
    else:
        range_start, range_end = 1, args.num_samples
    
    # Check existing
    indices_to_generate = []
    already_done = 0
    for idx in range(range_start, range_end + 1):
        part = (idx - 1) // 500 + 1
        txt_path = os.path.join(input_dir, f"part_{part}", f"{idx}.txt")
        if os.path.exists(txt_path):
            already_done += 1
        else:
            indices_to_generate.append(idx)
    
    total = range_end - range_start + 1
    remaining = len(indices_to_generate)
    
    print(f"\n  [CHECKPOINT] Đã có: {already_done}/{total}. Cần sinh: {remaining}")
    
    if remaining == 0:
        print(f"\n  ✅ Đã hoàn tất {total} mẫu.")
        sys.exit(0)
    
    # Disease distribution tracking
    disease_counts = {}
    success = 0
    ptr = 0
    
    while ptr < len(indices_to_generate):
        idx = indices_to_generate[ptr]
        done_total = already_done + success
        
        # Chọn bệnh theo ma trận
        disease = select_disease_weighted()
        icd = disease[1]
        disease_counts[icd] = disease_counts.get(icd, 0) + 1
        
        # Lấy thuốc ràng buộc
        # Chọn scenario & style
        scenario_id = random.choices([1, 2, 3, 4], weights=[0.20, 0.25, 0.40, 0.15])[0]
        style_id = random.choices([1, 2, 3, 4, 5], weights=[0.25, 0.15, 0.15, 0.15, 0.30])[0]
        
        # Lấy danh sách thuốc ràng buộc cho bệnh
        raw_drugs = CLINICAL_DRUG_MATRIX.get(icd, [])
        if not raw_drugs:
            raw_drugs = ["Paracetamol", "Amoxicillin", "Omeprazole"]
            
        if scenario_id == 3:
            k = min(random.randint(3, 5), len(raw_drugs))
            drugs_list = random.sample(raw_drugs, k)
        elif scenario_id == 4:
            drugs_list = [random.choice(raw_drugs)]
        else:
            drugs_list = []
            
        # Build prompt
        prompt = build_prompt_v4(scenario_id, style_id, disease, drugs_list)
        
        print(f"  [{done_total+1}/{total}] Sinh mẫu #{idx} | {disease[2]} ({icd})")
        
        # Generate
        raw, account, provider = generate_with_rotation(args.provider, prompt, args.api_key)
        
        if not raw:
            print(f"    ❌ Thất bại sau nhiều lần. Tạm nghỉ 10s...")
            time.sleep(10)
            continue
        
        # Align
        entities = process_and_align(raw)
        text_content = raw.get("text", "")
        if not isinstance(text_content, str) or not text_content.strip():
            print(f"    ⚠️ Text rỗng, bỏ qua.")
            continue
        
        # Save
        part = (idx - 1) // 500 + 1
        part_in = os.path.join(input_dir, f"part_{part}")
        part_out = os.path.join(output_dir, f"part_{part}")
        os.makedirs(part_in, exist_ok=True)
        os.makedirs(part_out, exist_ok=True)
        
        with open(os.path.join(part_in, f"{idx}.txt"), "w", encoding="utf-8") as f:
            f.write(text_content.strip())
        
        with open(os.path.join(part_out, f"{idx}.json"), "w", encoding="utf-8") as f:
            f.write(compact_json_format(entities))
        
        success += 1
        ptr += 1
        
        p_name = (provider or "UNKNOWN").upper()
        a_name = (account or "UNKNOWN").upper()
        record_stats(args.member, idx, p_name, a_name)
        
        sleep_sec = random.uniform(5.0, 9.0)
        print(f"    ✅ #{idx} [{p_name}/{a_name}] entities={len(entities)} (nghỉ {sleep_sec:.1f}s)")
        time.sleep(sleep_sec)
    
    print(f"\n{'═' * 60}")
    print(f"  HOÀN TẤT V4 (member={args.member})")
    print(f"  Tổng: {already_done + success}/{total}")
    print(f"\n  Phân bổ bệnh đã sinh:")
    for icd, cnt in sorted(disease_counts.items(), key=lambda x: -x[1])[:15]:
        name = next((d[2] for d in DISEASE_DISTRIBUTION if d[1] == icd), icd)
        print(f"    {icd:8s} {name:35s} {cnt:4d} mẫu")

if __name__ == "__main__":
    main()

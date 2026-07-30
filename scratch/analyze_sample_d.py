import os
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_D_DIR = BASE_DIR / "sample_D"
DB_PATH = BASE_DIR / "db" / "medical_codes.db"

# List of critical incorrect codes from V6.0 log
BAD_CODES = {
    "Y06", "Y06.2", "A50.04", "A54.84", "B06.81", "A52.06",
    "Z35.0", "Z35.1", "Z35.3", "Z35.4",
    "O04.0", "O03.0", "O03.5",
    "E12.9", "E13", "E13.0"
}

def classify_style(text):
    has_case_report = bool(re.search(r'(Tiền sử bệnh|Bệnh sử hiện tại|Đánh giá tại bệnh viện|Lý do nhập viện|Triệu chứng hiện tại|Triệu chứng khi nhập viện)', text))
    has_qa = bool(re.search(r'(Hỏi\s*:|Trả lời\s*:|Câu hỏi từ người dùng|Câu trả lời của bác sĩ|Chào bác sĩ|Chào bạn)', text))
    has_article = bool(re.search(r'(LÀ GÌ\??|Định nghĩa khái niệm|Dấu hiệu và triệu chứng|Cách điều trị|là bệnh gì|là tình trạng|được đặc trưng bởi)', text, re.IGNORECASE))
    
    styles = []
    if has_case_report:
        styles.append("Case Report")
    if has_qa:
        styles.append("Q&A")
    if has_article:
        styles.append("Article")
    
    if len(styles) >= 2:
        return "Hybrid"
    elif len(styles) == 1:
        return styles[0]
    else:
        return "Other"

def main():
    if not SAMPLE_D_DIR.exists():
        print(f"Error: {SAMPLE_D_DIR} does not exist.")
        sys.exit(1)
        
    input_dir = SAMPLE_D_DIR / "input"
    output_dir = SAMPLE_D_DIR / "output"
    
    txt_files = sorted(list(input_dir.rglob("*.txt")))
    json_files = sorted(list(output_dir.rglob("*.json")))
    
    print("=" * 80)
    print("  PHÂN TÍCH THỐNG KÊ CHI TIẾT TẬP DỮ LIỆU: SAMPLE D")
    print("=" * 80)
    print(f"Tổng số tệp văn bản (.txt): {len(txt_files)}")
    print(f"Tổng số tệp kết quả (.json): {len(json_files)}")
    
    if len(txt_files) == 0:
        print("Không có tệp dữ liệu để phân tích.")
        return

    # Lookups
    json_lookup = {f.stem: f for f in json_files}
    
    lengths = []
    styles = Counter()
    total_entities = 0
    entity_types = Counter()
    assertion_counts = Counter()
    
    icd_counts = Counter()
    rxnorm_counts = Counter()
    
    missing_icd_candidates = []
    missing_rx_candidates = []
    bad_code_samples = []
    
    for txt_f in txt_files:
        stem = txt_f.stem
        # Read text
        try:
            text = txt_f.read_text(encoding="utf-8")
        except:
            text = txt_f.read_text(encoding="utf-8-sig", errors="replace")
            
        lengths.append(len(text.split())) # word count
        styles[classify_style(text)] += 1
        
        json_f = json_lookup.get(stem)
        if not json_f or not json_f.exists():
            continue
            
        try:
            entities = json.loads(json_f.read_text(encoding="utf-8"))
        except:
            entities = json.loads(json_f.read_text(encoding="utf-8-sig", errors="replace"))
            
        for ent in entities:
            total_entities += 1
            etype = ent.get("type", "")
            entity_types[etype] += 1
            
            assertions = ent.get("assertions", [])
            for ass in assertions:
                assertion_counts[ass] += 1
                
            candidates = ent.get("candidates", [])
            ent_text = ent.get("text", "")
            
            if etype == "CHẨN_ĐOÁN":
                if not candidates:
                    missing_icd_candidates.append((stem, ent_text))
                else:
                    for c in candidates:
                        icd_counts[c] += 1
                        if c in BAD_CODES:
                            bad_code_samples.append((stem, ent_text, c))
            elif etype == "THUỐC":
                if not candidates:
                    missing_rx_candidates.append((stem, ent_text))
                else:
                    for c in candidates:
                        rxnorm_counts[c] += 1
                        if c in BAD_CODES:
                            bad_code_samples.append((stem, ent_text, c))

    print("\n--- THỐNG KÊ ĐỘ DÀI VĂN BẢN (Số lượng từ) ---")
    print(f"Độ dài trung bình: {sum(lengths) / len(lengths):.1f} từ")
    print(f"Độ dài lớn nhất:   {max(lengths)} từ")
    print(f"Độ dài nhỏ nhất:   {min(lengths)} từ")
    print(f"Số mẫu có độ dài ngắn (< 450 từ): {sum(1 for l in lengths if l < 450)}")
    
    print("\n--- PHÂN BỔ PHONG CÁCH VĂN BẢN ---")
    for s, c in styles.most_common():
        print(f"  * {s:15s}: {c:4d} mẫu ({c / len(txt_files) * 100:.1f}%)")
        
    print("\n--- PHÂN BỔ CÁC THỰC THỂ (ENTITIES) ---")
    print(f"Tổng số thực thể trích xuất: {total_entities}")
    print(f"Trung bình thực thể / mẫu:   {total_entities / len(txt_files):.1f}")
    for t, c in entity_types.most_common():
        print(f"  * {t:22s}: {c:4d} thực thể ({c / total_entities * 100:.1f}%)")
        
    print("\n--- THỐNG KÊ THUỘC TÍNH (ASSERTIONS) ---")
    for a, c in assertion_counts.most_common():
        print(f"  * {a:15s}: {c:4d} lần xuất hiện")
        
    print("\n--- TOP 15 MÃ ICD-10 XUẤT HIỆN NHIỀU NHẤT ---")
    for code, c in icd_counts.most_common(15):
        print(f"  * {code:8s}: {c:4d} lần")
        
    print("\n--- TOP 15 MÃ RXNORM XUẤT HIỆN NHIỀU NHẤT ---")
    for code, c in rxnorm_counts.most_common(15):
        print(f"  * {code:8s}: {c:4d} lần")

    print("\n--- PHÂN TÍCH LỖI VÀ CHẤT LƯỢNG ÁNH XẠ ---")
    print(f"Số lượng thực thể CHẨN_ĐOÁN thiếu candidates: {len(missing_icd_candidates)}")
    if missing_icd_candidates:
        print("  Ví dụ mẫu thiếu:")
        for stem, text in missing_icd_candidates[:10]:
            print(f"    - File {stem}.json: '{text}'")
            
    print(f"Số lượng thực thể THUỐC thiếu candidates: {len(missing_rx_candidates)}")
    if missing_rx_candidates:
        print("  Ví dụ mẫu thiếu:")
        for stem, text in missing_rx_candidates[:10]:
            print(f"    - File {stem}.json: '{text}'")
            
    print(f"Số lượng thực thể ánh xạ trúng mã sai nghiêm trọng (BAD_CODES): {len(bad_code_samples)}")
    if bad_code_samples:
        print("  Danh sách lỗi trúng mã sai:")
        for stem, text, code in bad_code_samples[:15]:
            print(f"    - File {stem}.json: '{text}' -> mã lỗi '{code}'")

if __name__ == "__main__":
    main()

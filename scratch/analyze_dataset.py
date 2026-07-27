import os
import sys
import json
import sqlite3
from collections import Counter

# Đảm bảo in tiếng Việt ra console không bị lỗi encoding
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def get_icd10_chapter_name(letter):
    """Ánh xạ ký tự đầu của mã ICD-10 sang tên chương bệnh rút gọn"""
    chapters = {
        "A": "Nhiễm trùng & Ký sinh trùng (A-B)",
        "B": "Nhiễm trùng & Ký sinh trùng (A-B)",
        "C": "Khối u / Ung thư (C-D)",
        "D": "Khối u & Bệnh máu (C-D)",
        "E": "Nội tiết, Dinh dưỡng & Chuyển hóa",
        "F": "Tâm thần & Hành vi",
        "G": "Hệ thần kinh",
        "H": "Mắt & Tai",
        "I": "Hệ tuần hoàn",
        "J": "Hệ hô hấp",
        "K": "Hệ tiêu hóa",
        "L": "Da & Mô dưới da",
        "M": "Hệ cơ xương khớp & Mô liên kết",
        "N": "Hệ tiết niệu - Sinh dục",
        "O": "Thai nghén, Sinh đẻ & Hậu sản",
        "P": "Bệnh lý chu sinh (Sơ sinh)",
        "Q": "Dị tật bẩm sinh",
        "R": "Triệu chứng cận lâm sàng bất thường",
        "S": "Chấn thương & Ngộ độc (S-T)",
        "T": "Chấn thương & Ngộ độc (S-T)",
        "U": "Mã mục đích đặc biệt",
        "V": "Nguyên nhân ngoại viện (V-Y)",
        "W": "Nguyên nhân ngoại viện (V-Y)",
        "X": "Nguyên nhân ngoại viện (V-Y)",
        "Y": "Nguyên nhân ngoại viện (V-Y)",
        "Z": "Yếu tố ảnh hưởng sức khỏe"
    }
    return chapters.get(letter.upper(), "Không xác định")

def analyze_dataset(input_dir="sample/input", output_dir="sample/output"):
    if not os.path.exists(output_dir):
        print(f"Lỗi: Không tìm thấy thư mục kết quả '{output_dir}'")
        return
        
    print(f"--- Đang phân tích tập dữ liệu sinh ra tại '{output_dir}' ---")
    
    json_files = [f for f in os.listdir(output_dir) if f.endswith(".json")]
    total_samples = len(json_files)
    
    if total_samples == 0:
        print("Cảnh báo: Thư mục trống. Chưa có tệp dữ liệu nào để phân tích.")
        return
        
    # Các bộ đếm thống kê
    entity_counter = Counter()
    assertion_counter = Counter()
    
    # Thống kê mã hóa candidates
    diagnoses_total = 0
    diagnoses_mapped = 0
    drugs_total = 0
    drugs_mapped = 0
    
    # Phân phối chương bệnh ICD-10
    icd_chapters = Counter()
    
    # Top từ khóa xuất hiện
    diseases_list = []
    drugs_list = []
    
    for filename in json_files:
        json_path = os.path.join(output_dir, filename)
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                entities = json.load(f)
                
            for ent in entities:
                etype = ent.get("type", "")
                text = ent.get("text", "")
                assertions = ent.get("assertions", [])
                candidates = ent.get("candidates", [])
                
                # 1. Đếm loại thực thể
                entity_counter[etype] += 1
                
                # 2. Đếm các assertions
                for ass in assertions:
                    assertion_counter[ass] += 1
                    
                # 3. Đánh giá tỷ lệ ánh xạ mã ứng viên (candidates)
                if etype == "CHẨN_ĐOÁN":
                    diagnoses_total += 1
                    if candidates:
                        diagnoses_mapped += 1
                        diseases_list.append(f"{text} ({candidates[0]})")
                        # Lấy ký tự đầu để phân phối chương bệnh
                        first_letter = candidates[0][0].upper()
                        icd_chapters[first_letter] += 1
                    else:
                        diseases_list.append(text)
                        
                elif etype == "THUỐC":
                    drugs_total += 1
                    if candidates:
                        drugs_mapped += 1
                        drugs_list.append(f"{text} (CUI: {candidates[0]})")
                    else:
                        drugs_list.append(text)
                        
        except Exception as e:
            print(f"Lỗi đọc tệp '{filename}': {e}")
            
    # Tính toán tỷ lệ phần trăm
    total_entities = sum(entity_counter.values())
    
    # Chuẩn bị nội dung báo cáo dạng Markdown
    report_lines = []
    report_lines.append("# Báo cáo Phân tích Khám phá Dữ liệu (EDA Dataset Report)")
    report_lines.append(f"\n*   **Tổng số mẫu bệnh án đã sinh (samples):** {total_samples}")
    report_lines.append(f"*   **Tổng số thực thể trích xuất (entities):** {total_entities}")
    
    report_lines.append("\n## 📊 1. Phân bổ Loại Thực thể (Entity Type Distribution)")
    report_lines.append("| Loại thực thể | Số lượng | Tỷ lệ (%) |")
    report_lines.append("|---|---|---|")
    for etype, count in entity_counter.most_common():
        pct = (count / total_entities * 100) if total_entities > 0 else 0
        report_lines.append(f"| {etype} | {count} | {pct:.2f}% |")
        
    report_lines.append("\n## 🏷️ 2. Phân bổ Assertions (Ngữ cảnh thực thể)")
    report_lines.append("| Loại Ngữ cảnh | Số lượng | Tỷ lệ trên tổng thực thể (%) |")
    report_lines.append("|---|---|---|")
    for ass, count in assertion_counter.most_common():
        pct = (count / total_entities * 100) if total_entities > 0 else 0
        report_lines.append(f"| {ass} | {count} | {pct:.2f}% |")
        
    report_lines.append("\n## 🔍 3. Tỷ lệ Ánh xạ Mã ứng viên (Candidate Mapping Success)")
    diag_pct = (diagnoses_mapped / diagnoses_total * 100) if diagnoses_total > 0 else 0
    drug_pct = (drugs_mapped / drugs_total * 100) if drugs_total > 0 else 0
    report_lines.append(f"*   **Chẩn đoán (ICD-10) ánh xạ thành công:** {diagnoses_mapped}/{diagnoses_total} ({diag_pct:.2f}%)")
    report_lines.append(f"*   **Thuốc (RxNorm CUI) ánh xạ thành công:** {drugs_mapped}/{drugs_total} ({drug_pct:.2f}%)")
    
    report_lines.append("\n## 🗺️ 4. Phân bổ theo Chương bệnh ICD-10 (Chapter Distribution)")
    report_lines.append("| Ký tự đầu | Tên chương bệnh ICD-10 | Số lượng | Tỷ lệ (%) |")
    report_lines.append("|---|---|---|---|")
    total_mapped_icd = sum(icd_chapters.values())
    for letter, count in sorted(icd_chapters.items()):
        ch_name = get_icd10_chapter_name(letter)
        pct = (count / total_mapped_icd * 100) if total_mapped_icd > 0 else 0
        report_lines.append(f"| {letter} | {ch_name} | {count} | {pct:.2f}% |")
        
    report_lines.append("\n## 🔝 5. Top 10 Bệnh và Thuốc xuất hiện nhiều nhất")
    report_lines.append("\n### Top 10 Chẩn đoán Bệnh:")
    for item, count in Counter(diseases_list).most_common(10):
        report_lines.append(f"*   {item}: {count} lần")
        
    report_lines.append("\n### Top 10 Hoạt chất Thuốc:")
    for item, count in Counter(drugs_list).most_common(10):
        report_lines.append(f"*   {item}: {count} lần")
        
    # Xuất ra file markdown kết quả
    report_text = "\n".join(report_lines)
    report_file = os.path.join("docs", "dataset_eda.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_text)
        
    # In ra console
    print("\n" + report_text)
    print(f"\n--- ĐÃ GHI BÁO CÁO EDA THÀNH CÔNG VÀO: {report_file} ---")

if __name__ == "__main__":
    analyze_dataset()

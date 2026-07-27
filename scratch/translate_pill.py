import os
import sys
import re

# Đảm bảo console in unicode không bị lỗi
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def translate_pill():
    input_file = "pill.txt"
    if not os.path.exists(input_file):
        print(f"Lỗi: Không tìm thấy file {input_file}")
        return
        
    # Từ điển dịch nghĩa các dòng tiếng Việt và các muối/ghi chú y khoa phức tạp
    replacements = {
        "Dưới đây là danh sách tên các hoạt chất / thành phần của 493 thuốc hóa dược theo đúng thứ tự trong bảng:": "",
        "Adrenalin (tartrat hoặc hydroclorid)": "Epinephrine",
        "Amidotrizoat (natri hoặc meglumin)": "Diatrizoate",
        "Bạc sulfadiazin": "Silver sulfadiazine",
        "Benzylpenicilin (kali hoặc natri)": "Penicillin G",
        "Ciprofloxacin (base hoặc hydroclorid)": "Ciprofloxacin",
        "Cloroquin (phosphat hoặc sulfat)": "Chloroquine",
        "Cloroquin phosphal hoặc Cloroquin sulfat": "Chloroquine",
        "Cloroquin phosphat hoặc Cloroquin sulfat": "Chloroquine",
        "Cồn 70 độ": "Ethanol",
        "Cồn A.S.A": "Salicylic acid / Benzoic acid",
        "Cồn BSI": "Salicylic acid / Iodine",
        "Cồn iod": "Iodine",
        "Dung dịch lọc thận acetat": "Acetate hemodialysis solution",
        "Dung dịch thẩm phân màng bụng": "Peritoneal dialysis solution",
        "Erythromycin (stearat hoặc ethyl succinat)": "Erythromycin",
        "Insulin (tác dụng trung bình)": "NPH Insulin",
        "Isosorbid dinitrat hoặc mononitrat": "Isosorbide dinitrate",
        "Kẽm sulfat": "Zinc sulfate",
        "Magnesi hydroxyd + nhôm hydroxyd": "Magnesium hydroxide / Aluminum hydroxide",
        "Men tụy (Thành phần: lipase, protease và amylase.)": "Pancreatin",
        "Morphin hydroclorid hoặc morphin sulfat": "Morphine",
        "Muối bismuth (carbonat, trikali dicitrat...)": "Bismuth",
        "Nước cất pha tiêm": "Sterile water for injection",
        "Nước oxy già (Hydroxigen peroxide - H2O2)": "Hydrogen peroxide",
        "Oxygen dược dụng": "Oxygen",
        "Pilocarpin (hydroclorid hoặc nitrat)": "Pilocarpine",
        "Quinin sulfat hoặc Quinin bisulfat": "Quinine",
        "Sắt (sulfat hoặc oxalat)": "Iron",
        "Sắt (sulfat) + acid folic": "Iron / Folic acid",
        "Surfactant (phospholipid chiết xuất từ phổi lợn, bò có tính diện hoạt)": "Poractant alfa",
        "Testosteron enantat hoặc testosteron undecanoat": "Testosterone",
        "Than hoạt": "Activated charcoal",
        "Thiamin hydroclorid hoặc thiamin nitrat": "Thiamine",
        "Huyết thanh kháng dại": "Rabies immunoglobulin",
        "Huyết thanh kháng nọc độc": "Antivenom",
        "Huyết thanh kháng uốn ván": "Tetanus immunoglobulin",
        "Phức hợp yếu tố IX (các yếu tố đông máu II, VII, IX và X) đậm đặc": "Factor IX Complex",
        "Yếu tố VIII đậm đặc": "Factor VIII",
        "Vắc xin phối hợp phòng 3 bệnh: Sởi - Quai bị - Rubella": "Measles-Mumps-Rubella Vaccine",
        "Vắc xin phối hợp phòng 4 bệnh: Bạch hầu - Ho gà - Uốn ván - Bại liệt": "Diphtheria-Tetanus-Pertussis-Poliovirus Vaccine",
        "Vắc xin phối hợp phòng 5 Bệnh: Bạch hầu - Ho gà - Uốn ván - Viêm gan B - Hib": "Diphtheria-Tetanus-Pertussis-Hepatitis B-Haemophilus influenzae type b Vaccine",
        "Vắc xin phối hợp phòng 3 bệnh: Bạch hầu - Ho gà - Uốn ván": "Diphtheria-Tetanus-Pertussis Vaccine",
        "Vắc xin phối hợp phòng 2 bệnh: Bạch hầu - Uốn ván": "Diphtheria-Tetanus Vaccine",
        "Vắc xin phối hợp phòng 2 bệnh: Sởi - Rubella": "Measles-Rubella Vaccine",
        "Vắc xin phòng Bại liệt": "Poliovirus Vaccine",
        "Vắc xin phòng 4 bệnh: Bạch hầu - Ho gà - Uốn ván - Hib": "Diphtheria-Tetanus-Pertussis-Haemophilus influenzae type b Vaccine",
        "Vắc xin phòng bệnh do Hib": "Haemophilus influenzae type b Vaccine",
        "Vắc xin phòng bệnh viêm phổi và nhiễm khuẩn toàn thân do phế cầu Streptococcus": "Pneumococcal Vaccine",
        "Vắc xin phòng Cúm mùa": "Influenza Vaccine",
        "Vắc xin phòng Dại": "Rabies Vaccine",
        "Vắc xin phòng Lao": "BCG Vaccine",
        "Vắc xin phòng Não mô cầu": "Meningococcal Vaccine",
        "Vắc xin phòng Rubella": "Rubella Vaccine",
        "Vắc xin phòng Sởi": "Measles Vaccine",
        "Vắc xin phòng Tả": "Cholera Vaccine",
        "Vắc xin phòng Thương hàn": "Typhoid Vaccine",
        "Vắc xin phòng Thủy đậu": "Varicella Vaccine",
        "Vắc xin phòng Tiêu chảy do Rotavirus": "Rotavirus Vaccine",
        "Vắc xin phòng Ung thư cổ tử cung": "HPV Vaccine",
        "Vắc xin phòng Uốn ván": "Tetanus Vaccine",
        "Vắc xin phòng Viêm gan A": "Hepatitis A Vaccine",
        "Vắc xin phòng Viêm gan B": "Hepatitis B Vaccine",
        "Vắc xin phòng Viêm màng não mủ": "Meningococcal Vaccine",
        "Vắc xin phòng Viêm não Nhật Bản": "Japanese Encephalitis Vaccine",
        "Vắc xin polysaccharide phế cầu liên hợp với protein D của Haemophilus influenzae không định tuýp (NTHi)": "Pneumococcal conjugate vaccine",
        "Vắc xin tổng hợp phòng 6 bệnh: Bạch hầu - Ho gà - Uốn ván - Bại liệt - Hib và Viêm gan B": "Diphtheria-Tetanus-Pertussis-Poliovirus-Hepatitis B-Haemophilus influenzae type b Vaccine"
    }

    # Các từ điển sửa lỗi chính tả/phiên âm tiếng Việt sang tiếng Anh
    spelling_fixes = {
        "amoxicilin": "amoxicillin",
        "ampicilin": "ampicillin",
        "cloxacilin": "cloxacillin",
        "cephalexin": "cephalexin",
        "aciclovir": "acyclovir",
        "clorpheniramin maleat": "chlorpheniramine maleate",
        "clorpromazin hydroclorid": "chlorpromazine hydrochloride",
        "alimemazin": "alimemazine",
        "amitriptylin hydroclorid": "amitriptyline hydrochloride",
        "vastarel": "trimetazidine",
        "berlthyrox": "levothyroxine",
        "doxycyclin": "doxycycline",
        "cotrimoxazol": "sulfamethoxazole / trimethoprim",
        "nitralmyl": "nitroglycerin",
        "prednisolon": "prednisolone",
        "methylprednisolon": "methylprednisolone",
        "chlorpheniramin": "chlorpheniramine",
        "vastarel": "trimetazidine"
    }

    # Đọc tệp pill.txt
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    cleaned_lines = []
    changes_made = 0
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("\n")
            continue
            
        # 1. Thay thế chính xác từ bảng dịch
        if stripped in replacements:
            new_val = replacements[stripped]
            if new_val:  # Nếu giá trị dịch không rỗng
                cleaned_lines.append(new_val + "\n")
                print(f"Đã dịch: '{stripped}' -> '{new_val}'")
                changes_made += 1
            else:
                print(f"Đã xóa dòng tiêu đề: '{stripped}'")
                # Không thêm dòng này vào (xóa tiêu đề)
                changes_made += 1
            continue
            
        # 2. Sửa lỗi chính tả/phiên âm Việt hóa
        lowered = stripped.lower()
        if lowered in spelling_fixes:
            new_val = spelling_fixes[lowered]
            # Giữ nguyên hoa/thường chữ cái đầu
            if stripped[0].isupper():
                new_val = new_val[0].upper() + new_val[1:]
            cleaned_lines.append(new_val + "\n")
            print(f"Sửa chính tả: '{stripped}' -> '{new_val}'")
            changes_made += 1
            continue
            
        # 3. Chuẩn hóa tự động các từ Latinh hóa (ví dụ: clor -> chlor, bỏ ngoặc đơn, v.v.)
        modified = stripped
        
        # Loại bỏ các gốc muối/phụ gia trong ngoặc đơn ở cuối tên thuốc
        # Ví dụ: "Doxycyclin (hydroclorid)" -> "Doxycyclin"
        modified = re.sub(r"\s*\([^)]*\)\s*$", "", modified)
        
        # Chuyển đổi một số ký tự phiên âm đặc thù
        modified_lower = modified.lower()
        if modified_lower.startswith("clor"):
            modified = "Chlor" + modified[4:]
        elif modified_lower.startswith("calci"):
            modified = "Calcium" + modified[5:]
        elif modified_lower.startswith("kali"):
            modified = "Potassium" + modified[4:]
        elif modified_lower.startswith("natri"):
            modified = "Sodium" + modified[5:]
            
        if modified != stripped:
            # Sửa tiếp spelling lần cuối
            m_lower = modified.lower()
            if m_lower in spelling_fixes:
                modified = spelling_fixes[m_lower]
                if stripped[0].isupper():
                    modified = modified[0].upper() + modified[1:]
            cleaned_lines.append(modified + "\n")
            print(f"Tự động chuẩn hóa: '{stripped}' -> '{modified}'")
            changes_made += 1
        else:
            cleaned_lines.append(line)
            
    # Ghi đè lại tệp pill.txt
    with open(input_file, "w", encoding="utf-8") as f:
        f.writelines(cleaned_lines)
        
    print(f"\nĐã hoàn tất chuẩn hóa trực tiếp tệp '{input_file}'. Tổng số dòng đã thay đổi: {changes_made}")

if __name__ == "__main__":
    translate_pill()

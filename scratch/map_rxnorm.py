import os
import sys
import requests
import json
import time
import csv

# Đảm bảo console in unicode không bị lỗi
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def get_rxcui_from_api(drug_name):
    """
    Truy vấn API NIH RxNav để tìm mã RxCUI.
    Nếu tìm theo tên chính xác không được, sẽ thử một số cách chuẩn hóa tên.
    """
    drug_name_clean = drug_name.strip()
    
    # 1. Thử truy vấn trực tiếp bằng tên
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={drug_name_clean}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            rxnorm_id_list = data.get("idGroup", {}).get("rxnormId", [])
            if rxnorm_id_list:
                return rxnorm_id_list[0]
    except Exception:
        pass
        
    # 2. Thử nghiệm thay thế dấu gạch chéo '/' bằng khoảng trắng (đối với thuốc phối hợp)
    if "/" in drug_name_clean:
        name_alt = drug_name_clean.replace("/", "and").strip()
        url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={name_alt}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                rxnorm_id_list = data.get("idGroup", {}).get("rxnormId", [])
                if rxnorm_id_list:
                    return rxnorm_id_list[0]
        except Exception:
            pass
            
    # 3. Sử dụng API findRxcuiByIdentifier nếu vẫn không ra kết quả
    # hoặc API Approximate Match của NIH (rxtx)
    url_approx = f"https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term={drug_name_clean}&maxEntries=1"
    try:
        response = requests.get(url_approx, timeout=10)
        if response.status_code == 200:
            data = response.json()
            candidates = data.get("approximateGroup", {}).get("candidate", [])
            if candidates:
                # Trả về RxCUI của ứng viên tốt nhất
                return candidates[0].get("rxcui")
    except Exception:
        pass
        
    return None

def main():
    input_file = "pill.txt"
    output_dir = "db"
    output_json = os.path.join(output_dir, "rxnorm_mapped.json")
    output_csv = os.path.join(output_dir, "rxnorm_mapped.csv")
    
    if not os.path.exists(input_file):
        print(f"Lỗi: Không tìm thấy file đầu vào '{input_file}'")
        sys.exit(1)
        
    # Tạo thư mục đầu ra nếu chưa tồn tại
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Đã tạo thư mục đầu ra: '{output_dir}'")
        
    # Đọc danh sách thuốc
    with open(input_file, "r", encoding="utf-8") as f:
        drugs = [line.strip() for line in f if line.strip()]
        
    # Lọc bỏ trùng lặp để tiết kiệm lượt gọi API, nhưng vẫn giữ thứ tự
    unique_drugs = []
    seen = set()
    for drug in drugs:
        if drug not in seen:
            seen.add(drug)
            unique_drugs.append(drug)
            
    print(f"Tìm thấy {len(drugs)} dòng thuốc trong {input_file} ({len(unique_drugs)} tên hoạt chất duy nhất).")
    print("Bắt đầu truy vấn API RxNorm của NIH (tuần tự, delay 50ms để tránh rate-limit)...")
    
    mapped_results = {}
    success_count = 0
    fail_count = 0
    
    for idx, drug in enumerate(unique_drugs):
        print(f"[{idx+1}/{len(unique_drugs)}] Đang tra cứu: '{drug}'... ", end="", flush=True)
        
        rxcui = get_rxcui_from_api(drug)
        
        if rxcui:
            mapped_results[drug] = rxcui
            success_count += 1
            print(f"Thành công! Mã: {rxcui}")
        else:
            mapped_results[drug] = ""
            fail_count += 1
            print("Thất bại.")
            
        # Tránh spam API dồn dập
        time.sleep(0.05)
        
    # Ánh xạ ngược lại danh sách gốc (bao gồm cả các dòng trùng lặp)
    final_output = []
    for drug in drugs:
        rxcui = mapped_results.get(drug, "")
        final_output.append({
            "original_name": drug,
            "rxcui": rxcui
        })
        
    # Ghi file JSON
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
        
    # Ghi file CSV
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["original_name", "rxcui"])
        for item in final_output:
            writer.writerow([item["original_name"], item["rxcui"]])
            
    print("\n=== QUY TRÌNH ÁNH XẠ HOÀN TẤT ===")
    print(f" - Tổng số thuốc duy nhất: {len(unique_drugs)}")
    print(f" - Ánh xạ thành công: {success_count}")
    # Đếm số lượng mã rỗng trong kết quả cuối
    empty_count = sum(1 for item in final_output if not item["rxcui"])
    print(f" - Ánh xạ thất bại: {fail_count}")
    print(f" - Kết quả đã được lưu tại:")
    print(f"    * JSON: {output_json}")
    print(f"    * CSV: {output_csv}")

if __name__ == "__main__":
    main()

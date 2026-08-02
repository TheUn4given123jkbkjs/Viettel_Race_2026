import os
import json
import glob
import re
import sys

# Ensure UTF-8 output for Windows terminal
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

SUBMISSION_DIR = r"D:\AI Race\Viettel_Race_2026\submissionv3"
INPUT_DIR = r"D:\AI Race\Viettel_Race_2026\input_turn2_vong1\input"

def analyze():
    json_files = glob.glob(os.path.join(SUBMISSION_DIR, "*.json"))
    if not json_files:
        print(f"No JSON files found in {SUBMISSION_DIR}")
        return

    print(f"Found {len(json_files)} JSON files in submission.")
    
    total_entities = 0
    duplicate_count = 0
    empty_candidates_diagnoses = 0
    empty_candidates_drugs = 0
    total_diagnoses = 0
    total_drugs = 0
    total_symptoms = 0
    total_tests = 0
    total_results = 0
    
    type_distribution = {}
    assertions_distribution = {"isNegated": 0, "isHistorical": 0, "isFamily": 0, "empty": 0}
    alignment_errors = 0
    
    # Detail on candidates format issues
    asterisk_candidates = 0
    
    for j_path in json_files:
        fname = os.path.basename(j_path)
        txt_path = os.path.join(INPUT_DIR, fname.replace(".json", ".txt"))
        
        # Read original text if exists
        doc_text = ""
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                doc_text = f.read()
                
        with open(j_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception as e:
                print(f"Failed to parse {fname}: {e}")
                continue
                
        if not isinstance(data, list):
            print(f"Root element of {fname} is not a list!")
            continue
            
        seen_entities = set()
        
        for ent in data:
            total_entities += 1
            text = ent.get("text", "")
            etype = ent.get("type", "")
            pos = ent.get("position", [0, 0])
            assertions = ent.get("assertions", [])
            candidates = ent.get("candidates", [])
            
            # Check duplicate entity in same file
            ent_key = (text, tuple(pos), etype, tuple(assertions), tuple(candidates))
            if ent_key in seen_entities:
                duplicate_count += 1
            seen_entities.add(ent_key)
            
            # Count type
            type_distribution[etype] = type_distribution.get(etype, 0) + 1
            if etype == "CHẨN_ĐOÁN":
                total_diagnoses += 1
                if not candidates:
                    empty_candidates_diagnoses += 1
                for c in candidates:
                    if "*" in c:
                        asterisk_candidates += 1
            elif etype == "THUỐC":
                total_drugs += 1
                if not candidates:
                    empty_candidates_drugs += 1
                for c in candidates:
                    if "*" in c:
                        asterisk_candidates += 1
            elif etype == "TRIỆU_CHỨNG":
                total_symptoms += 1
            elif etype == "TÊN_XÉT_NGHIỆM":
                total_tests += 1
            elif etype == "KẾT_QUẢ_XÉT_NGHIỆM":
                total_results += 1
                
            # Assertions check
            if not assertions:
                assertions_distribution["empty"] += 1
            else:
                for ass in assertions:
                    if ass in assertions_distribution:
                        assertions_distribution[ass] += 1
                        
            # Alignment check
            if doc_text:
                start, end = pos[0], pos[1]
                substring = doc_text[start:end]
                if substring.lower() != text.lower():
                    alignment_errors += 1
                    if alignment_errors <= 5:
                        print(f"Mismatch in {fname}: text='{text}', substring='{substring}', pos={pos}")
                        
    print("\n" + "="*50)
    print("SUBMISSION V3 DETAILED ANALYSIS")
    print("="*50)
    print(f"Tong so thuc the trich xuat: {total_entities}")
    print(f"So luong thuc the bi trung lap (trung 100%): {duplicate_count} ({duplicate_count/total_entities*100:.2f}%)")
    print(f"So luong loi lech toa do so voi text goc: {alignment_errors}")
    
    print("\n--- Phan phoi Nhan Thuc the (Entity Type) ---")
    for k, v in type_distribution.items():
        print(f"  {k:22}: {v} ({v/total_entities*100:.2f}%)")
        
    print("\n--- Tinh trang Gan ma Candidates ---")
    print(f"Tong so CHAN_DOAN: {total_diagnoses}")
    print(f"  - So CHAN_DOAN khong co code: {empty_candidates_diagnoses} ({empty_candidates_diagnoses/max(1, total_diagnoses)*100:.2f}%)")
    print(f"Tong so THUOC: {total_drugs}")
    print(f"  - So THUOC khong co code: {empty_candidates_drugs} ({empty_candidates_drugs/max(1, total_drugs)*100:.2f}%)")
    print(f"So luong ma candidates chua dau sao '*' (vi du D63.0*): {asterisk_candidates}")
    
    print("\n--- Phan phoi Nhan Ngu Canh (Assertions) ---")
    print(f"So luong thuc the khong co assertions (empty): {assertions_distribution['empty']} ({assertions_distribution['empty']/total_entities*100:.2f}%)")
    for k, v in assertions_distribution.items():
        if k != "empty":
            print(f"  {k:22}: {v}")
            
    print("\n" + "="*50)
    print("GOI Y & PHAT HIEN SU CO:")
    if duplicate_count > 0:
        print("RED WARNING: Co qua nhieu thuc the trung lap 100% trong cung mot file. Dieu nay co the do LLM bi lap lai hoac loi lap post-processing.")
    if alignment_errors > 0:
        print("RED WARNING: Van con loi lech toa do giua 'text' va text trong file goc o 'position'.")
    if asterisk_candidates > 0:
        print("RED WARNING: Co ma candidate chua ky tu '*'. He thong cham diem y khoa (ICD-10/RxNorm) co the khong cong nhan ma chua ki tu dac biet nay.")
    if empty_candidates_diagnoses / max(1, total_diagnoses) > 0.3:
        print("RED WARNING: Ty le CHAN_DOAN khong co ma candidates qua cao! Can kiem tra lai bo chuan hoa (HybridLinker).")
    if assertions_distribution["empty"] / total_entities > 0.9:
        print("RED WARNING: Hon 90% thuc the khong co nhan ngu canh (assertions). Diem J_assertion bi keo tut do thieu thong tin.")

if __name__ == "__main__":
    analyze()

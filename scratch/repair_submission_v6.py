import os
import json
import glob
import re
import sys
import shutil

sys.stdout.reconfigure(encoding='utf-8')
sys.path.append('D:/AI Race/Viettel_Race_2026/pipeline')

from hybrid_linker import HybridLinker

# List of known common symptoms to repair incorrect overrides
SYMPTOMS_WHITELIST = {
    "đau", "sốt", "ho", "ngứa", "nôn", "mệt", "ớn lạnh", "khó thở", "chóng mặt", 
    "đau đầu", "đau ngực", "đau bụng", "buồn nôn", "mệt mỏi", "đánh trống ngực", 
    "bí tiểu", "tiêu chảy", "táo bón", "chướng bụng", "dịch báng", "ho khan",
    "ho có đờm", "ho đờm xanh", "ớn lạnh", "khó nuốt", "nuốt nghẹn", "tím tái",
    "ngất", "choáng", "đau thượng vị", "ợ hơi", "ợ chua", "đau thắt ngực", 
    "yếu liệt", "liệt", "mất phản xạ", "sưng", "tấy đỏ", "mất ngủ", "lo âu"
}

def repair_submission():
    print("=" * 80)
    print("🛠️  REPAIRING SUBMISSION V6 (FIXING TYPE OVERRIDES & DB LINKING)")
    print("=" * 80)
    
    QWEN_DIR = "D:/AI Race/Viettel_Race_2026/finetune_qwen_7b/submission_v6"
    REPAIRED_DIR = "D:/AI Race/Viettel_Race_2026/finetune_qwen_7b/submission_v6_repaired"
    DB_PATH = "D:/AI Race/Viettel_Race_2026/db/medical_codes.db"
    
    if os.path.exists(REPAIRED_DIR):
        shutil.rmtree(REPAIRED_DIR)
    os.makedirs(REPAIRED_DIR, exist_ok=True)
    
    # Initialize Upgraded Linker (has Layer 1.5 substring match and G6PD/THA synonyms)
    linker = HybridLinker(db_path=DB_PATH, use_semantic=False)
    
    json_files = glob.glob(f"{QWEN_DIR}/*.json")
    print(f"Found {len(json_files)} JSON files to repair...")
    
    repaired_count = 0
    candidate_updates = 0
    symptom_restores = 0
    
    for fpath in json_files:
        fname = os.path.basename(fpath)
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        repaired_ents = []
        for ent in data:
            text = ent.get("text", "").strip()
            text_clean = text.lower()
            etype = ent.get("type", "").strip()
            assertions = ent.get("assertions", [])
            candidates = ent.get("candidates", [])
            pos = ent.get("position", [0, 0])
            
            # 1. Restore symptoms that were incorrectly overridden to CHẨN_ĐOÁN
            is_symptom = False
            for sym in SYMPTOMS_WHITELIST:
                if sym in text_clean or text_clean in sym:
                    is_symptom = True
                    break
                    
            if is_symptom and etype == "CHẨN_ĐOÁN" and text_clean not in ["u ác buồng trứng", "viêm gan", "gút", "gout", "tiểu đường", "đái tháo đường", "xơ gan", "nhồi máu cơ tim"]:
                etype = "TRIỆU_CHỨNG"
                candidates = []
                symptom_restores += 1
                
            # 2. Relink ICD-10/RxNorm candidates using upgraded Layer 1.5 Substring matching
            if etype in ["CHẨN_ĐOÁN", "THUỐC"]:
                new_codes = linker.link_entity(text, etype)
                if new_codes:
                    if new_codes != candidates:
                        candidates = new_codes
                        candidate_updates += 1
                else:
                    # Clean any bad characters in existing candidates
                    candidates = [c.replace('*', '').replace('†', '').strip() for c in candidates if c]
            else:
                candidates = []
                
            repaired_ents.append({
                "text": text,
                "position": pos,
                "type": etype,
                "assertions": assertions,
                "candidates": candidates
            })
            
        # Save repaired file
        out_path = os.path.join(REPAIRED_DIR, fname)
        with open(out_path, "w", encoding="utf-8") as out_f:
            json.dump(repaired_ents, out_f, ensure_ascii=False, indent=2)
            
    linker.close()
    
    # Package into zip
    zip_path = "D:/AI Race/Viettel_Race_2026/submission_v6_repaired"
    shutil.make_archive(zip_path, 'zip', REPAIRED_DIR)
    
    print("\n" + "=" * 40)
    print("📊 REPAIR REPORT")
    print("=" * 40)
    print(f"Symptoms restored to TRIỆU_CHỨNG: {symptom_restores}")
    print(f"Candidate codes updated/fixed:    {candidate_updates}")
    print(f"Repaired Zip saved to:           {zip_path}.zip")
    print("=" * 80)

if __name__ == "__main__":
    repair_submission()

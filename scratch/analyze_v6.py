import glob
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

files = glob.glob('D:/AI Race/Viettel_Race_2026/finetune_qwen_7b/submissionv3/*.json')
total_ents = 0
type_counts = {}
assertion_counts = {}
has_candidates_count = 0
empty_candidates_count = 0
eligible_candidates_count = 0

for fpath in files:
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
        for ent in data:
            total_ents += 1
            etype = ent.get("type", "")
            type_counts[etype] = type_counts.get(etype, 0) + 1
            
            for ass in ent.get("assertions", []):
                assertion_counts[ass] = assertion_counts.get(ass, 0) + 1
                
            cands = ent.get("candidates", [])
            if etype in ["CHẨN_ĐOÁN", "THUỐC"]:
                eligible_candidates_count += 1
                if cands:
                    has_candidates_count += 1
                else:
                    empty_candidates_count += 1

print("="*60)
print("📊 SUBMISSION V6 ANALYSIS")
print("="*60)
print(f"Total files: {len(files)}")
print(f"Total entities: {total_ents}")
print("\n--- Type Distribution ---")
for k, v in type_counts.items():
    print(f"  {k:22}: {v} entities ({v/total_ents*100:.2f}%)")
    
print("\n--- Assertion Distribution ---")
for k, v in assertion_counts.items():
    print(f"  {k:22}: {v} assertions")
    
print("\n--- Candidates Info ---")
print(f"  Eligible (CHẨN_ĐOÁN/THUỐC): {eligible_candidates_count}")
print(f"  Has candidates:            {has_candidates_count} ({has_candidates_count/eligible_candidates_count*100:.2f}%)")
print(f"  Empty candidates:          {empty_candidates_count} ({empty_candidates_count/eligible_candidates_count*100:.2f}%)")
print("="*60)

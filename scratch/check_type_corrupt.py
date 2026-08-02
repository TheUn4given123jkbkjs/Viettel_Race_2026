import glob
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

files = glob.glob('D:/AI Race/Viettel_Race_2026/finetune_qwen_7b/submission_v6/*.json')
corrupted_symptoms = {}

for fpath in files:
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
        for ent in data:
            text = ent.get("text", "").lower().strip()
            etype = ent.get("type", "")
            
            # These are definitely symptoms
            if text in ["khó thở", "ho", "sốt", "đau ngực", "đau đầu", "đau bụng", "buồn nôn", "mệt mỏi", "chóng mặt", "đánh trống ngực"]:
                if etype == "CHẨN_ĐOÁN":
                    corrupted_symptoms[text] = corrupted_symptoms.get(text, 0) + 1

print("="*60)
print("⚠️ CORRUPTED SYMPTOMS IN SUBMISSION V6 (OVERRIDDEN TO CHẨN_ĐOÁN)")
print("="*60)
for k, v in sorted(corrupted_symptoms.items(), key=lambda x: -x[1]):
    print(f"  Symptom '{k}' was overridden to CHẨN_ĐOÁN: {v} times")
print("="*60)
print(f"Total corrupted symptom instances: {sum(corrupted_symptoms.values())}")
print("="*60)

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

TRAIN_PATH = "train_clean.json"

def analyze_train():
    if not os.path.exists(TRAIN_PATH):
        print(f"File {TRAIN_PATH} does not exist!")
        return
        
    with open(TRAIN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    total_convs = len(data)
    total_entities = 0
    type_distribution = {}
    empty_candidates_diag = 0
    empty_candidates_drug = 0
    total_diag = 0
    total_drug = 0
    empty_assertions = 0
    
    print(f"Total conversations in train set: {total_convs}")
    
    for item in data:
        convs = item.get("conversations", [])
        # Find the assistant turn
        gpt_val = ""
        for msg in convs:
            if msg["from"] == "gpt":
                gpt_val = msg["value"]
                break
                
        if not gpt_val:
            continue
            
        try:
            entities = json.loads(gpt_val)
        except Exception:
            continue
            
        for ent in entities:
            total_entities += 1
            etype = ent.get("type", "")
            type_distribution[etype] = type_distribution.get(etype, 0) + 1
            
            if etype == "CHẨN_ĐOÁN":
                total_diag += 1
                if not ent.get("candidates", []):
                    empty_candidates_diag += 1
            elif etype == "THUỐC":
                total_drug += 1
                if not ent.get("candidates", []):
                    empty_candidates_drug += 1
                    
            if not ent.get("assertions", []):
                empty_assertions += 1
                
    avg_entities = total_entities / total_convs if total_convs > 0 else 0
    print(f"Total entities: {total_entities}")
    print(f"Average entities per conversation: {avg_entities:.2f}")
    
    print("\n--- Type distribution in train set ---")
    for k, v in type_distribution.items():
        print(f"  {k:22}: {v} ({v/total_entities*100:.2f}%)")
        
    print("\n--- Candidates in train set ---")
    print(f"Diagnoses with empty candidates: {empty_candidates_diag} / {total_diag} ({empty_candidates_diag/max(1, total_diag)*100:.2f}%)")
    print(f"Drugs with empty candidates: {empty_candidates_drug} / {total_drug} ({empty_candidates_drug/max(1, total_drug)*100:.2f}%)")
    
    print(f"\nEntities with empty assertions: {empty_assertions} / {total_entities} ({empty_assertions/max(1, total_entities)*100:.2f}%)")

if __name__ == "__main__":
    analyze_train()

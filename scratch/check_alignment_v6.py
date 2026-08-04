import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

QWEN_DIR = "D:/AI Race/Viettel_Race_2026/finetune_qwen_7b/submission_v6_repaired"
INPUT_DIR = "D:/AI Race/Viettel_Race_2026/input_turn2_vong1/input"

json_files = glob.glob(f"{QWEN_DIR}/*.json")
mismatches = 0
total_ents = 0

for fpath in json_files:
    fname = os.path.basename(fpath)
    txt_name = fname.replace(".json", ".txt")
    txt_path = os.path.join(INPUT_DIR, txt_name)
    
    if not os.path.exists(txt_path):
        # try without subfolders
        txt_path = f"D:/AI Race/input_turn2_vong1/input/{txt_name}"
        if not os.path.exists(txt_path):
            continue
            
    with open(txt_path, "r", encoding="utf-8") as f:
        doc_text = f.read()
        
    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for ent in data:
        total_ents += 1
        text = ent.get("text", "")
        pos = ent.get("position", [0, 0])
        
        extracted = doc_text[pos[0]:pos[1]]
        if extracted != text:
            mismatches += 1
            if mismatches <= 20:
                print(f"Mismatch in {fname}:")
                print(f"  Expected: '{text}' at {pos}")
                print(f"  Got:      '{extracted}'")
                print("-" * 40)

print("="*60)
print(f"Total entities checked: {total_ents}")
print(f"Total position mismatches: {mismatches} ({mismatches/total_ents*100:.2f}%)")
print("="*60)

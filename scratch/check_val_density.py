import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("D:/AI Race/Viettel_Race_2026/fine_tune_phobert/val_phobert.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()
    
total_ents = 0
for line in lines:
    data = json.loads(line)
    # The entities in val_phobert.jsonl might be in a different format
    # Let's see the structure of one line
    if "entities" in data:
        total_ents += len(data["entities"])
    elif "ner_tags" in data:
        # sequence labeling format
        tags = data["ner_tags"]
        # count B- tags
        b_count = sum(1 for t in tags if t % 2 == 1) # B-tags are odd in standard Bio
        total_ents += b_count
    else:
        # just print keys to see
        print(data.keys())
        break

print(f"Total lines: {len(lines)}")
print(f"Total entities: {total_ents}")
print(f"Avg entities per sample: {total_ents / len(lines) if len(lines) > 0 else 0}")

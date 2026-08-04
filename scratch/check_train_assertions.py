import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("D:/AI Race/Viettel_Race_2026/train_clean.json", "r", encoding="utf-8") as f:
    data = json.load(f)

count = 0
for idx, item in enumerate(data):
    convs = item["conversations"]
    gpt_val = convs[1]["value"]
    try:
        ents = json.loads(gpt_val)
        for ent in ents:
            if ent.get("assertions"):
                print(f"Sample {idx}:")
                print(f"  Text: {ent.get('text')}")
                print(f"  Type: {ent.get('type')}")
                print(f"  Assertions: {ent.get('assertions')}")
                # Print the surrounding context from human message
                human_val = convs[0]["value"]
                # Find where the text is in the human message
                print("  Context:")
                for line in human_val.split("\n"):
                    if ent.get('text') in line:
                        print(f"    {line.strip()}")
                print("-" * 50)
                count += 1
                if count >= 10:
                    break
    except Exception:
        pass
    if count >= 10:
        break

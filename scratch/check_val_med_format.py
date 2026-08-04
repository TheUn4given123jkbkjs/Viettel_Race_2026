import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open("D:/AI Race/Viettel_Race_2026/fine_tune_phobert/val_phobert.jsonl", "r", encoding="utf-8") as f:
    lines = f.readlines()[:5]

id_to_label = {0: 'O', 1: 'B-TRIỆU_CHỨNG', 2: 'I-TRIỆU_CHỨNG', 3: 'B-TÊN_XÉT_NGHIỆM', 4: 'I-TÊN_XÉT_NGHIỆM', 5: 'B-KẾT_QUẢ_XÉT_NGHIỆM', 6: 'I-KẾT_QUẢ_XÉT_NGHIỆM', 7: 'B-CHẨN_ĐOÁN', 8: 'I-CHẨN_ĐOÁN', 9: 'B-THUỐC', 10: 'I-THUỐC'}

for idx, line in enumerate(lines):
    data = json.loads(line)
    tokens = data["tokens"]
    tags = data["ner_tags"]
    
    entities = []
    curr_ent = None
    
    for tok, tag in zip(tokens, tags):
        label = id_to_label[tag]
        if label.startswith("B-"):
            if curr_ent:
                entities.append(curr_ent)
            curr_ent = {"type": label[2:], "tokens": [tok]}
        elif label.startswith("I-"):
            if curr_ent and curr_ent["type"] == label[2:]:
                curr_ent["tokens"].append(tok)
            else:
                if curr_ent:
                    entities.append(curr_ent)
                curr_ent = None
        else:
            if curr_ent:
                entities.append(curr_ent)
            curr_ent = None
    if curr_ent:
        entities.append(curr_ent)
        
    print(f"\n--- Line {idx} ---")
    for ent in entities:
        text = " ".join(ent["tokens"])
        print(f"  [{ent['type']}] '{text}'")


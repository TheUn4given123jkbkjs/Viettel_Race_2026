import os
import json
import re
import random
import sys
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

# Standardize path
BASE_DIR = Path("d:/record_by_me/Viettel_race")
SAMPLE_DIRS = ["sample_A", "sample_C", "sample_Long", "sample_D", "sample_E"]

OUTPUT_DIR = BASE_DIR / "fine_tune_phobert"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# List of 5 entity types
LABEL_LIST = ["TRIỆU_CHỨNG", "TÊN_XÉT_NGHIỆM", "KẾT_QUẢ_XÉT_NGHIỆM", "CHẨN_ĐOÁN", "THUỐC"]

# Mapping labels to IDs
# O: 0
# B-Type: 2*i + 1
# I-Type: 2*i + 2
LABEL_TO_ID = {"O": 0}
for i, label in enumerate(LABEL_LIST):
    LABEL_TO_ID[f"B-{label}"] = 2 * i + 1
    LABEL_TO_ID[f"I-{label}"] = 2 * i + 2

# Save the label mapping for Hugging Face config
with open(OUTPUT_DIR / "label_mapping.json", "w", encoding="utf-8") as f:
    json.dump({
        "label_to_id": LABEL_TO_ID,
        "id_to_label": {v: k for k, v in LABEL_TO_ID.items()}
    }, f, ensure_ascii=False, indent=2)

def tokenize_and_align_positions(text):
    """
    Split text into words and record their start and end character positions.
    """
    tokens = []
    # Regex to find words or punctuation
    for m in re.finditer(r'\w+|[^\w\s]', text):
        tokens.append({
            "word": m.group(),
            "start": m.start(),
            "end": m.end()
        })
    return tokens

def main():
    print("=" * 80)
    print("  BẮT ĐẦU CHUYỂN ĐỔI DỮ LIỆU SANG BIO SEQUENCE TAGGING CHO PHOBERT")
    print("=" * 80)
    
    all_examples = []
    
    for s_dir in SAMPLE_DIRS:
        input_dir = BASE_DIR / s_dir / "input"
        output_dir = BASE_DIR / s_dir / "output"
        
        if not input_dir.exists() or not output_dir.exists():
            continue
            
        print(f"Đang xử lý {s_dir}...")
        
        # Scannng files
        txt_files = []
        for p_dir in os.scandir(input_dir):
            if p_dir.is_dir():
                for f in os.scandir(p_dir.path):
                    if f.is_file() and f.name.endswith(".txt"):
                        txt_files.append(Path(f.path))
            elif p_dir.is_file() and p_dir.name.endswith(".txt"):
                txt_files.append(Path(p_dir.path))
                
        json_lookup = {}
        for p_dir in os.scandir(output_dir):
            if p_dir.is_dir():
                for f in os.scandir(p_dir.path):
                    if f.is_file() and f.name.endswith(".json") and f.name != 'stats.json':
                        json_lookup[f.name[:-5]] = Path(f.path)
            elif p_dir.is_file() and p_dir.name.endswith(".json") and p_dir.name != 'stats.json':
                json_lookup[p_dir.name[:-5]] = Path(p_dir.path)
                
        for f in txt_files:
            try:
                text = f.read_text(encoding="utf-8")
            except:
                text = f.read_text(encoding="utf-8-sig", errors="replace")
                
            jf = json_lookup.get(f.stem)
            if not jf or not jf.exists():
                continue
                
            try:
                entities = json.loads(jf.read_text(encoding="utf-8"))
            except:
                entities = json.loads(jf.read_text(encoding="utf-8-sig", errors="replace"))
                
            if not isinstance(entities, list):
                continue
                
            # Tokenize text into words with char index bounds
            tokens_data = tokenize_and_align_positions(text)
            
            # Map words to BIO tags
            tags = ["O"] * len(tokens_data)
            
            for ent in entities:
                ent_type = ent.get("type", "")
                if ent_type not in LABEL_LIST:
                    continue
                start_char, end_char = ent.get("position", [0, 0])
                
                # Find tokens that fall inside this entity span
                first_found = False
                for idx, t in enumerate(tokens_data):
                    # Check overlap
                    if t["start"] >= start_char and t["end"] <= end_char:
                        if not first_found:
                            tags[idx] = f"B-{ent_type}"
                            first_found = True
                        else:
                            # Only label as I-Type if it hasn't been set by another entity
                            if tags[idx] == "O":
                                tags[idx] = f"I-{ent_type}"
                                
            # Convert tags to IDs
            tag_ids = [LABEL_TO_ID[t] for t in tags]
            words = [t["word"] for t in tokens_data]
            
            all_examples.append({
                "tokens": words,
                "ner_tags": tag_ids
            })
            
    print(f"Tổng số mẫu được tạo: {len(all_examples)}")
    
    # Shuffle and split into Train (90%) and Val (10%)
    random.seed(42)
    random.shuffle(all_examples)
    split_idx = int(len(all_examples) * 0.9)
    train_data = all_examples[:split_idx]
    val_data = all_examples[split_idx:]
    
    train_out = OUTPUT_DIR / "train_phobert.jsonl"
    val_out = OUTPUT_DIR / "val_phobert.jsonl"
    
    with open(train_out, "w", encoding="utf-8") as f:
        for ex in train_data:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
            
    with open(val_out, "w", encoding="utf-8") as f:
        for ex in val_data:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
            
    print(f"✅ Đã ghi tập train ({len(train_data)} mẫu) vào {train_out}")
    print(f"✅ Đã ghi tập validation ({len(val_data)} mẫu) vào {val_out}")
    print("Cấu trúc nhãn (Label distributions):")
    all_tag_ids = [tid for ex in all_examples for tid in ex["ner_tags"]]
    id_to_label = {v: k for k, v in LABEL_TO_ID.items()}
    counts = Counter(all_tag_ids)
    for tid, count in sorted(counts.items()):
        print(f"  - {id_to_label[tid]:22s} (ID: {tid:2d}): {count:,} tokens")

if __name__ == "__main__":
    main()

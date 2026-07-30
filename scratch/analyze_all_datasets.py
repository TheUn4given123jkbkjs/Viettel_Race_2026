import os
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIRS = ["sample_A", "sample_C", "sample_Long", "sample_D", "sample_E"]

def main():
    print("=" * 90)
    print("  PHÂN TÍCH QUY MÔ & CƠ CẤU TỔNG HỢP 5 BỘ DỮ LIỆU HUẤN LUYỆN (A, C, LONG, D, E)")
    print("=" * 90)
    
    total_txt = 0
    total_json = 0
    total_words = 0
    total_entities = 0
    
    combined_types = Counter()
    combined_assertions = Counter()
    combined_missing_icd = 0
    combined_missing_rx = 0
    
    dataset_summaries = {}
    
    for s_dir in SAMPLE_DIRS:
        input_dir = BASE_DIR / s_dir / "input"
        output_dir = BASE_DIR / s_dir / "output"
        
        if not input_dir.exists() or not output_dir.exists():
            continue
            
        # Fast directory scanning instead of recursive rglob
        txt_files = []
        for p_dir in os.scandir(input_dir):
            if p_dir.is_dir():
                for f in os.scandir(p_dir.path):
                    if f.is_file() and f.name.endswith(".txt"):
                        txt_files.append(Path(f.path))
            elif p_dir.is_file() and p_dir.name.endswith(".txt"):
                txt_files.append(Path(p_dir.path))
                
        json_files_count = 0
        json_lookup = {}
        for p_dir in os.scandir(output_dir):
            if p_dir.is_dir():
                for f in os.scandir(p_dir.path):
                    if f.is_file() and f.name.endswith(".json") and f.name != 'stats.json':
                        json_files_count += 1
                        json_lookup[f.name[:-5]] = Path(f.path)
            elif p_dir.is_file() and p_dir.name.endswith(".json") and p_dir.name != 'stats.json':
                json_files_count += 1
                json_lookup[p_dir.name[:-5]] = Path(p_dir.path)
        
        words_count = 0
        entities_count = 0
        missing_icd = 0
        missing_rx = 0
        
        types = Counter()
        assertions = Counter()
        
        for f in txt_files:
            try:
                text = f.read_text(encoding="utf-8")
            except:
                text = f.read_text(encoding="utf-8-sig", errors="replace")
            words_count += len(text.split())
            
            # Read output
            jf = json_lookup.get(f.stem)
            if jf and jf.exists():
                try:
                    labels = json.loads(jf.read_text(encoding="utf-8"))
                except:
                    labels = json.loads(jf.read_text(encoding="utf-8-sig", errors="replace"))
                    
                for ent in labels:
                    entities_count += 1
                    etype = ent.get("type", "")
                    types[etype] += 1
                    
                    for ass in ent.get("assertions", []):
                        assertions[ass] += 1
                        
                    candidates = ent.get("candidates", [])
                    if not candidates:
                        if etype == "CHẨN_ĐOÁN":
                            missing_icd += 1
                        elif etype == "THUỐC":
                            missing_rx += 1
                            
        # Store dataset summary
        dataset_summaries[s_dir] = {
            "num_files": len(txt_files),
            "avg_words": words_count / len(txt_files) if txt_files else 0,
            "total_entities": entities_count,
            "avg_entities": entities_count / len(txt_files) if txt_files else 0,
            "types": types,
            "assertions": assertions,
            "missing_icd": missing_icd,
            "missing_rx": missing_rx
        }
        
        # Add to combined
        total_txt += len(txt_files)
        total_json += json_files_count
        total_words += words_count
        total_entities += entities_count
        combined_types.update(types)
        combined_assertions.update(assertions)
        combined_missing_icd += missing_icd
        combined_missing_rx += missing_rx

    # Print comparative table
    print(f"{'Bộ dữ liệu':15s} | {'Số lượng file':13s} | {'Độ dài TB (từ)':15s} | {'Tổng thực thể':13s} | {'Thực thể/file':13s} | {'Thiếu ICD':9s} | {'Thiếu RxNorm':12s}")
    print("-" * 105)
    for name, s in dataset_summaries.items():
        print(f"{name:15s} | {s['num_files']:13d} | {s['avg_words']:15.1f} | {s['total_entities']:13d} | {s['avg_entities']:13.1f} | {s['missing_icd']:9d} | {s['missing_rx']:12d}")
    print("-" * 105)
    print(f"{'TỔNG CỘNG':15s} | {total_txt:13d} | {total_words/total_txt:15.1f} | {total_entities:13d} | {total_entities/total_txt:13.1f} | {combined_missing_icd:9d} | {combined_missing_rx:12d}")
    
    print("\n" + "=" * 90)
    print("  CƠ CẤU THÀNH PHẦN THỰC THỂ (COMBINED ENTITIES STRUCTURE)")
    print("=" * 90)
    for etype, cnt in combined_types.most_common():
        print(f"  * {etype:22s}: {cnt:5d} nhãn ({cnt/total_entities*100:.1f}%)")
        
    print("\n" + "=" * 90)
    print("  THUỘC TÍNH NGỮ CẢNH (COMBINED ASSERTIONS)")
    print("=" * 90)
    for ass, cnt in combined_assertions.most_common():
        print(f"  * {ass:15s}: {cnt:5d} lần xuất hiện")

if __name__ == "__main__":
    main()

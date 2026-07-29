import os
import sys
import json
import glob
import re
from collections import Counter, defaultdict
import numpy as np

# Ensure UTF-8 output formatting
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def find_dataset_pairs(base_dir):
    """
    Finds all (input_txt_path, output_json_path_or_None) in a dataset folder.
    Supports structures with part_1, part_2 or flat input/output dirs.
    """
    pairs = []
    input_dir = os.path.join(base_dir, "input")
    output_dir = os.path.join(base_dir, "output")
    
    if not os.path.exists(input_dir):
        return pairs
        
    for root, dirs, files in os.walk(input_dir):
        for f in files:
            if f.endswith(".txt"):
                input_path = os.path.join(root, f)
                rel_path = os.path.relpath(input_path, input_dir)
                
                # Corresponding output json path
                rel_json = os.path.splitext(rel_path)[0] + ".json"
                output_path = os.path.join(output_dir, rel_json)
                
                if not os.path.exists(output_path):
                    # Check if output is flat in output_dir
                    flat_output = os.path.join(output_dir, os.path.splitext(f)[0] + ".json")
                    if os.path.exists(flat_output):
                        output_path = flat_output
                    else:
                        output_path = None
                        
                pairs.append((input_path, output_path))
    return sorted(pairs, key=lambda x: x[0])

def analyze_all_datasets():
    datasets = {
        "sample_A": "sample_A",
        "sample_C": "sample_C",
        "sample_Long": "sample_Long",
        "input_turn2_vong1 (Test Set)": "input_turn2_vong1"
    }

    report = {}

    for name, path in datasets.items():
        if not os.path.exists(path):
            print(f"Skipping {name}, path not found: {path}")
            continue

        pairs = find_dataset_pairs(path)
        print(f"Dataset '{name}': found {len(pairs)} input files.")

        doc_lengths_char = []
        doc_lengths_word = []
        doc_lengths_line = []

        total_entities = 0
        entities_per_doc = []
        type_counts = Counter()
        assertion_counts = Counter()
        assertion_by_type = defaultdict(Counter)

        candidates_diag_total = 0
        candidates_diag_mapped = 0
        candidates_drug_total = 0
        candidates_drug_mapped = 0

        candidate_array_lens = Counter()

        icd10_codes = Counter()
        rxnorm_codes = Counter()

        position_exact_matches = 0
        position_total_checked = 0
        position_out_of_bounds = 0
        position_mismatches = []

        text_duplicates = Counter()

        for inp_path, out_path in pairs:
            # Read input text
            try:
                with open(inp_path, "r", encoding="utf-8") as f:
                    raw_text = f.read()
            except Exception as e:
                print(f"Error reading {inp_path}: {e}")
                continue

            char_len = len(raw_text)
            word_len = len(raw_text.split())
            line_len = len(raw_text.splitlines())

            doc_lengths_char.append(char_len)
            doc_lengths_word.append(word_len)
            doc_lengths_line.append(line_len)
            text_duplicates[raw_text.strip()] += 1

            if out_path and os.path.exists(out_path):
                try:
                    with open(out_path, "r", encoding="utf-8") as f:
                        entities = json.load(f)
                except Exception as e:
                    print(f"Error reading JSON {out_path}: {e}")
                    continue

                doc_ent_count = len(entities)
                total_entities += doc_ent_count
                entities_per_doc.append(doc_ent_count)

                for ent in entities:
                    etype = ent.get("type", "UNKNOWN")
                    text = ent.get("text", "")
                    pos = ent.get("position", [])
                    assertions = ent.get("assertions", [])
                    candidates = ent.get("candidates", [])

                    type_counts[etype] += 1

                    for ass in assertions:
                        assertion_counts[ass] += 1
                        assertion_by_type[etype][ass] += 1

                    if etype == "CHẨN_ĐOÁN":
                        candidates_diag_total += 1
                        if candidates:
                            candidates_diag_mapped += 1
                            for c in candidates:
                                icd10_codes[c] += 1
                            candidate_array_lens[len(candidates)] += 1
                        else:
                            candidate_array_lens[0] += 1
                    elif etype == "THUỐC":
                        candidates_drug_total += 1
                        if candidates:
                            candidates_drug_mapped += 1
                            for c in candidates:
                                rxnorm_codes[c] += 1
                            candidate_array_lens[len(candidates)] += 1
                        else:
                            candidate_array_lens[0] += 1

                    # Position checking
                    if len(pos) == 2:
                        start, end = pos[0], pos[1]
                        position_total_checked += 1
                        if start < 0 or end > len(raw_text):
                            position_out_of_bounds += 1
                            position_mismatches.append({
                                "file": inp_path,
                                "text": text,
                                "pos": pos,
                                "doc_len": len(raw_text),
                                "reason": "out_of_bounds"
                            })
                        else:
                            extracted_sub = raw_text[start:end]
                            if extracted_sub == text:
                                position_exact_matches += 1
                            else:
                                position_mismatches.append({
                                    "file": inp_path,
                                    "text_in_json": text,
                                    "text_at_pos": extracted_sub,
                                    "pos": pos,
                                    "reason": "text_mismatch"
                                })

        report[name] = {
            "total_files": len(pairs),
            "unique_text_count": len(text_duplicates),
            "duplicate_text_count": sum(c for c in text_duplicates.values() if c > 1),
            "char_len": {
                "mean": float(np.mean(doc_lengths_char)) if doc_lengths_char else 0,
                "std": float(np.std(doc_lengths_char)) if doc_lengths_char else 0,
                "min": int(np.min(doc_lengths_char)) if doc_lengths_char else 0,
                "median": float(np.median(doc_lengths_char)) if doc_lengths_char else 0,
                "max": int(np.max(doc_lengths_char)) if doc_lengths_char else 0,
            },
            "word_len": {
                "mean": float(np.mean(doc_lengths_word)) if doc_lengths_word else 0,
                "std": float(np.std(doc_lengths_word)) if doc_lengths_word else 0,
                "min": int(np.min(doc_lengths_word)) if doc_lengths_word else 0,
                "median": float(np.median(doc_lengths_word)) if doc_lengths_word else 0,
                "max": int(np.max(doc_lengths_word)) if doc_lengths_word else 0,
            },
            "line_len": {
                "mean": float(np.mean(doc_lengths_line)) if doc_lengths_line else 0,
                "min": int(np.min(doc_lengths_line)) if doc_lengths_line else 0,
                "max": int(np.max(doc_lengths_line)) if doc_lengths_line else 0,
            },
            "total_entities": total_entities,
            "entities_per_doc": {
                "mean": float(np.mean(entities_per_doc)) if entities_per_doc else 0,
                "min": int(np.min(entities_per_doc)) if entities_per_doc else 0,
                "median": float(np.median(entities_per_doc)) if entities_per_doc else 0,
                "max": int(np.max(entities_per_doc)) if entities_per_doc else 0,
            },
            "type_counts": dict(type_counts),
            "assertion_counts": dict(assertion_counts),
            "assertion_by_type": {k: dict(v) for k, v in assertion_by_type.items()},
            "candidates_diag": {
                "total": candidates_diag_total,
                "mapped": candidates_diag_mapped,
                "coverage_pct": (candidates_diag_mapped / candidates_diag_total * 100) if candidates_diag_total else 0,
                "unique_icd10_count": len(icd10_codes),
                "top_10_icd10": icd10_codes.most_common(10)
            },
            "candidates_drug": {
                "total": candidates_drug_total,
                "mapped": candidates_drug_mapped,
                "coverage_pct": (candidates_drug_mapped / candidates_drug_total * 100) if candidates_drug_total else 0,
                "unique_rxnorm_count": len(rxnorm_codes),
                "top_10_rxnorm": rxnorm_codes.most_common(10)
            },
            "candidate_array_lens": dict(candidate_array_lens),
            "position_checks": {
                "total_checked": position_total_checked,
                "exact_matches": position_exact_matches,
                "out_of_bounds": position_out_of_bounds,
                "match_rate_pct": (position_exact_matches / position_total_checked * 100) if position_total_checked else 0,
                "sample_mismatches": position_mismatches[:5]
            }
        }

    # Save complete JSON analysis
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_file = os.path.join(script_dir, "comprehensive_analysis.json")
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n Analysis saved to {out_file}")
    except Exception as e:
        print(f" Could not write file: {e}")

    # Print summary report directly to stdout
    print("\n" + "="*80)
    print(" SUMMARY ANALYSIS REPORT")
    print("="*80)
    for name, data in report.items():
        print(f"\n--- DATASET: {name} ---")
        print(f"Total Files: {data['total_files']} | Unique Texts: {data['unique_text_count']} | Duplicates: {data['duplicate_text_count']}")
        print(f"Char Length: mean={data['char_len']['mean']:.1f}, min={data['char_len']['min']}, median={data['char_len']['median']:.1f}, max={data['char_len']['max']}")
        print(f"Word Length: mean={data['word_len']['mean']:.1f}, min={data['word_len']['min']}, median={data['word_len']['median']:.1f}, max={data['word_len']['max']}")
        print(f"Line Count: mean={data['line_len']['mean']:.1f}, min={data['line_len']['min']}, max={data['line_len']['max']}")

        if data['total_entities'] > 0:
            print(f"Total Entities: {data['total_entities']} | Entities/Doc: mean={data['entities_per_doc']['mean']:.1f}, median={data['entities_per_doc']['median']:.1f}, max={data['entities_per_doc']['max']}")
            print("Type Counts:", data['type_counts'])
            print("Assertion Counts:", data['assertion_counts'])
            print(f"Diagnosis Mapping: {data['candidates_diag']['mapped']}/{data['candidates_diag']['total']} ({data['candidates_diag']['coverage_pct']:.2f}%) - Unique ICD10: {data['candidates_diag']['unique_icd10_count']}")
            print("Top ICD10:", data['candidates_diag']['top_10_icd10'])
            print(f"Drug Mapping: {data['candidates_drug']['mapped']}/{data['candidates_drug']['total']} ({data['candidates_drug']['coverage_pct']:.2f}%) - Unique RxNorm: {data['candidates_drug']['unique_rxnorm_count']}")
            print("Top RxNorm:", data['candidates_drug']['top_10_rxnorm'])
            print(f"Position Match Rate: {data['position_checks']['exact_matches']}/{data['position_checks']['total_checked']} ({data['position_checks']['match_rate_pct']:.2f}%)")
            print(f"Position Out of Bounds: {data['position_checks']['out_of_bounds']}")
            if data['position_checks']['sample_mismatches']:
                print("Sample Mismatches:", data['position_checks']['sample_mismatches'][:3])

    return report

if __name__ == "__main__":
    analyze_all_datasets()

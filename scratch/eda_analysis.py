"""
EDA (Exploratory Data Analysis) cho dữ liệu sinh huấn luyện y khoa.
Phân tích: phân bổ loại thực thể, phong cách văn bản, độ dài, vị trí, mã ICD/RxNorm.
"""
import os
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIRS = ["sample_A", "sample_C", "sample_Long"]

def find_all_files(sample_dir, subfolder, ext):
    """Tìm tất cả file trong thư mục, hỗ trợ cả cấu trúc flat và part_N."""
    root = BASE_DIR / sample_dir / subfolder
    if not root.exists():
        return []
    files = []
    for f in root.rglob(f"*{ext}"):
        if f.is_file():
            files.append(f)
    return sorted(files)

def classify_style(text):
    """Phân loại phong cách văn bản dựa trên heuristic nội dung."""
    has_case_report = bool(re.search(r'(Tiền sử bệnh|Bệnh sử hiện tại|Đánh giá tại bệnh viện|Lý do nhập viện|Triệu chứng hiện tại|Triệu chứng khi nhập viện)', text))
    has_qa = bool(re.search(r'(Hỏi\s*:|Trả lời\s*:|Câu hỏi từ người dùng|Câu trả lời của bác sĩ|Chào bác sĩ|Chào bạn)', text))
    has_article = bool(re.search(r'(LÀ GÌ\??|Định nghĩa khái niệm|Dấu hiệu và triệu chứng|Cách điều trị|là bệnh gì|là tình trạng|được đặc trưng bởi)', text, re.IGNORECASE))
    
    styles = []
    if has_case_report:
        styles.append("Case Report")
    if has_qa:
        styles.append("Q&A")
    if has_article:
        styles.append("Article")
    
    if len(styles) >= 2:
        return "Hybrid"
    elif len(styles) == 1:
        return styles[0]
    else:
        return "Other"

def check_position_accuracy(text, entities):
    """Kiểm tra position mapping có chính xác không."""
    total = 0
    correct = 0
    wrong = 0
    out_of_range = 0
    
    for ent in entities:
        pos = ent.get("position", [])
        ent_text = ent.get("text", "")
        if len(pos) != 2 or not ent_text:
            continue
        total += 1
        start, end = pos
        if start < 0 or end > len(text) or start >= end:
            out_of_range += 1
            continue
        extracted = text[start:end]
        if extracted.strip() == ent_text.strip():
            correct += 1
        else:
            wrong += 1
    
    return total, correct, wrong, out_of_range

def run_eda():
    print("=" * 70)
    print("  EDA: PHÂN TÍCH DỮ LIỆU SINH HUẤN LUYỆN Y KHOA")
    print("=" * 70)
    
    all_stats = {}
    grand_entity_types = Counter()
    grand_styles = Counter()
    grand_text_lengths = []
    grand_entity_counts = []
    grand_pos_total = 0
    grand_pos_correct = 0
    grand_pos_wrong = 0
    grand_pos_oor = 0
    grand_icd_codes = Counter()
    grand_rxnorm_codes = Counter()
    grand_candidate_has = 0
    grand_candidate_empty = 0
    grand_entity_type_details = defaultdict(lambda: {"has_candidates": 0, "no_candidates": 0})
    grand_assertions_counter = Counter()
    grand_empty_text_count = 0
    grand_empty_entities_count = 0
    grand_entity_text_samples = defaultdict(list)  # type -> sample texts
    
    for sample_name in SAMPLE_DIRS:
        print(f"\n{'─' * 60}")
        print(f"  📁 {sample_name}")
        print(f"{'─' * 60}")
        
        input_files = find_all_files(sample_name, "input", ".txt")
        output_files = find_all_files(sample_name, "output", ".json")
        
        print(f"  Input files (txt): {len(input_files)}")
        print(f"  Output files (json): {len(output_files)}")
        
        if not input_files:
            print(f"  ⚠️  Không tìm thấy dữ liệu!")
            continue
        
        # Build lookup by filename stem
        output_lookup = {}
        for f in output_files:
            output_lookup[f.stem] = f
        
        entity_types = Counter()
        styles = Counter()
        text_lengths = []
        entity_counts = []
        pos_total = 0
        pos_correct = 0
        pos_wrong = 0
        pos_oor = 0
        icd_codes = Counter()
        rxnorm_codes = Counter()
        candidate_has = 0
        candidate_empty = 0
        empty_text = 0
        empty_entities = 0
        
        for txt_file in input_files:
            # Read text
            try:
                text = txt_file.read_text(encoding="utf-8")
            except:
                try:
                    text = txt_file.read_text(encoding="utf-8-sig")
                except:
                    text = ""
            
            if not text.strip():
                empty_text += 1
                continue
            
            text_lengths.append(len(text))
            grand_text_lengths.append(len(text))
            
            # Classify style
            style = classify_style(text)
            styles[style] += 1
            grand_styles[style] += 1
            
            # Read corresponding JSON
            json_file = output_lookup.get(txt_file.stem)
            if not json_file or not json_file.exists():
                empty_entities += 1
                continue
            
            try:
                entities = json.loads(json_file.read_text(encoding="utf-8"))
            except:
                try:
                    entities = json.loads(json_file.read_text(encoding="utf-8-sig"))
                except:
                    entities = []
            
            if not isinstance(entities, list):
                entities = []
            
            entity_counts.append(len(entities))
            grand_entity_counts.append(len(entities))
            
            if len(entities) == 0:
                empty_entities += 1
            
            # Check position accuracy
            t, c, w, o = check_position_accuracy(text, entities)
            pos_total += t
            pos_correct += c
            pos_wrong += w
            pos_oor += o
            grand_pos_total += t
            grand_pos_correct += c
            grand_pos_wrong += w
            grand_pos_oor += o
            
            for ent in entities:
                etype = ent.get("type", "UNKNOWN")
                entity_types[etype] += 1
                grand_entity_types[etype] += 1
                
                candidates = ent.get("candidates", [])
                assertions = ent.get("assertions", [])
                
                # Track assertions
                for a in assertions:
                    grand_assertions_counter[a] += 1
                
                if candidates:
                    candidate_has += 1
                    grand_candidate_has += 1
                    grand_entity_type_details[etype]["has_candidates"] += 1
                    
                    for code in candidates:
                        if re.match(r'^[A-Z]\d', str(code)):
                            icd_codes[code] += 1
                            grand_icd_codes[code] += 1
                        elif str(code).isdigit():
                            rxnorm_codes[code] += 1
                            grand_rxnorm_codes[code] += 1
                else:
                    candidate_empty += 1
                    grand_candidate_empty += 1
                    grand_entity_type_details[etype]["no_candidates"] += 1
                
                # Sample entity texts
                if len(grand_entity_text_samples[etype]) < 5:
                    grand_entity_text_samples[etype].append(ent.get("text", "")[:60])
        
        grand_empty_text_count += empty_text
        grand_empty_entities_count += empty_entities
        
        # Print per-member summary
        print(f"\n  📊 Phân bổ phong cách văn bản:")
        for s, c in styles.most_common():
            pct = c / sum(styles.values()) * 100
            bar = "█" * int(pct / 2)
            print(f"    {s:15s}: {c:5d} ({pct:5.1f}%) {bar}")
        
        print(f"\n  📊 Phân bổ loại thực thể:")
        for t, c in entity_types.most_common():
            print(f"    {t:25s}: {c:5d}")
        
        if text_lengths:
            avg_len = sum(text_lengths) / len(text_lengths)
            print(f"\n  📏 Độ dài văn bản: min={min(text_lengths)}, max={max(text_lengths)}, avg={avg_len:.0f} ký tự")
        
        if entity_counts:
            avg_ent = sum(entity_counts) / len(entity_counts)
            print(f"  🏷️  Thực thể/mẫu: min={min(entity_counts)}, max={max(entity_counts)}, avg={avg_ent:.1f}")
        
        if pos_total > 0:
            acc = pos_correct / pos_total * 100
            print(f"  🎯 Position accuracy: {pos_correct}/{pos_total} ({acc:.1f}%) chính xác, {pos_wrong} sai, {pos_oor} out-of-range")
        
        print(f"  ⚠️  Empty text: {empty_text}, No entities: {empty_entities}")
    
    # ===== GRAND SUMMARY =====
    print(f"\n{'=' * 70}")
    print(f"  TỔNG HỢP TOÀN BỘ DỮ LIỆU")
    print(f"{'=' * 70}")
    
    total_samples = len(grand_text_lengths)
    print(f"\n  📁 Tổng số mẫu có nội dung: {total_samples}")
    print(f"  ⚠️  Mẫu rỗng/không entities: text rỗng={grand_empty_text_count}, không entities={grand_empty_entities_count}")
    
    print(f"\n  {'─' * 50}")
    print(f"  1. PHÂN BỔ PHONG CÁCH VĂN BẢN")
    print(f"  {'─' * 50}")
    for s, c in grand_styles.most_common():
        pct = c / sum(grand_styles.values()) * 100
        bar = "█" * int(pct / 2)
        print(f"    {s:15s}: {c:5d} ({pct:5.1f}%) {bar}")
    
    print(f"\n  {'─' * 50}")
    print(f"  2. PHÂN BỔ LOẠI THỰC THỂ")
    print(f"  {'─' * 50}")
    total_entities = sum(grand_entity_types.values())
    for t, c in grand_entity_types.most_common():
        pct = c / total_entities * 100
        has_c = grand_entity_type_details[t]["has_candidates"]
        no_c = grand_entity_type_details[t]["no_candidates"]
        cov_pct = has_c / (has_c + no_c) * 100 if (has_c + no_c) > 0 else 0
        print(f"    {t:25s}: {c:6d} ({pct:5.1f}%) | candidates: {cov_pct:5.1f}%")
        # Show samples
        samples = grand_entity_text_samples.get(t, [])
        if samples:
            print(f"      VD: {', '.join(samples[:3])}")
    
    print(f"\n  Tổng thực thể: {total_entities}")
    print(f"  Thực thể/mẫu trung bình: {total_entities/total_samples:.1f}" if total_samples > 0 else "")
    
    print(f"\n  {'─' * 50}")
    print(f"  3. ĐỘ DÀI VĂN BẢN")
    print(f"  {'─' * 50}")
    if grand_text_lengths:
        sorted_lens = sorted(grand_text_lengths)
        p25 = sorted_lens[len(sorted_lens) // 4]
        p50 = sorted_lens[len(sorted_lens) // 2]
        p75 = sorted_lens[3 * len(sorted_lens) // 4]
        avg = sum(sorted_lens) / len(sorted_lens)
        print(f"    Min: {min(sorted_lens):,} ký tự")
        print(f"    P25: {p25:,} ký tự")
        print(f"    P50 (Median): {p50:,} ký tự")
        print(f"    P75: {p75:,} ký tự")
        print(f"    Max: {max(sorted_lens):,} ký tự")
        print(f"    Trung bình: {avg:,.0f} ký tự")
        
        # Length distribution buckets
        buckets = {"<500": 0, "500-1000": 0, "1000-2000": 0, "2000-3000": 0, ">3000": 0}
        for l in sorted_lens:
            if l < 500: buckets["<500"] += 1
            elif l < 1000: buckets["500-1000"] += 1
            elif l < 2000: buckets["1000-2000"] += 1
            elif l < 3000: buckets["2000-3000"] += 1
            else: buckets[">3000"] += 1
        print(f"\n    Phân bổ độ dài:")
        for b, c in buckets.items():
            pct = c / len(sorted_lens) * 100
            bar = "█" * int(pct / 2)
            print(f"      {b:12s}: {c:5d} ({pct:5.1f}%) {bar}")
    
    print(f"\n  {'─' * 50}")
    print(f"  4. POSITION MAPPING ACCURACY")
    print(f"  {'─' * 50}")
    if grand_pos_total > 0:
        acc = grand_pos_correct / grand_pos_total * 100
        print(f"    Tổng thực thể kiểm tra: {grand_pos_total:,}")
        print(f"    ✅ Chính xác: {grand_pos_correct:,} ({acc:.1f}%)")
        print(f"    ❌ Sai: {grand_pos_wrong:,} ({grand_pos_wrong/grand_pos_total*100:.1f}%)")
        print(f"    ⚠️  Out-of-range: {grand_pos_oor:,} ({grand_pos_oor/grand_pos_total*100:.1f}%)")
    
    print(f"\n  {'─' * 50}")
    print(f"  5. CANDIDATE CODE COVERAGE")
    print(f"  {'─' * 50}")
    total_cand = grand_candidate_has + grand_candidate_empty
    if total_cand > 0:
        print(f"    Có candidates: {grand_candidate_has:,} ({grand_candidate_has/total_cand*100:.1f}%)")
        print(f"    Không có candidates: {grand_candidate_empty:,} ({grand_candidate_empty/total_cand*100:.1f}%)")
        print(f"    Mã ICD-10 duy nhất: {len(grand_icd_codes):,}")
        print(f"    Mã RxNorm duy nhất: {len(grand_rxnorm_codes):,}")
        
        print(f"\n    Top 15 ICD-10 phổ biến nhất:")
        for code, count in grand_icd_codes.most_common(15):
            print(f"      {code:10s}: {count:4d}")
        
        print(f"\n    Top 15 RxNorm phổ biến nhất:")
        for code, count in grand_rxnorm_codes.most_common(15):
            print(f"      {code:10s}: {count:4d}")
    
    print(f"\n  {'─' * 50}")
    print(f"  6. ASSERTIONS")
    print(f"  {'─' * 50}")
    if grand_assertions_counter:
        for a, c in grand_assertions_counter.most_common():
            print(f"    {a:25s}: {c:5d}")
    else:
        print(f"    Không có assertions nào được ghi nhận.")
    
    print(f"\n  {'─' * 50}")
    print(f"  7. SỐ LƯỢNG THỰC THỂ MỖI MẪU")
    print(f"  {'─' * 50}")
    if grand_entity_counts:
        ent_buckets = {"0": 0, "1-3": 0, "4-6": 0, "7-10": 0, ">10": 0}
        for c in grand_entity_counts:
            if c == 0: ent_buckets["0"] += 1
            elif c <= 3: ent_buckets["1-3"] += 1
            elif c <= 6: ent_buckets["4-6"] += 1
            elif c <= 10: ent_buckets["7-10"] += 1
            else: ent_buckets[">10"] += 1
        for b, c in ent_buckets.items():
            pct = c / len(grand_entity_counts) * 100
            bar = "█" * int(pct / 2)
            print(f"    {b:8s}: {c:5d} ({pct:5.1f}%) {bar}")
    
    print(f"\n{'=' * 70}")
    print(f"  KẾT THÚC EDA")
    print(f"{'=' * 70}")

if __name__ == "__main__":
    run_eda()

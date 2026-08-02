import os
import json
import sys
import re
import unicodedata
from pathlib import Path

# Ensure UTF-8 printing
sys.stdout.reconfigure(encoding='utf-8')

# Resolve paths
PIPELINE_DIR = Path(__file__).parent
BASE_DIR = PIPELINE_DIR.parent
sys.path.append(str(PIPELINE_DIR))

from ensemble_merger import merge_entities
from hybrid_linker import HybridLinker
from phobert_predictor import clean_and_validate_entity

def validate_and_align_positions(entities, original_text):
    valid_entities = []
    for ent in entities:
        text = ent.get("text", "").strip()
        if not text:
            continue
            
        pos = ent.get("position")
        if not pos or not isinstance(pos, list) or len(pos) < 2 or pos[0] is None or pos[1] is None:
            llm_start = 0
        else:
            llm_start = pos[0]
            
        # 1. Khớp chính xác (Case Insensitive)
        pattern = re.escape(text)
        matches = list(re.finditer(pattern, original_text, re.IGNORECASE))
        if matches:
            best_match = min(matches, key=lambda m: abs(m.start() - llm_start))
            start_idx, end_idx = best_match.start(), best_match.end()
            ent["text"] = original_text[start_idx:end_idx]
            ent["position"] = [start_idx, end_idx]
            valid_entities.append(ent)
            continue
            
        # 2. Chuẩn hóa NFC (Sửa lỗi lệch NFD/NFC của văn bản gốc)
        doc_nfc = unicodedata.normalize("NFC", original_text)
        text_nfc = unicodedata.normalize("NFC", text)
        matches_nfc = list(re.finditer(re.escape(text_nfc), doc_nfc, re.IGNORECASE))
        if matches_nfc:
            best_match_nfc = min(matches_nfc, key=lambda m: abs(m.start() - llm_start))
            start_nfc, end_nfc = best_match_nfc.start(), best_match_nfc.end()
            
            import difflib
            matcher = difflib.SequenceMatcher(None, doc_nfc, original_text)
            matching_blocks = matcher.get_matching_blocks()
            
            def map_index(idx):
                for a, b, size in matching_blocks:
                    if a <= idx <= a + size:
                        return b + (idx - a)
                return idx
                
            start_idx, end_idx = map_index(start_nfc), map_index(end_nfc)
            ent["text"] = original_text[start_idx:end_idx]
            ent["position"] = [start_idx, end_idx]
            valid_entities.append(ent)
            continue
            
        # 3. Tìm kiếm mờ (Fuzzy Search) để sửa lỗi chính tả/từ đồng nghĩa từ LLM
        window_start = max(0, llm_start - 80)
        window_end = min(len(original_text), llm_start + len(text) + 80)
        window_text = original_text[window_start:window_end]
        
        import difflib
        best_ratio = 0.0
        best_pos = None
        
        n = len(text)
        for length in range(max(1, n - 15), min(len(window_text), n + 15) + 1):
            for start in range(0, len(window_text) - length + 1):
                sub = window_text[start:start+length]
                ratio = difflib.SequenceMatcher(None, text.lower(), sub.lower()).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_pos = (window_start + start, window_start + start + length)
                    
        if best_ratio >= 0.70 and best_pos is not None:
            start_idx, end_idx = best_pos
            ent["text"] = original_text[start_idx:end_idx]
            ent["position"] = [start_idx, end_idx]
            valid_entities.append(ent)
            continue
            
        # Loại bỏ nếu không khớp và không tìm thấy trong văn bản gốc
        print(f"  [Lưu ý] Đã loại bỏ thực thể ảo giác của Qwen: '{text}'")
        
    return valid_entities

def deduplicate_entities(entities):
    """
    Loại bỏ các thực thể trùng lặp hoàn toàn (cùng vị trí và nhãn)
    hoặc trùng vị trí nhưng khác nhãn (chỉ giữ lại nhãn có độ ưu tiên cao hơn).
    """
    type_priority = {
        "CHẨN_ĐOÁN": 5,
        "THUỐC": 4,
        "TRIỆU_CHỨNG": 3,
        "TÊN_XÉT_NGHIỆM": 2,
        "KẾT_QUẢ_XÉT_NGHIỆM": 1
    }
    
    seen = {}
    for ent in entities:
        pos = ent.get("position", [0, 0])
        key = (pos[0], pos[1])
        
        if key not in seen:
            seen[key] = ent
        else:
            existing_ent = seen[key]
            existing_type = existing_ent.get("type", "")
            current_type = ent.get("type", "")
            
            p_existing = type_priority.get(existing_type, 0)
            p_current = type_priority.get(current_type, 0)
            
            if p_current > p_existing:
                seen[key] = ent
            elif p_current == p_existing:
                existing_cands = existing_ent.get("candidates", [])
                current_cands = ent.get("candidates", [])
                if len(current_cands) > len(existing_cands):
                    seen[key] = ent
                    
    deduped_list = list(seen.values())
    deduped_list.sort(key=lambda x: x.get("position", [0, 0])[0])
    return deduped_list

def main():
    INPUT_DIR = BASE_DIR / "input_turn2_vong1" / "input"
    QWEN_DIR = BASE_DIR / "finetune_qwen_7b" / "submissionv3"
    PHOBERT_DIR = BASE_DIR / "input_turn2_vong1" / "output"
    MERGED_DIR = BASE_DIR / "input_turn2_vong1" / "output_merged_v1"
    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("  QUÁ TRÌNH MERGE VÀ CHUẨN HÓA CSDL SUBMISSION V1 (QWEN + PHOBERT)")
    print("=" * 80)
    print(f"Thư mục nguồn Qwen (v3):    {QWEN_DIR}")
    print(f"Thư mục nguồn PhoBERT:      {PHOBERT_DIR}")
    print(f"Thư mục đích đầu ra:        {MERGED_DIR}")
    
    linker = HybridLinker(use_semantic=True)
    
    txt_files = sorted(list(INPUT_DIR.glob("*.txt")), key=lambda x: int(x.stem) if x.stem.isdigit() else 9999)
    print(f"\nTìm thấy {len(txt_files)} tệp văn bản. Bắt đầu gộp và đối chiếu...")
    
    for f in txt_files:
        name = f.stem
        text_orig = f.read_text(encoding="utf-8")
        
        # Load Qwen entities
        qwen_f = QWEN_DIR / f"{name}.json"
        qwen_ents = []
        if qwen_f.exists():
            try:
                qwen_ents = json.loads(qwen_f.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"⚠️ Lỗi đọc file Qwen {qwen_f.name}: {e}")
                
        # Load PhoBERT entities
        phobert_f = PHOBERT_DIR / f"{name}.json"
        phobert_ents = []
        if phobert_f.exists():
            try:
                phobert_ents = json.loads(phobert_f.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"⚠️ Lỗi đọc file PhoBERT {phobert_f.name}: {e}")
                
        # Xác thực và cân chỉnh vị trí của Qwen
        valid_qwen = validate_and_align_positions(qwen_ents, text_orig)
        
        # Merge thực thể (Ensemble Merger)
        merged_ents = merge_entities(valid_qwen, phobert_ents)
        
        # Loại bỏ trùng lặp ranh giới và nhãn
        merged_ents = deduplicate_entities(merged_ents)
        
        # Ánh xạ mã ICD-10 và RxNorm từ CSDL chuẩn hóa + làm sạch thực thể nâng cao
        cleaned_merged_ents = []
        for ent in merged_ents:
            pos = ent.get("position", [0, 0])
            cleaned = clean_and_validate_entity(text_orig, pos[0], pos[1], ent.get("type"))
            if cleaned:
                # Bảo toàn các trường thông tin bổ trợ như assertions
                cleaned["assertions"] = ent.get("assertions", [])
                
                etype = cleaned.get("type")
                if etype in ["CHẨN_ĐOÁN", "THUỐC"]:
                    text_val = cleaned.get("text")
                    codes = linker.link_entity(text_val, etype)
                    if not codes:
                        # Fallback to LLM's own candidate codes (clean '*' and '†')
                        llm_codes = ent.get("candidates", [])
                        if llm_codes:
                            codes = [c.replace('*', '').replace('†', '').strip() for c in llm_codes if c]
                    cleaned["candidates"] = codes
                else:
                    cleaned["candidates"] = []
                    
                cleaned_merged_ents.append(cleaned)
                
        merged_ents = cleaned_merged_ents
                
        # Ghi kết quả
        out_f = MERGED_DIR / f"{name}.json"
        with open(out_f, "w", encoding="utf-8") as out_file:
            json.dump(merged_ents, out_file, ensure_ascii=False, indent=2)
            
        print(f"  -> Đã gộp và ghi kết quả: {out_f.name}")
        
    linker.close()
    print("\n🎉 Gộp và ánh xạ CSDL cho 100 tệp thành công! Kết quả lưu tại: input_turn2_vong1/output_merged_v1")

if __name__ == "__main__":
    main()

import os
import json
import sys
import re
from pathlib import Path

# Ensure UTF-8 printing
sys.stdout.reconfigure(encoding='utf-8')

# Resolve paths
PIPELINE_DIR = Path(__file__).parent
BASE_DIR = PIPELINE_DIR.parent
sys.path.append(str(PIPELINE_DIR))

from ensemble_merger import merge_entities
from hybrid_linker import HybridLinker

def validate_and_align_positions(entities, original_text):
    valid_entities = []
    for ent in entities:
        text = ent.get("text", "").strip()
        if not text:
            continue
            
        pos = ent.get("position")
        if not pos or not isinstance(pos, list) or len(pos) < 2 or pos[0] is None or pos[1] is None:
            # Nếu thiếu vị trí hoặc vị trí lỗi, tìm kiếm vị trí xuất hiện trong văn bản gốc
            match = re.search(re.escape(text), original_text, re.IGNORECASE)
            if match:
                pos = [match.start(), match.end()]
            else:
                # Không tìm thấy -> Bỏ qua thực thể ảo giác
                continue
                
        start, end = pos[0], pos[1]
        
        # 1. Kiểm tra khớp chính xác vị trí
        sub_text = original_text[start:end].strip()
        if sub_text.lower() == text.lower():
            ent["text"] = sub_text
            ent["position"] = [start, end]
            valid_entities.append(ent)
            continue
            
        # 2. Tìm khớp hoàn hảo ở vị trí khác trong văn bản
        matches = [m.start() for m in re.finditer(re.escape(text), original_text, re.IGNORECASE)]
        if matches:
            closest_start = min(matches, key=lambda x: abs(x - start))
            new_end = closest_start + len(text)
            ent["position"] = [closest_start, new_end]
            ent["text"] = original_text[closest_start:new_end]
            valid_entities.append(ent)
            continue
            
        # 3. Tìm khớp mờ trong cửa sổ trượt hẹp
        search_start = max(0, start - 30)
        search_end = min(len(original_text), end + 30)
        window_text = original_text[search_start:search_end]
        
        match_in_window = re.search(re.escape(text), window_text, re.IGNORECASE)
        if match_in_window:
            new_start = search_start + match_in_window.start()
            new_end = new_start + len(text)
            ent["position"] = [new_start, new_end]
            ent["text"] = original_text[new_start:new_end]
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
    
    linker = HybridLinker(use_semantic=False)
    
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
        
        # Ánh xạ mã ICD-10 và RxNorm từ CSDL chuẩn hóa
        for ent in merged_ents:
            etype = ent.get("type", "")
            if etype in ["CHẨN_ĐOÁN", "THUỐC"]:
                text_val = ent.get("text", "")
                codes = linker.link_entity(text_val, etype)
                ent["candidates"] = codes
                
        # Ghi kết quả
        out_f = MERGED_DIR / f"{name}.json"
        with open(out_f, "w", encoding="utf-8") as out_file:
            json.dump(merged_ents, out_file, ensure_ascii=False, indent=2)
            
        print(f"  -> Đã gộp và ghi kết quả: {out_f.name}")
        
    linker.close()
    print("\n🎉 Gộp và ánh xạ CSDL cho 100 tệp thành công! Kết quả lưu tại: input_turn2_vong1/output_merged_v1")

if __name__ == "__main__":
    main()

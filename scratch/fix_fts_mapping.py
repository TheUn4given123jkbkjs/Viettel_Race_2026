"""
Sửa lỗi ánh xạ FTS: Khi thực thể chỉ ghi "Tăng huyết áp" thuần túy,
chỉ giữ lại I10, loại bỏ I11/I67.4 khỏi candidates.
Chỉ giữ I11 khi văn bản có ngữ cảnh suy tim/phì đại thất.
Chỉ giữ I67.4 khi văn bản có ngữ cảnh mạch máu não/xuất huyết não.
"""
import os, json, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIRS = ["sample_A", "sample_C", "sample_Long"]

# Ngữ cảnh cho I11 (Bệnh tim do THA)
I11_CONTEXT = re.compile(
    r'(suy tim|phì đại thất|bệnh tim|suy chức năng tim|nhồi máu cơ tim'
    r'|bệnh cơ tim|thiếu máu cơ tim|đau thắt ngực|hẹp van|hở van'
    r'|rung nhĩ|loạn nhịp|block nhĩ thất)', re.IGNORECASE
)

# Ngữ cảnh cho I67.4 (Bệnh lý não do THA)
I674_CONTEXT = re.compile(
    r'(mạch máu não|xuất huyết não|nhồi máu não|đột quỵ|tai biến'
    r'|thiếu máu não|bệnh lý não|não do tăng huyết áp|encephalopathy'
    r'|não tăng huyết áp)', re.IGNORECASE
)

def compact_json_format(data):
    s = json.dumps(data, ensure_ascii=False, indent=2)
    s = re.sub(r'\[\s*\n\s*(\d+),\s*\n\s*(\d+)\s*\n\s*\]', r'[\1, \2]', s)
    s = re.sub(r'\[\s*\n\s*\]', r'[]', s)
    s = re.sub(r'\[\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1"]', s)
    s = re.sub(r'\[\s*\n\s*"([^"]+)",\s*\n\s*"([^"]+)"\s*\n\s*\]', r'["\1", "\2"]', s)
    return s

def fix_hypertension_candidates(entities, full_text):
    """Sửa candidates cho các thực thể liên quan THA."""
    modified = False
    for ent in entities:
        if ent.get("type") != "CHẨN_ĐOÁN":
            continue
        candidates = ent.get("candidates", [])
        if not candidates:
            continue
        
        has_i10 = "I10" in candidates
        has_i11 = "I11" in candidates
        has_i674 = "I67.4" in candidates
        
        # Chỉ xử lý nếu có ít nhất 2 trong 3 mã THA
        if sum([has_i10, has_i11, has_i674]) < 2:
            continue
        
        ent_text = ent.get("text", "").lower()
        
        # Kiểm tra xem thực thể có thực sự là về biến chứng tim hay não không
        text_has_heart = bool(I11_CONTEXT.search(ent_text)) or bool(I11_CONTEXT.search(full_text))
        text_has_brain = bool(I674_CONTEXT.search(ent_text)) or bool(I674_CONTEXT.search(full_text))
        
        new_candidates = []
        
        # Luôn giữ I10 nếu có
        if has_i10:
            new_candidates.append("I10")
        
        # Chỉ giữ I11 nếu có ngữ cảnh tim
        if has_i11 and text_has_heart:
            new_candidates.append("I11")
        
        # Chỉ giữ I67.4 nếu có ngữ cảnh não
        if has_i674 and text_has_brain:
            new_candidates.append("I67.4")
        
        # Giữ nguyên các mã không phải THA
        for c in candidates:
            if c not in ("I10", "I11", "I67.4") and c not in new_candidates:
                new_candidates.append(c)
        
        if not new_candidates and has_i10:
            new_candidates = ["I10"]
        
        if new_candidates != candidates:
            ent["candidates"] = new_candidates
            modified = True
    
    return modified

def main():
    total_files = 0
    total_modified = 0
    stats = {"I11_removed": 0, "I674_removed": 0, "I11_kept": 0, "I674_kept": 0}
    
    print("=" * 60)
    print("  SỬA LỖI ÁNH XẠ FTS: PHÂN TÁCH BIẾN CHỨNG THA")
    print("=" * 60)
    
    for s_dir in SAMPLE_DIRS:
        print(f"\n📂 {s_dir}...")
        input_root = BASE_DIR / s_dir / "input"
        output_root = BASE_DIR / s_dir / "output"
        
        if not output_root.exists():
            continue
        
        json_files = sorted(output_root.rglob("*.json"))
        modified_count = 0
        
        for jf in json_files:
            total_files += 1
            
            # Đọc JSON
            try:
                entities = json.loads(jf.read_text(encoding="utf-8"))
            except:
                try:
                    entities = json.loads(jf.read_text(encoding="utf-8-sig"))
                except:
                    continue
            
            if not isinstance(entities, list):
                continue
            
            # Đọc file text tương ứng để kiểm tra ngữ cảnh
            # Tìm file txt tương ứng (cùng tên, cùng part)
            rel = jf.relative_to(output_root)
            txt_path = input_root / rel.parent / (jf.stem + ".txt")
            full_text = ""
            if txt_path.exists():
                try:
                    full_text = txt_path.read_text(encoding="utf-8")
                except:
                    try:
                        full_text = txt_path.read_text(encoding="utf-8-sig")
                    except:
                        pass
            
            # Đếm trước sửa
            before_i11 = sum(1 for e in entities if "I11" in e.get("candidates", []))
            before_i674 = sum(1 for e in entities if "I67.4" in e.get("candidates", []))
            
            if fix_hypertension_candidates(entities, full_text):
                # Đếm sau sửa
                after_i11 = sum(1 for e in entities if "I11" in e.get("candidates", []))
                after_i674 = sum(1 for e in entities if "I67.4" in e.get("candidates", []))
                
                stats["I11_removed"] += (before_i11 - after_i11)
                stats["I11_kept"] += after_i11
                stats["I674_removed"] += (before_i674 - after_i674)
                stats["I674_kept"] += after_i674
                
                formatted = compact_json_format(entities)
                jf.write_text(formatted, encoding="utf-8")
                modified_count += 1
                total_modified += 1
        
        print(f"   Sửa đổi: {modified_count}/{len(json_files)} files")
    
    print(f"\n{'=' * 60}")
    print(f"  KẾT QUẢ")
    print(f"{'=' * 60}")
    print(f"  Tổng files quét: {total_files}")
    print(f"  Tổng files sửa: {total_modified}")
    print(f"  I11 bị loại bỏ: {stats['I11_removed']} (giữ lại: {stats['I11_kept']})")
    print(f"  I67.4 bị loại bỏ: {stats['I674_removed']} (giữ lại: {stats['I674_kept']})")

if __name__ == "__main__":
    main()

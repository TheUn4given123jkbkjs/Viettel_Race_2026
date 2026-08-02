import os
import json
import sqlite3
import sys
from pathlib import Path

# Add pipeline to path
sys.path.append(str(Path(__file__).parent.parent / "pipeline"))
try:
    from hybrid_linker import HybridLinker
except ImportError:
    sys.path.append(str(Path(__file__).parent.parent))
    from pipeline.hybrid_linker import HybridLinker

V4_DIR = Path(r"d:\AI Race\Viettel_Race_2026\finetune_qwen_7b\submission_v4")
V5_DIR = Path(r"d:\AI Race\Viettel_Race_2026\finetune_qwen_7b\submisstionv5")
DB_PATH = Path(r"d:\AI Race\Viettel_Race_2026\db\medical_codes.db")

def compare():
    print("======================================================================")
    print("📊 SO SÁNH CHI TIẾT SUBMISSION V4 VS SUBMISSION V5 (10 FILE TEST ĐẦU)")
    print("======================================================================\n")

    linker = HybridLinker(db_path=DB_PATH, use_semantic=False)

    for i in range(1, 11):
        fname = f"{i}.json"
        f4 = V4_DIR / fname
        f5 = V5_DIR / fname
        
        print(f"--- 📄 Tệp tin: {fname} ---")
        
        if not f4.exists():
            print(f"  ❌ File V4 {fname} không tồn tại.")
            continue
        if not f5.exists():
            print(f"  ❌ File V5 {fname} không tồn tại.")
            continue
            
        with open(f4, "r", encoding="utf-8") as f:
            ents4 = json.load(f)
        with open(f5, "r", encoding="utf-8") as f:
            ents5 = json.load(f)
            
        print(f"  * Số thực thể ở V4: {len(ents4)}")
        print(f"  * Số thực thể ở V5: {len(ents5)}")
        
        # Tạo map để đối chiếu
        map4 = { (ent.get("text"), ent.get("type")): ent for ent in ents4 }
        map5 = { (ent.get("text"), ent.get("type")): ent for ent in ents5 }
        
        # 1. Các thực thể mới xuất hiện ở V5 (hoặc được sửa vị trí thành công)
        new_ents = []
        for k, ent5 in map5.items():
            if k not in map4:
                new_ents.append(ent5)
                
        # 2. Các thực thể bị mất ở V5 (hoặc bị loại bỏ)
        missing_ents = []
        for k, ent4 in map4.items():
            if k not in map5:
                missing_ents.append(ent4)
                
        # 3. Các thực thể có cùng text + type nhưng thay đổi mã candidates hoặc vị trí
        modified_ents = []
        for k, ent5 in map5.items():
            if k in map4:
                ent4 = map4[k]
                c4 = ent4.get("candidates", [])
                c5 = ent5.get("candidates", [])
                p4 = ent4.get("position", [])
                p5 = ent5.get("position", [])
                if c4 != c5 or p4 != p5:
                    modified_ents.append((ent4, ent5))
                    
        if new_ents:
            print("  🟢 Thực thể mới được định vị/thêm vào V5:")
            for ent in new_ents:
                print(f"    - [{ent['type']}] '{ent['text']}' tại {ent['position']} | Codes: {ent['candidates']}")
                
        if missing_ents:
            print("  🔴 Thực thể bị loại bỏ trong V5 (Có thể do lỗi lọc cũ):")
            for ent in missing_ents:
                print(f"    - [{ent['type']}] '{ent['text']}' tại {ent['position']} | Codes: {ent['candidates']}")
                
        if modified_ents:
            print("  🔵 Thực thể thay đổi Mã candidates hoặc Vị trí:")
            for ent4, ent5 in modified_ents:
                c4_str = f"{ent4['candidates']}"
                c5_str = f"{ent5['candidates']}"
                p4_str = f"{ent4['position']}"
                p5_str = f"{ent5['position']}"
                
                change_parts = []
                if ent4['position'] != ent5['position']:
                    change_parts.append(f"Vị trí: {p4_str} ➔ {p5_str}")
                if ent4['candidates'] != ent5['candidates']:
                    change_parts.append(f"Mã: {c4_str} ➔ {c5_str}")
                    
                print(f"    - [{ent5['type']}] '{ent5['text']}': {', '.join(change_parts)}")
        
        print()
        
    linker.close()

if __name__ == "__main__":
    compare()

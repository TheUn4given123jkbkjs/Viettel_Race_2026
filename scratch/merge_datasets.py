import os
import json
import sys
from pathlib import Path

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIRS = ["sample_A", "sample_C", "sample_Long", "sample_D", "sample_E"]
OUTPUT_FILE = BASE_DIR / "train_clean.json"

PROMPT_TEMPLATE = """Bạn là một chuyên gia y tế AI. Hãy phân tích đoạn văn bản lâm sàng tiếng Việt sau đây, trích xuất tất cả các thực thể y tế và trả về dưới dạng một danh sách JSON.

Với mỗi thực thể, bạn cần xác định:
1. `text`: Đoạn văn bản chính xác của thực thể.
2. `position`: Vị trí ký tự bắt đầu và kết thúc [start, end] trong văn bản gốc.
3. `type`: Nhãn thực thể, nhận một trong các giá trị: TRIỆU_CHỨNG, TÊN_XÉT_NGHIỆM, KẾT_QUẢ_XÉT_NGHIỆM, CHẨN_ĐOÁN, THUỐC.
4. `assertions`: Mảng các thuộc tính ngữ cảnh (chỉ dành cho TRIỆU_CHỨNG, CHẨN_ĐOÁN, THUỐC), có thể chứa các nhãn: "isNegated", "isHistorical", "isFamily".
5. `candidates`: Mảng chứa mã chuẩn hóa (ICD-10 cho CHẨN_ĐOÁN, RxNorm cho THUỐC).

Văn bản lâm sàng:
\"\"\"
{text}
\"\"\""""

def main():
    print("=" * 80)
    print("  BẮT ĐẦU TIẾN TRÌNH GỘP VÀ LÀM SẠCH DỮ LIỆU HUẤN LUYỆN (P4)")
    print("=" * 80)
    
    merged_data = []
    total_files = 0
    total_entities = 0
    
    for s_dir in SAMPLE_DIRS:
        input_dir = BASE_DIR / s_dir / "input"
        output_dir = BASE_DIR / s_dir / "output"
        
        if not input_dir.exists() or not output_dir.exists():
            print(f"Bỏ qua {s_dir} vì không tìm thấy thư mục.")
            continue
            
        print(f"Đang xử lý thư mục: {s_dir}...")
        
        # Scan files using os.scandir for speed
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
                
        ds_processed = 0
        
        for f in txt_files:
            try:
                text = f.read_text(encoding="utf-8").strip()
            except:
                text = f.read_text(encoding="utf-8-sig", errors="replace").strip()
                
            jf = json_lookup.get(f.stem)
            if not jf or not jf.exists():
                continue
                
            try:
                entities = json.loads(jf.read_text(encoding="utf-8"))
            except:
                entities = json.loads(jf.read_text(encoding="utf-8-sig", errors="replace"))
                
            # Basic validation of data structure
            if not isinstance(entities, list):
                continue
                
            clean_entities = []
            for ent in entities:
                if not isinstance(ent, dict):
                    continue
                # Ensure all 5 required fields are present with correct defaults
                clean_ent = {
                    "text": ent.get("text", ""),
                    "position": ent.get("position", [0, 0]),
                    "type": ent.get("type", "UNKNOWN"),
                    "assertions": ent.get("assertions", []),
                    "candidates": ent.get("candidates", [])
                }
                clean_entities.append(clean_ent)
                total_entities += 1
                
            # Create conversation structure (ShareGPT format)
            human_prompt = PROMPT_TEMPLATE.format(text=text)
            gpt_response = json.dumps(clean_entities, ensure_ascii=False, indent=2)
            
            conversation = {
                "conversations": [
                    {
                        "from": "human",
                        "value": human_prompt
                    },
                    {
                        "from": "gpt",
                        "value": gpt_response
                    }
                ]
            }
            
            merged_data.append(conversation)
            ds_processed += 1
            total_files += 1
            
        print(f"  -> Xử lý thành công {ds_processed} file từ {s_dir}.")
        
    print("-" * 80)
    print(f"Tổng số bệnh án gộp thành công: {total_files}")
    print(f"Tổng số thực thể NER tương ứng: {total_entities}")
    
    # Save the merged dataset
    print(f"Đang ghi kết quả ra tệp {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out_f:
        json.dump(merged_data, out_f, ensure_ascii=False, indent=2)
        
    print("✅ Hoàn thành gộp dữ liệu thành công!")

if __name__ == "__main__":
    main()

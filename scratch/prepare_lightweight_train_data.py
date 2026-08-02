import json
import os
import re
import sys
import unicodedata
from pathlib import Path

# Ensure UTF-8 printing
sys.stdout.reconfigure(encoding='utf-8')

# Thư mục gốc dự án
BASE_DIR = Path(__file__).parent.parent
TRAIN_DATA_PATH = BASE_DIR / "train_clean.json"
OUTPUT_DATA_PATH = BASE_DIR / "train_clean_lightweight.json"

def align_text_to_source(original_text, entity_text, start_idx, end_idx):
    """
    Nếu nhãn bị lệch ký tự/chính tả so với văn bản gốc (do người dán chuẩn hóa sẵn),
    ta tự động sửa text của nhãn về đúng từng ký tự trong văn bản gốc.
    """
    if start_idx is not None and end_idx is not None and start_idx < end_idx:
        # Cắt chính xác chuỗi con trong văn bản gốc ở tọa độ đó
        source_sub = original_text[start_idx:end_idx].strip()
        if source_sub:
            return source_sub
            
    # Fallback nếu không có tọa độ hoặc lỗi: Dò tìm exact-match gần nhất
    pattern = re.escape(entity_text)
    matches = list(re.finditer(pattern, original_text, re.IGNORECASE))
    if matches:
        # Lấy khớp đầu tiên
        return original_text[matches[0].start():matches[0].end()]
        
    return entity_text

def extract_doc_text(human_value):
    """Trích xuất văn bản lâm sàng nằm trong cặp dấu ba nháy kép ở cuối prompt."""
    parts = human_value.split('\"\"\"')
    if len(parts) >= 3:
        # Lấy phần nằm giữa cặp ba nháy kép thứ hai từ dưới lên
        return parts[-2].strip()
    return human_value

def prepare_data():
    print("=" * 80)
    print("🚀 TIỀN XỬ LÝ DỮ LIỆU HUẤN LUYỆN - KIẾN TRÚC RÚT GỌN (DATASET ALIGNMENT)")
    print("=" * 80)
    
    if not TRAIN_DATA_PATH.exists():
        print(f"❌ Không tìm thấy tệp tin: {TRAIN_DATA_PATH}")
        return
        
    print(f"-> Đang đọc dữ liệu gốc từ: {TRAIN_DATA_PATH.name}...")
    with open(TRAIN_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"-> Bắt đầu làm sạch và căn chỉnh thực thể cho {len(data)} mẫu dữ liệu hội thoại...")
    
    lightweight_data = []
    aligned_count = 0
    total_ents_count = 0
    
    for item in data:
        conversations = item.get("conversations", [])
        if len(conversations) < 2:
            lightweight_data.append(item)
            continue
            
        human_item = conversations[0]
        gpt_item = conversations[1]
        
        doc_text = extract_doc_text(human_item.get("value", ""))
        
        try:
            entities = json.loads(gpt_item.get("value", "[]"))
        except Exception as e:
            print(f"⚠️ Lỗi parse JSON thực thể ở một mẫu: {e}")
            lightweight_data.append(item)
            continue
            
        cleaned_entities = []
        for ent in entities:
            total_ents_count += 1
            text = ent.get("text", "").strip()
            etype = ent.get("type", "").strip()
            assertions = ent.get("assertions", [])
            pos = ent.get("position", [None, None])
            
            # Căn chỉnh text nhãn về đúng 100% chuỗi con trong văn bản gốc
            aligned_text = align_text_to_source(doc_text, text, pos[0], pos[1])
            if aligned_text.lower() != text.lower():
                aligned_count += 1
                
            # Tạo nhãn rút gọn (Chỉ giữ lại text, type và assertions)
            cleaned_ent = {
                "text": aligned_text,
                "type": etype,
                "assertions": assertions
            }
            cleaned_entities.append(cleaned_ent)
            
        # Cập nhật lại giá trị phản hồi của GPT dưới dạng JSON rút gọn
        new_gpt_value = json.dumps(cleaned_entities, ensure_ascii=False, indent=2)
        
        new_conversations = [
            {"from": "human", "value": human_item.get("value", "")},
            {"from": "gpt", "value": new_gpt_value}
        ]
        
        lightweight_data.append({
            "conversations": new_conversations
        })
        
    # Ghi kết quả ra tệp tin mới
    with open(OUTPUT_DATA_PATH, "w", encoding="utf-8") as out_file:
        json.dump(lightweight_data, out_file, ensure_ascii=False, indent=2)
        
    print("\n" + "=" * 40)
    print("📊 BÁO CÁO KẾT QUẢ TIỀN XỬ LÝ")
    print("=" * 40)
    print(f"Tổng số mẫu văn bản xử lý : {len(lightweight_data)}")
    print(f"Tổng số thực thể đã duyệt : {total_ents_count}")
    print(f"Số lượng nhãn được căn chỉnh chính tả về gốc : {aligned_count}")
    print(f"Đường dẫn lưu kết quả mới : {OUTPUT_DATA_PATH}")
    print("=" * 80)

if __name__ == "__main__":
    prepare_data()

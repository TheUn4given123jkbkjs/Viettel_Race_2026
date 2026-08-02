import os
import json
import glob
import sys
import numpy as np

# Ensure UTF-8 output
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

SUBMISSION_DIR = r"D:\AI Race\Viettel_Race_2026\submissionv3"
INPUT_DIR = r"D:\AI Race\Viettel_Race_2026\input_turn2_vong1\input"
TRAIN_PATH = "train_clean.json"

def diagnostic():
    # 1. Read test documents and submission files
    json_files = glob.glob(os.path.join(SUBMISSION_DIR, "*.json"))
    if not json_files:
        print("No json files found in submission.")
        return
        
    test_lengths = []
    entity_counts = []
    masked_text_predicted = 0
    masked_text_in_test = 0
    asterisk_candidates_count = 0
    duplicate_coords_count = 0
    
    type_counts = {}
    
    for j_path in json_files:
        fname = os.path.basename(j_path)
        txt_path = os.path.join(INPUT_DIR, fname.replace(".json", ".txt"))
        
        doc_text = ""
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                doc_text = f.read()
        
        test_lengths.append(len(doc_text.split())) # length in words
        
        # Count masked words in test text
        masked_text_in_test += len(re.findall(r'\*+', doc_text))
        
        with open(j_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        entity_counts.append(len(data))
        
        seen_positions = set()
        for ent in data:
            etype = ent.get("type", "")
            text = ent.get("text", "")
            pos = tuple(ent.get("position", [0, 0]))
            candidates = ent.get("candidates", [])
            
            type_counts[etype] = type_counts.get(etype, 0) + 1
            
            if "*" in text:
                masked_text_predicted += 1
                
            for c in candidates:
                if "*" in c or "†" in c:
                    asterisk_candidates_count += 1
                    
            if pos in seen_positions:
                duplicate_coords_count += 1
            seen_positions.add(pos)
            
    # 2. Read train documents
    train_lengths = []
    if os.path.exists(TRAIN_PATH):
        with open(TRAIN_PATH, "r", encoding="utf-8") as f:
            train_data = json.load(f)
        for item in train_data:
            convs = item.get("conversations", [])
            user_val = ""
            for msg in convs:
                if msg["from"] == "human":
                    user_val = msg["value"]
                    break
            # Extract text from human prompt
            match = re.search(r'Văn bản lâm sàng:\s*"""(.*?)"""', user_val, re.DOTALL)
            if match:
                text_content = match.group(1)
                train_lengths.append(len(text_content.split()))
            else:
                train_lengths.append(len(user_val.split()))
                
    # 3. Print out statistics
    print("="*60)
    print("ANALYSIS OF SUBMISSION V3 PERFORMANCE DROP")
    print("="*60)
    
    print("\n--- 1. CHÊNH LỆCH ĐỘ DÀI VĂN BẢN (LENGTH DISCREPANCY) ---")
    print(f"Độ dài trung bình văn bản tập Huấn luyện (Train): {np.mean(train_lengths):.1f} từ (Min: {np.min(train_lengths) if train_lengths else 0}, Max: {np.max(train_lengths) if train_lengths else 0})")
    print(f"Độ dài trung bình văn bản tập Kiểm thử (Test): {np.mean(test_lengths):.1f} từ (Min: {np.min(test_lengths)}, Max: {np.max(test_lengths)})")
    ratio = np.mean(test_lengths) / np.mean(train_lengths) if train_lengths else 1
    print(f"-> Văn bản tập Test dài gấp {ratio:.2f} lần so với tập Train!")
    
    print("\n--- 2. TỶ LỆ TRÍCH XUẤT THỰC THỂ (ENTITY EXTRACTION RATES) ---")
    print(f"Trung bình số thực thể trích xuất được mỗi file: {np.mean(entity_counts):.2f}")
    print(f"Tổng số thực thể trích xuất trên 100 file: {sum(entity_counts)}")
    print(f"Tỷ lệ số thực thể / 100 từ văn bản gốc (Độ đậm đặc):")
    print(f"  - Tập Train: {53060 / sum(train_lengths) * 100:.2f} thực thể / 100 từ")
    print(f"  - Tập Test (V3): {sum(entity_counts) / sum(test_lengths) * 100:.2f} thực thể / 100 từ")
    print("-> Nhận xét: Độ đậm đặc thực thể ở tập Test V3 thấp hơn hẳn so với tập Train! LLM bị bỏ sót rất nhiều thực thể do văn bản quá dài.")
    
    print("\n--- 3. LẶP VỊ TRÍ VÀ TRÙNG LẶP TOÀN BỘ (REPETITIONS & DUPLICATES) ---")
    print(f"Số lượng thực thể bị trùng lặp tọa độ [start, end] trong cùng file: {duplicate_coords_count}")
    print("-> Nhận xét: Có hiện tượng LLM bị lặp lại hoặc lỗi ranh giới khiến nhiều thực thể đè lên nhau ở cùng 1 vị trí (ví dụ 1.json).")
    
    print("\n--- 4. VẤN ĐỀ TỪ KHÓA BỊ ẨN / MASKED WORDS (***) ---")
    print(f"Tổng số từ bị ẩn (chứa dấu sao '*') xuất hiện trong tập Test: {masked_text_in_test}")
    print(f"Tổng số thực thể có chứa '*' được trích xuất trong V3: {masked_text_predicted}")
    print("-> Nhận xét: Tập Test chứa rất nhiều từ bị ẩn (như ************ để che tên thuốc/bệnh), nhưng V3 hoàn toàn KHÔNG trích xuất được thực thể nào chứa dấu '*'. Trong khi tập Train có nhãn này.")
    
    print("\n--- 5. VẤN ĐỀ MÃ CỐD CHỨA KÝ TỰ ĐẶC BIỆT TRONG DB ---")
    print(f"Số lượng mã candidates chứa '*' hoặc '†': {asterisk_candidates_count}")
    print("-> Nhận xét: Các mã này (ví dụ D63.0*) cần phải được làm sạch ký tự đặc biệt trước khi nộp bài để hệ thống chấp nhận.")

if __name__ == "__main__":
    import re
    diagnostic()

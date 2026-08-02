import os
import re
import sys
import numpy as np
import unicodedata
import difflib

# Ensure UTF-8 printing
sys.stdout.reconfigure(encoding='utf-8')

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForTokenClassification
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

# Tập hợp các từ đơn âm tiết tiếng Việt hợp lệ được phân loại nghiêm ngặt theo loại thực thể lâm sàng
# Nhằm loại bỏ các thực thể một từ đơn bị trích xuất nhầm hoặc bị cắt nửa chừng (như "Đái", "truyền", "căn", "giác").
VALID_SINGLE_DIAGNOSES = {"gout", "lao", "trĩ"}

VALID_SINGLE_SYMPTOMS = {
    "ho", "sốt", "đau", "ngứa", "phù", "run", "mệt", "nôn", "nấc", "xỉu", 
    "co", "giật", "khò", "khè", "táo", "lỏng", "bí", "trướng", "báng"
}

VALID_SINGLE_OTHERS = {"gel", "men", "cồn", "mỡ", "kem", "tiêm", "truyền", "mổ", "chọc", "phết"}

# Danh sách các từ chỉ dẫn lâm sàng / hành động / đơn vị liều lượng thường bị phân loại nhầm làm thực thể lâm sàng.
BLACKLIST_WORDS = {
    # Hoạt động lâm sàng / Từ chỉ dẫn chung
    "thiết lập", "sử dụng", "chỉ định", "định lượng", "hướng dẫn", "theo dõi", 
    "điều trị", "phát hiện", "chẩn đoán", "nghi ngờ", "phương pháp", "kết quả",
    "tiến triển", "mức độ", "giai đoạn", "khám bệnh", "nhập viện", "xuất viện",
    # Từ chỉ liều lượng / Tần suất dùng thuốc
    "po bid", "po", "bid", "tid", "qd", "qhs", "mg", "ml", "viên", "ống", "gói", "lần"
}

def preprocess_text(text):
    """
    Sửa lỗi dính chữ phổ biến trong bệnh án để bộ tách từ và tokenizer hoạt động chuẩn xác,
    ví dụ: "bịchảy" -> "bị chảy", "đauđầu" -> "đau đầu".
    """
    replacements = {
        "bịchảy": "bị chảy",
        "bịho": "bị ho",
        "bịsốt": "bị sốt",
        "bịngứa": "bị ngứa",
        "bịnôn": "bị nôn",
        "đauđầu": "đau đầu",
        "đauhọng": "đau họng",
        "đaubụng": "đau bụng",
        "đaugực": "đau ngực",
        "đaulưng": "đau lưng",
        "đaukhớp": "đau khớp",
        "chảymáu": "chảy máu",
        "nổimề": "nổi mề",
        "đáitháo": "đái tháo"
    }
    for k, v in replacements.items():
        # Thay thế không phân biệt hoa thường
        text = re.sub(re.escape(k), v, text, flags=re.IGNORECASE)
    return text

def get_offset_mapper(text_src, text_tgt):
    """
    Tạo hàm ánh xạ chỉ số ký tự từ chuỗi nguồn (src - đã tiền xử lý) 
    sang chuỗi đích (tgt - gốc NFD) dùng SequenceMatcher để xử lý hoàn hảo
    sự thay đổi chiều dài do sửa lỗi chính tả hay chuẩn hóa Unicode.
    """
    matcher = difflib.SequenceMatcher(None, text_src, text_tgt)
    matching_blocks = matcher.get_matching_blocks()
    
    def map_index(idx_src):
        # Duyệt qua các khối khớp nhau để tìm khối chứa idx_src
        for a, b, size in matching_blocks:
            if a <= idx_src <= a + size:
                return b + (idx_src - a)
        
        # Fallback nếu nằm ngoài các khối khớp
        best_dist = float('inf')
        best_mapped = idx_src
        for a, b, size in matching_blocks:
            if idx_src < a:
                dist = a - idx_src
                if dist < best_dist:
                    best_dist = dist
                    best_mapped = b
            elif idx_src > a + size:
                dist = idx_src - (a + size)
                if dist < best_dist:
                    best_dist = dist
                    best_mapped = b + size
        return best_mapped
        
    return map_index

def clean_and_validate_entity(text_nfd, start_nfd, end_nfd, ent_type):
    """
    Hàm chuẩn hóa, làm sạch và xác thực thực thể lâm sàng:
    - Loại bỏ dấu câu và khoảng trắng ở hai đầu thực thể.
    - Cắt bỏ các tiền tố ngữ pháp thừa (như "là ", "bị ", "và ").
    - Cắt bỏ hậu tố chỉ liều lượng cho nhãn THUỐC (như "x 4 viên", "mg").
    - Áp dụng các Whitelist đơn tiết lâm sàng và danh sách từ đen Blacklist.
    """
    # 1. Trim dấu câu và khoảng trắng ở hai đầu
    while start_nfd < end_nfd and (text_nfd[start_nfd].isspace() or text_nfd[start_nfd] in ".,:;-–—_/+*()[]{}"):
        start_nfd += 1
    while end_nfd > start_nfd and (text_nfd[end_nfd - 1].isspace() or text_nfd[end_nfd - 1] in ".,:;-–—_/+*()[]{}"):
        end_nfd -= 1
        
    text = text_nfd[start_nfd:end_nfd].strip()
    if not text:
        return None
        
    # 2. Cắt bỏ tiền tố ngữ pháp thừa (lặp cho đến khi hết)
    prefixes = ["là ", "là ", "bị ", "bị ", "và ", "và ", "thì ", "thì ", "bởi ", "bởi ", "do "]
    modified = True
    while modified:
        modified = False
        text_lower = text.lower()
        for p in prefixes:
            if text_lower.startswith(p):
                start_nfd += len(p)
                text = text_nfd[start_nfd:end_nfd].strip()
                modified = True
                break
                
    # 3. Cắt bỏ hậu tố chỉ liều lượng thừa cho nhãn THUỐC
    if ent_type == "THUỐC":
        modified = True
        while modified:
            modified = False
            words = text.split()
            if not words:
                break
            last_word = words[-1].lower()
            # Cắt các đơn vị liều lượng
            if last_word in {"viên", "ống", "ống", "gói", "gói", "lần", "lần", "mg", "ml", "g", "mcg", "v", "l", "gram", "gr"}:
                end_nfd -= len(words[-1])
                while end_nfd > start_nfd and text_nfd[end_nfd - 1].isspace():
                    end_nfd -= 1
                text = text_nfd[start_nfd:end_nfd].strip()
                modified = True
            # Cắt cụm "x <số>"
            elif len(words) >= 2 and words[-2].lower() == "x" and words[-1].isdigit():
                end_nfd -= (len(words[-2]) + len(words[-1]) + 1)
                while end_nfd > start_nfd and text_nfd[end_nfd - 1].isspace():
                    end_nfd -= 1
                text = text_nfd[start_nfd:end_nfd].strip()
                modified = True
                
    if not text or len(text) <= 1:
        return None
        
    # 4. Loại bỏ thực thể chỉ gồm chữ số (ngoại trừ kết quả xét nghiệm)
    if ent_type != "KẾT_QUẢ_XÉT_NGHIỆM" and text.isdigit():
        return None
        
    # 5. Loại bỏ thực thể nằm trong danh sách đen (Blacklist)
    if text.lower() in BLACKLIST_WORDS:
        return None
        
    # 6. Lọc nhiễu âm tiết đơn (Single Syllable Verification) nghiêm ngặt theo loại nhãn
    words = text.split()
    if len(words) == 1:
        word_norm = unicodedata.normalize("NFC", words[0].lower())
        if ent_type == "CHẨN_ĐOÁN":
            if word_norm not in VALID_SINGLE_DIAGNOSES:
                return None
        elif ent_type == "TRIỆU_CHỨNG":
            if word_norm not in VALID_SINGLE_SYMPTOMS:
                return None
        else:
            if word_norm not in VALID_SINGLE_OTHERS:
                return None
                
    # 7. Loại bỏ các thực thể quá dài (nhiễu phân loại)
    if len(text) > 50 or len(words) > 8:
        return None
        
    return {
        "text": text,
        "position": [start_nfd, end_nfd],
        "type": ent_type
    }

class PhobertPredictor:
    def __init__(self, model_path=None):
        """
        Nhánh xử lý (cánh tay) PhoBERT của pipeline.
        Hoạt động hoàn toàn trên văn bản chuẩn hóa NFC để tránh vỡ âm tiết khi tokenize,
        sau đó ánh xạ ngược kết quả về tọa độ ký tự NFD gốc của file dữ liệu.
        """
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        self.device = "cpu"
        
        if model_path and HAS_TORCH:
            print(f"[PhoBERT Predictor] Đang tải mô hình từ: {model_path}...")
            self.tokenizer = AutoTokenizer.from_pretrained("vinai/phobert-base", use_fast=False)
            self.model = AutoModelForTokenClassification.from_pretrained(model_path)
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            self.model.eval()
        else:
            print("[PhoBERT Predictor] ⚠️ Chạy ở chế độ MOCK (Chưa cấu hình model_path).")

    def split_text_into_chunks(self, text_nfc, max_words=120, overlap_words=30):
        """
        Cắt văn bản NFC thành các đoạn tối ưu dưới 240 tokens dựa trên số token thực tế của từ.
        """
        words_data = []
        for m in re.finditer(r'\w+|[^\w\s]', text_nfc):
            words_data.append({
                "word": m.group(),
                "start": m.start(),
                "end": m.end()
            })
            
        if not words_data:
            return [{"text": text_nfc[:600] if len(text_nfc) > 600 else text_nfc, "start_offset": 0}]
            
        chunks = []
        total_words = len(words_data)
        start_idx = 0
        
        while start_idx < total_words:
            end_idx = start_idx
            
            if self.tokenizer is not None:
                token_count = 0
                while end_idx < total_words:
                    word_item = words_data[end_idx]
                    word_tokens = self.tokenizer.tokenize(word_item["word"])
                    if token_count + len(word_tokens) > 240:
                        break
                    token_count += len(word_tokens)
                    end_idx += 1
            else:
                while end_idx < total_words:
                    next_end_idx = end_idx + 1
                    chunk_len = words_data[next_end_idx - 1]["end"] - words_data[start_idx]["start"]
                    if next_end_idx - start_idx > max_words or chunk_len > 450:
                        break
                    end_idx = next_end_idx
                
            if end_idx == start_idx:
                end_idx = start_idx + 1
            
            char_start = words_data[start_idx]["start"]
            char_end = words_data[end_idx - 1]["end"]
            chunk_text = text_nfc[char_start:char_end]
            
            # Khống chế cứng giới hạn 240 tokens cho từ đơn lẻ quá dài để tránh lỗi CUDA
            if self.tokenizer is not None:
                if len(self.tokenizer.tokenize(chunk_text)) > 240:
                    while len(chunk_text) > 10 and len(self.tokenizer.tokenize(chunk_text)) > 240:
                        chunk_text = chunk_text[:-10]
            
            chunks.append({
                "text": chunk_text,
                "start_offset": char_start
            })
            
            if end_idx == total_words:
                break
            
            next_start_idx = end_idx - overlap_words
            if next_start_idx <= start_idx:
                next_start_idx = start_idx + 1
            start_idx = next_start_idx
            
        return chunks

    def run_phobert_inference(self, text_nfc):
        """
        Suy luận NER trên văn bản chuẩn hóa NFC, trả về thực thể lâm sàng kèm vị trí ký tự NFC.
        """
        if not self.model or not self.tokenizer:
            return [
                {"text": "tăng huyết áp", "position": [14, 27], "type": "CHẨN_ĐOÁN"},
                {"text": "Aspirin", "position": [40, 47], "type": "THUỐC"}
            ]
            
        words_data = []
        for m in re.finditer(r'\w+|[^\w\s]', text_nfc):
            words_data.append({
                "word": m.group(),
                "start": m.start(),
                "end": m.end()
            })
            
        if not words_data:
            return []
            
        input_ids = [self.tokenizer.bos_token_id]
        token_word_indices = [None]
        
        for w_idx, w_item in enumerate(words_data):
            w_tokens = self.tokenizer.tokenize(w_item["word"])
            if not w_tokens:
                continue
            w_ids = self.tokenizer.convert_tokens_to_ids(w_tokens)
            input_ids.extend(w_ids)
            token_word_indices.extend([w_idx] * len(w_ids))
            
        input_ids.append(self.tokenizer.eos_token_id)
        token_word_indices.append(None)
        
        input_tensor = torch.tensor([input_ids]).to(self.device)
        with torch.no_grad():
            outputs = self.model(input_tensor)
            logits = outputs.logits[0].cpu().numpy()
            
        exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
        probs = exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)
        predictions = probs.argmax(axis=-1)
        pred_probs = probs.max(axis=-1)
        
        id2label = self.model.config.id2label
        
        entities = []
        curr_entity = None
        
        for idx, (label_id, w_idx) in enumerate(zip(predictions, token_word_indices)):
            if w_idx is None:
                continue
                
            label = id2label[str(label_id)] if str(label_id) in id2label else id2label[label_id]
            prob = pred_probs[idx]
            
            # Đặt ngưỡng 0.55 để có độ bao phủ Recall tốt cho các cụm từ
            if label != "O" and prob >= 0.55:
                parts = label.split("-")
                ent_type = parts[1]
                is_start = parts[0] == "B"
                
                if curr_entity and not is_start and curr_entity["type"] == ent_type:
                    curr_entity["word_indices"].append(w_idx)
                else:
                    if curr_entity:
                        entities.append(curr_entity)
                    curr_entity = {
                        "type": ent_type,
                        "word_indices": [w_idx]
                    }
            else:
                if curr_entity:
                    entities.append(curr_entity)
                curr_entity = None
                
        if curr_entity:
            entities.append(curr_entity)
            
        phobert_entities = []
        for ent in entities:
            w_indices = ent["word_indices"]
            start_offset = words_data[w_indices[0]]["start"]
            end_offset = words_data[w_indices[-1]]["end"]
            
            phobert_entities.append({
                "text": text_nfc[start_offset:end_offset],
                "position": [start_offset, end_offset],
                "type": ent["type"]
            })
            
        return phobert_entities

    def predict(self, text_nfd):
        """
        Quá trình trích xuất thực thể PhoBERT trọn vẹn: Chuẩn hóa -> Tiền xử lý dính chữ -> Chia chunk -> Suy luận -> Khôi phục tọa độ NFD.
        """
        # 1. Chuẩn hóa NFC văn bản gốc và áp dụng bộ sửa lỗi chính tả dính chữ lâm sàng
        text_nfc_raw = unicodedata.normalize("NFC", text_nfd)
        text_nfc = preprocess_text(text_nfc_raw)
        
        # 2. Xây dựng hàm ánh xạ chỉ số ngược về file gốc NFD dựa trên đối sánh SequenceMatcher
        map_fn = get_offset_mapper(text_nfc, text_nfd)
        
        # 3. Chia cửa sổ trượt động trên NFC đã xử lý chính tả
        chunks = self.split_text_into_chunks(text_nfc)
        all_nfc_ents = []
        
        for chunk in chunks:
            chunk_text = chunk["text"]
            offset = chunk["start_offset"]
            
            phobert_ents = self.run_phobert_inference(chunk_text)
            for ent in phobert_ents:
                pos = ent.get("position")
                if pos and isinstance(pos, list) and len(pos) >= 2:
                    ent["position"] = [pos[0] + offset, pos[1] + offset]
                    all_nfc_ents.append(ent)
                    
        # 4. Ánh xạ ngược vị trí từ NFC sang tọa độ NFD gốc và lọc nhiễu
        all_nfd_ents = []
        for ent in all_nfc_ents:
            pos_nfc = ent["position"]
            start_nfd = map_fn(pos_nfc[0])
            end_nfd = map_fn(pos_nfc[1])
            
            # Làm sạch, chuẩn hóa tiền tố/hậu tố/liều lượng và xác thực thực thể
            cleaned = clean_and_validate_entity(text_nfd, start_nfd, end_nfd, ent["type"])
            if cleaned is not None:
                all_nfd_ents.append(cleaned)
            
        # 5. Hợp nhất các thực thể cùng loại đứng cạnh nhau trên tọa độ NFD gốc
        if not all_nfd_ents:
            return []
            
        all_nfd_ents.sort(key=lambda x: x["position"][0])
        merged_nfd_ents = []
        curr_ent = all_nfd_ents[0]
        
        for next_ent in all_nfd_ents[1:]:
            curr_start, curr_end = curr_ent["position"]
            next_start, next_end = next_ent["position"]
            
            # Kiểm tra xem khoảng giữa hai thực thể có chứa xuống dòng (\n) hay không
            # Không được phép gộp hai thực thể đứng ở hai dòng khác nhau (ví dụ bullet points)
            has_newline = "\n" in text_nfd[curr_end:next_start]
            
            # Hợp nhất nếu cùng nhãn, gần nhau, không chứa xuống dòng và sau khi hợp nhất không vượt quá 50 ký tự
            if next_ent["type"] == curr_ent["type"] and (next_start - curr_end) <= 3 and not has_newline:
                combined_len = next_end - curr_start
                if combined_len <= 50:
                    curr_ent["position"] = [curr_start, next_end]
                    curr_ent["text"] = text_nfd[curr_start:next_end]
                else:
                    merged_nfd_ents.append(curr_ent)
                    curr_ent = next_ent
            else:
                merged_nfd_ents.append(curr_ent)
                curr_ent = next_ent
                
        merged_nfd_ents.append(curr_ent)
        return merged_nfd_ents

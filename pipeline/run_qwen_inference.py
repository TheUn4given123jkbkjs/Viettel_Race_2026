import os
# Ép buộc sử dụng duy nhất GPU 0 để tránh lỗi bitsandbytes/Unsloth đa GPU (T4 x2)
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import json
import glob
import re
import shutil
import torch
import sqlite3
import sys
import unicodedata
from pathlib import Path

# ==========================================
# 0. CÀI ĐẶT THƯ VIỆN BẮT BUỘC
# ==========================================
# LƯU Ý: Chạy cài đặt các thư viện này trước khi suy luận:
# !pip install -U xformers --index-url https://download.pytorch.org/whl/cu121
# !pip install unsloth
# !pip install rapidfuzz sentence-transformers

from unsloth import FastLanguageModel

# Thử import các thư viện bổ trợ cho bộ chuẩn hóa mã (HybridLinker)
try:
    from rapidfuzz import process as fuzz_process
    from rapidfuzz import utils as fuzz_utils
    HAS_RAPIDFUZZ = True
except ImportError:
    import difflib
    HAS_RAPIDFUZZ = False

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

# ==========================================
# 1. ĐỊNH NGHĨA BỘ CHUẨN HÓA MÃ (HYBRID LINKER) TRỰC TIẾP
# ==========================================
# Vietnamese clinical synonym map: common terms -> formal ICD Vietnamese names
_SYNONYMS = {
    # Diabetes
    "tiểu đường":          "đái tháo đường",
    "tieu duong":          "đái tháo đường",
    "tiểu đường type 2":   "đái tháo đường không phụ thuộc insuline",
    "tiểu đường type 1":   "đái tháo đường phụ thuộc insuline",
    "tiểu đường tuýp 2":   "đái tháo đường không phụ thuộc insuline",
    "tieu duong type 2":   "đái tháo đường không phụ thuộc insuline",
    "đái tháo đường type 2": "đái tháo đường không phụ thuộc insuline",
    "đái tháo đường tuýp 2": "đái tháo đường không phụ thuộc insuline",
    # Hypertension
    "tăng huyết áp":       "tăng huyết áp",
    "tăng ha":             "tăng huyết áp",
    "cao huyết áp":        "tăng huyết áp",
    # Heart
    "nhồi máu cơ tim":     "nhồi máu cơ tim cấp",
    "tai biến":            "tai biến mạch máu não",
    "đột quỵ":             "tai biến mạch máu não",
    # Infections
    "viêm phổi":           "viêm phổi",
    "nhiễm trùng tiểu":    "nhiễm khuẩn đường tiết niệu",
    "nhiễm trùng tiết niệu": "nhiễm khuẩn đường tiết niệu",
    # G6PD & THA
    "g6pd":                "thiếu máu do thiếu men glucose-6-phosphate dehydrogenase",
    "thiếu men g6pd":      "thiếu máu do thiếu men glucose-6-phosphate dehydrogenase",
    "thieu men g6pd":      "thiếu máu do thiếu men glucose-6-phosphate dehydrogenase",
    "tha":                 "tăng huyết áp",
}

# Prefix patterns stripped from ICD formal names to normalize DB keys
_ICD_PREFIX_RE = re.compile(
    r'^(bệnh lý|bệnh|hội chứng|rối loạn|tình trạng|nhiễm|tổn thương)\s+',
    re.IGNORECASE
)

class HybridLinker:
    """
    3-layer Entity Linker:
      Layer 1: Exact Match (dict lookup)
      Layer 2: Fuzzy String Match (rapidfuzz / difflib)
      Layer 3: Semantic Vector Search (sentence-transformers)
    """
    def __init__(self, db_path, use_semantic=True):
        self.db_conn = sqlite3.connect(str(db_path))
        self.cursor = self.db_conn.cursor()
        self.use_semantic = use_semantic and HAS_TRANSFORMERS

        # Load reference data from SQLite
        self._load_references()

        # Build semantic index if enabled
        if self.use_semantic:
            print("[Layer 3] Loading SentenceTransformer model...")
            self.model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            self._build_semantic_index()

    def _load_references(self):
        """Load ICD-10 and RxNorm dictionaries from SQLite."""
        # ICD-10: code, name_vi
        self.cursor.execute("SELECT code, name_vi FROM icd10")
        rows = self.cursor.fetchall()
        self.icd_dict = {}  # name_vi_lower -> code
        for code, name_vi in rows:
            if name_vi:
                key = self._normalize_icd_name(name_vi.lower().strip())
                self.icd_dict[key] = code
                self.icd_dict[name_vi.lower().strip()] = code  # keep original too
        self.icd_names = list(self.icd_dict.keys())
        self.icd_names_stripped = [self._strip_diacritics(n) for n in self.icd_names]

        # RxNorm: rxcui, name
        self.cursor.execute("SELECT rxcui, name FROM rxnorm")
        rows = self.cursor.fetchall()
        self.rx_dict = {}  # name_lower -> rxcui
        for rxcui, name in rows:
            if name:
                key = name.lower().strip()
                if key not in self.rx_dict:
                    self.rx_dict[key] = str(rxcui)
        self.rx_names = list(self.rx_dict.keys())
        self.rx_names_stripped = [self._strip_diacritics(n) for n in self.rx_names]

        print(f"[DB] Loaded {len(self.icd_names)} ICD-10 terms, {len(self.rx_names)} RxNorm terms.")

    def _build_semantic_index(self):
        """Pre-compute embeddings for all reference terms."""
        print("[Layer 3] Pre-computing embeddings...")
        self.icd_embeddings = self.model.encode(self.icd_names, show_progress_bar=False, convert_to_numpy=True)
        norms = np.linalg.norm(self.icd_embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.icd_embeddings /= norms

        self.rx_embeddings = self.model.encode(self.rx_names, show_progress_bar=False, convert_to_numpy=True)
        norms = np.linalg.norm(self.rx_embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self.rx_embeddings /= norms
        print("[Layer 3] Semantic index ready.")

    @staticmethod
    def _normalize_icd_name(name: str) -> str:
        """Strip formal prefixes from ICD Vietnamese names to normalize DB keys."""
        return _ICD_PREFIX_RE.sub('', name).strip()

    @staticmethod
    def _strip_diacritics(text: str) -> str:
        """Remove combining diacritics (Vietnamese tones) for fuzzy fallback matching."""
        return ''.join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )

    def _clean_text(self, text, etype):
        """Normalize entity text before lookup."""
        text = text.lower().strip()
        text = _SYNONYMS.get(text, text)
        if etype == "THUỐC":
            # Strip dosage info
            text = re.sub(r'[\d.,]+\s*(mg|ml|mcg|g|iu|%)(/\s*(ml|kg|m2))?', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s+', ' ', text).strip()
        elif etype == "CHẨN_ĐOÁN":
            # Strip common Vietnamese diagnostic prefixes
            text = re.sub(
                r'^(bệnh nhân bị|bệnh lý|tiền sử bị|mắc bệnh|chẩn đoán|nghi ngờ|bệnh)\s+',
                '', text
            )
            text = re.sub(r'\s+', ' ', text).strip()
        return text

    def link_entity(self, text, etype):
        if etype not in ("CHẨN_ĐOÁN", "THUỐC"):
            return []

        cleaned = self._clean_text(text, etype)
        if not cleaned:
            return []

        ref_dict = self.icd_dict if etype == "CHẨN_ĐOÁN" else self.rx_dict
        ref_names = self.icd_names if etype == "CHẨN_ĐOÁN" else self.rx_names
        ref_names_stripped = self.icd_names_stripped if etype == "CHẨN_ĐOÁN" else self.rx_names_stripped

        codes = []
        # ── Layer 1: Exact Match ──
        if cleaned in ref_dict:
            codes = [ref_dict[cleaned]]
        else:
            # ── Layer 1.5: Substring / Prefix Match ──
            matched_ref = None
            for ref_name in ref_names:
                if len(cleaned) >= 3 and (cleaned in ref_name or ref_name in cleaned):
                    matched_ref = ref_name
                    break
            
            if matched_ref:
                codes = [ref_dict[matched_ref]]
            else:
                # ── Layer 2: Fuzzy Match (with diacritics-stripped fallback) ──
                best_code = self._fuzzy_match(cleaned, ref_names, ref_dict, ref_names_stripped)
                if best_code:
                    codes = [best_code]
                # ── Layer 3: Semantic Match ──
                elif self.use_semantic:
                    best_code = self._semantic_match(cleaned, etype, ref_names, ref_dict)
                    if best_code:
                        codes = [best_code]

        # Clean codes: strip '*' and '†'
        return [c.replace('*', '').replace('†', '').strip() for c in codes if c]

    def _fuzzy_match(self, query, ref_names, ref_dict, ref_names_stripped, threshold=80.0):
        if HAS_RAPIDFUZZ:
            # Attempt 1: accented match
            result = fuzz_process.extractOne(query, ref_names, processor=fuzz_utils.default_process)
            if result and result[1] >= threshold:
                return ref_dict[result[0]]
            # Attempt 2: diacritics-stripped fallback
            query_stripped = self._strip_diacritics(query)
            result2 = fuzz_process.extractOne(query_stripped, ref_names_stripped, processor=fuzz_utils.default_process)
            if result2 and result2[1] >= threshold:
                original_name = ref_names[result2[2]]
                return ref_dict[original_name]
        else:
            import difflib
            matches = difflib.get_close_matches(query, ref_names, n=1, cutoff=threshold / 100.0)
            if matches:
                return ref_dict[matches[0]]
            # Attempt 2: diacritics-stripped fallback
            query_stripped = self._strip_diacritics(query)
            stripped_to_idx = {s: i for i, s in enumerate(ref_names_stripped)}
            matches2 = difflib.get_close_matches(query_stripped, ref_names_stripped, n=1, cutoff=threshold / 100.0)
            if matches2:
                idx = stripped_to_idx.get(matches2[0])
                if idx is not None:
                    return ref_dict[ref_names[idx]]
        return None

    def _semantic_match(self, query, etype, ref_names, ref_dict, threshold=0.80):
        import numpy as np
        query_emb = self.model.encode([query], convert_to_numpy=True)
        norm = np.linalg.norm(query_emb, axis=1, keepdims=True)
        if norm[0][0] == 0:
            return None
        query_emb /= norm

        db_embs = self.icd_embeddings if etype == "CHẨN_ĐOÁN" else self.rx_embeddings
        similarities = np.dot(db_embs, query_emb.T).squeeze()

        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= threshold:
            return ref_dict[ref_names[best_idx]]
        return None

    def check_type_override(self, text):
        """
        Checks if text matches any ICD-10 or RxNorm terms with similarity >= 95% (or exact match).
        Returns (override_type, candidates) if found, else (None, []).
        """
        # 1. Check ICD-10 (CHẨN_ĐOÁN)
        cleaned_icd = self._clean_text(text, "CHẨN_ĐOÁN")
        if cleaned_icd:
            if cleaned_icd in self.icd_dict:
                code = self.icd_dict[cleaned_icd].replace('*', '').replace('†', '').strip()
                return "CHẨN_ĐOÁN", [code]
            
            icd_code = self._fuzzy_match(cleaned_icd, self.icd_names, self.icd_dict, self.icd_names_stripped, threshold=95.0)
            if icd_code:
                code = icd_code.replace('*', '').replace('†', '').strip()
                return "CHẨN_ĐOÁN", [code]
                
        # 2. Check RxNorm (THUỐC)
        cleaned_rx = self._clean_text(text, "THUỐC")
        if cleaned_rx:
            if cleaned_rx in self.rx_dict:
                code = self.rx_dict[cleaned_rx].replace('*', '').replace('†', '').strip()
                return "THUỐC", [code]
                
            rx_code = self._fuzzy_match(cleaned_rx, self.rx_names, self.rx_dict, self.rx_names_stripped, threshold=95.0)
            if rx_code:
                code = rx_code.replace('*', '').replace('†', '').strip()
                return "THUỐC", [code]
                
        return None, []

    def close(self):
        self.db_conn.close()

# ==========================================
# 2. CẤU HÌNH ĐƯỜNG DẪN ĐẦU VÀO VÀ ĐẦU RA (TỰ ĐỘNG PHÁT HIỆN)
# ==========================================
search_roots = [Path("."), Path(".."), Path("/kaggle/input"), Path("/content")]

# 1. Tìm database path (medical_codes.db)
db_candidates = []
for root in search_roots:
    if root.exists():
        db_candidates.extend(list(root.rglob("medical_codes.db")))
if db_candidates:
    DB_PATH = str(db_candidates[0])
    print(f"✅ Tự động tìm thấy CSDL tại: {DB_PATH}")
else:
    DB_PATH = "db/medical_codes.db"
    print(f"⚠️ Không tìm thấy CSDL y khoa, dùng mặc định: {DB_PATH}")

# 2. Tìm adapter path (chứa adapter_config.json)
adapter_candidates = []
for root in search_roots:
    if root.exists():
        adapter_candidates.extend(list(root.rglob("adapter_config.json")))
if adapter_candidates:
    ADAPTER_PATH = str(adapter_candidates[0].parent)
    print(f"✅ Tự động tìm thấy Adapter Path tại: {ADAPTER_PATH}")
else:
    ADAPTER_PATH = "qwen2.5-7b-lora-adapter"
    print(f"⚠️ Không tìm thấy adapter_config.json, dùng mặc định: {ADAPTER_PATH}")

# 3. Tìm test input dir (chứa các file .txt đầu vào)
INPUT_TEST_DIR = "input"
for root in search_roots:
    if not root.exists(): continue
    txt_candidates = list(root.rglob("*.txt"))
    # Tránh các tệp nhật ký
    txt_candidates = [p for p in txt_candidates if "logs" not in str(p) and "Long_Logs" not in str(p)]
    if txt_candidates:
        INPUT_TEST_DIR = str(txt_candidates[0].parent)
        print(f"✅ Tự động tìm thấy Thư mục Test Input tại: {INPUT_TEST_DIR}")
        break
else:
    print(f"⚠️ Không tìm thấy file .txt, dùng mặc định: {INPUT_TEST_DIR}")

# Thư mục lưu kết quả dự đoán tạm thời
OUTPUT_TEST_DIR = "submission_output"
if os.path.exists(OUTPUT_TEST_DIR):
    shutil.rmtree(OUTPUT_TEST_DIR)
os.makedirs(OUTPUT_TEST_DIR, exist_ok=True)

# Khởi tạo bộ chuẩn hóa mã (HybridLinker) tra cứu DB
linker = HybridLinker(db_path=DB_PATH, use_semantic=True)

# ==========================================
# 3. KHỞI TẠO MÔ HÌNH QWEN 2.5 7B DẠNG 4-BIT
# ==========================================
MAX_SEQ_LENGTH = 2048
print("--> Đang tải mô hình nền gốc Qwen 2.5 7B ở dạng 4-bit...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "Qwen/Qwen2.5-7B-Instruct",
    max_seq_length = MAX_SEQ_LENGTH,
    dtype = None,
    load_in_4bit = True,
)

# Nạp adapter đã được huấn luyện (chỉ ~30MB)
print(f"--> Đang đắp adapter từ: {ADAPTER_PATH}...")
model.load_adapter(ADAPTER_PATH)

# Kích hoạt chế độ suy luận nhanh của Unsloth (Gọi SAU khi nạp adapter)
FastLanguageModel.for_inference(model)

# ==========================================
# 4. ĐỊNH NGHĨA HÀM DỰ ĐOÁN (PROMPT CHUẨN)
# ==========================================
def run_inference(text):
    messages = [
        {
            "role": "user",
            "content": f"""Bạn là một chuyên gia y tế AI. Hãy phân tích đoạn văn bản lâm sàng tiếng Việt sau đây, trích xuất tất cả các thực thể y tế và trả về dưới dạng một danh sách JSON.

Với mỗi thực thể, bạn cần xác định:
1. `text`: Đoạn văn bản chính xác của thực thể.
   🚨 YÊU CẦU CỰC KỲ QUAN TRỌNG: 
   - Trường `text` bắt buộc phải là chuỗi con (substring) xuất hiện nguyên bản trong văn bản gốc.
   - KHÔNG ĐƯỢC tự ý sửa lỗi chính tả của văn bản gốc (nếu gốc viết sai, hãy chép lại đúng lỗi sai đó).
   - KHÔNG ĐƯỢC tự ý chuẩn hóa từ viết tắt hoặc tự dịch thuật ngữ (ví dụ: gốc ghi "bạch huyết T" thì KHÔNG được viết là "lympho T"; gốc ghi "loét tì đệ" thì KHÔNG được viết là "loét tỳ đè").
2. `position`: Vị trí ký tự bắt đầu và kết thúc [start, end] trong văn bản gốc.
3. `type`: Nhãn thực thể, nhận một trong các giá trị: TRIỆU_CHỨNG, TÊN_XÉT_NGHIỆM, KẾT_QUẢ_XÉT_NGHIỆM, CHẨN_ĐOÁN, THUỐC.
4. `assertions`: Mảng các thuộc tính ngữ cảnh (chỉ dành cho TRIỆU_CHỨNG, CHẨN_ĐOÁN, THUỐC), có thể chứa các nhãn: "isNegated", "isHistorical", "isFamily".
5. `candidates`: Mảng chứa mã chuẩn hóa (ICD-10 cho CHẨN_ĐOÁN, RxNorm cho THUỐC).

Văn bản lâm sàng:
\"\"\"
{text}
\"\"\""""
        }
    ]
    
    # Định dạng qua template của tokenizer
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt"
    ).to("cuda")
    
    # Sinh kết quả
    with torch.no_grad():
        outputs = model.generate(
            input_ids=inputs,
            max_new_tokens=1024,
            use_cache=True,
            do_sample=False,  # Ép giải mã Greedy (không ngẫu nhiên) để tối ưu JSON và tăng tốc
            repetition_penalty=1.15,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id,
        )
    
    generated_ids = [output_ids[len(input_ids):] for input_ids, output_ids in zip(inputs, outputs)]
    generated_text = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    
    try:
        clean_json = re.sub(r'^```json\s*|```$', '', generated_text.strip(), flags=re.MULTILINE)
        return json.loads(clean_json)
    except Exception as e:
        print(f"❌ Lỗi parse JSON: {e}")
        return []

def split_text_into_chunks(text, max_words=256, overlap_words=60):
    """
    Cơ chế Cửa sổ trượt gối đầu (Overlap Sliding Window) theo từ (word-based)
    để chia nhỏ tài liệu dài khi suy luận với Qwen 2.5 7B.
    """
    words_data = []
    for m in re.finditer(r'\S+', text):
        words_data.append({
            "word": m.group(),
            "start": m.start(),
            "end": m.end()
        })
        
    if not words_data:
        return [{"text": text, "start_offset": 0}]
        
    chunks = []
    total_words = len(words_data)
    start_idx = 0
    
    while start_idx < total_words:
        end_idx = min(start_idx + max_words, total_words)
        
        char_start = words_data[start_idx]["start"]
        char_end = words_data[end_idx - 1]["end"]
        
        chunk_text = text[char_start:char_end]
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

def deduplicate_entities(entities):
    """
    Loại bỏ các thực thể trùng lặp hoàn toàn hoặc trùng ranh giới nhưng khác nhãn.
    Ưu tiên thực thể có nhãn độ ưu tiên cao hơn và số lượng candidates nhiều hơn.
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

# ==========================================
# 5. THUẬT TOÁN SỬA VỊ TRÍ & CHUẨN HÓA MÃ (POST-PROCESSING V4.0)
# ==========================================
def find_closest_position(doc_text, entity_text, llm_start):
    """
    Tìm kiếm tất cả vị trí xuất hiện của thực thể trong văn bản gốc (không phân biệt hoa thường)
    và trả về vị trí [start, end] có khoảng cách gần nhất với llm_start.
    Hỗ trợ tự động chuẩn hóa Unicode (NFC/NFD) và tìm kiếm mờ (fuzzy) khi có lỗi chính tả/từ đồng nghĩa.
    """
    if not doc_text or not entity_text:
        return None
        
    # 1. Tìm khớp chính xác (Case Insensitive)
    pattern = re.escape(entity_text)
    matches = list(re.finditer(pattern, doc_text, re.IGNORECASE))
    if matches:
        best_match = min(matches, key=lambda m: abs(m.start() - llm_start))
        return best_match.start(), best_match.end()
        
    # 2. Xử lý lệch chuẩn hóa Unicode (NFC vs NFD)
    doc_nfc = unicodedata.normalize("NFC", doc_text)
    entity_nfc = unicodedata.normalize("NFC", entity_text)
    
    pattern_nfc = re.escape(entity_nfc)
    matches_nfc = list(re.finditer(pattern_nfc, doc_nfc, re.IGNORECASE))
    if matches_nfc:
        best_match_nfc = min(matches_nfc, key=lambda m: abs(m.start() - llm_start))
        start_nfc, end_nfc = best_match_nfc.start(), best_match_nfc.end()
        
        # Ánh xạ ngược vị trí từ NFC sang NFD gốc
        import difflib
        matcher = difflib.SequenceMatcher(None, doc_nfc, doc_text)
        matching_blocks = matcher.get_matching_blocks()
        
        def map_index(idx):
            for a, b, size in matching_blocks:
                if a <= idx <= a + size:
                    return b + (idx - a)
            return idx
            
        return map_index(start_nfc), map_index(end_nfc)
        
    # 3. Tìm kiếm mờ (Fuzzy Search) trong cửa sổ cục bộ để sửa lỗi chính tả/từ đồng nghĩa từ LLM
    window_start = max(0, llm_start - 80)
    window_end = min(len(doc_text), llm_start + len(entity_text) + 80)
    window_text = doc_text[window_start:window_end]
    
    import difflib
    best_ratio = 0.0
    best_pos = None
    
    n = len(entity_text)
    for length in range(max(1, n - 15), min(len(window_text), n + 15) + 1):
        for start in range(0, len(window_text) - length + 1):
            sub = window_text[start:start+length]
            ratio = difflib.SequenceMatcher(None, entity_text.lower(), sub.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_pos = (window_start + start, window_start + start + length)
                
    # Chấp nhận kết quả nếu độ khớp cao (ví dụ >= 0.70)
    if best_ratio >= 0.70 and best_pos is not None:
        return best_pos
        
    return None


def check_assertions_with_rules(doc_text, start_idx, end_idx, current_assertions):
    """
    Quét ngữ cảnh câu hiện tại chứa thực thể bằng biểu thức chính quy để bổ sung thuộc tính ngữ cảnh.
    Tránh quét xuyên qua dấu ngắt câu để hạn chế dương tính giả (false positive).
    """
    delimiters = [".", "?", "!", "\n"]
    
    # Tìm điểm bắt đầu và kết thúc câu chứa thực thể
    sent_start = 0
    for i in range(start_idx - 1, -1, -1):
        if doc_text[i] in delimiters:
            sent_start = i + 1
            break
            
    sent_end = len(doc_text)
    for i in range(end_idx, len(doc_text)):
        if doc_text[i] in delimiters:
            sent_end = i
            break
            
    sentence = doc_text[sent_start:sent_end]
    rel_start = start_idx - sent_start
    rel_end = end_idx - sent_start
    
    # Trích xuất cửa sổ văn bản trước (40 ký tự) và sau (20 ký tự) thực thể trong câu
    window_before = sentence[max(0, rel_start - 40): rel_start].lower()
    window_after = sentence[rel_end: min(len(sentence), rel_end + 20)].lower()
    
    assertions = set(current_assertions)
    
    def has_keyword(text, keywords):
        for kw in keywords:
            pattern = rf"(?:^|[\s.,;:?!\-])({re.escape(kw)})(?:$|[\s.,;:?!\-])"
            if re.search(pattern, text):
                return True
        return False
    
    negation_kws = [
        "không", "chưa phát hiện", "chưa thấy", "âm tính", 
        "không ghi nhận", "không có", "loại trừ", "chưa ghi nhận", 
        "bình thường", "không mắc"
    ]
    historical_kws = [
        "tiền sử", "tiền căn", "đã từng", "đã bị", "lịch sử", 
        "cũ", "năm ngoái", "trước kia", "phát hiện từ"
    ]
    family_kws = [
        "gia đình", "bố", "mẹ", "cha", "ông", "bà", "di truyền", 
        "dòng họ", "chú", "dì", "cậu", "mợ", "chị gái", "anh trai", 
        "em gái", "em trai"
    ]
    
    if has_keyword(window_before, negation_kws) or has_keyword(window_after, negation_kws):
        assertions.add("isNegated")
        
    if has_keyword(window_before, historical_kws):
        assertions.add("isHistorical")
        
    if has_keyword(window_before, family_kws):
        assertions.add("isFamily")
        
    return list(assertions)


def align_and_link_entities(entities, doc_text):
    """
    1. Định vị thực thể thông minh (finditer + Closest Distance) dựa trên vị trí LLM gợi ý.
    2. Sửa lỗi gán nhãn thực thể y khoa bằng cơ chế Type Override (tra cứu DB ICD-10/RxNorm với độ khớp >= 95%).
    3. Tra cứu SQLite Database để ánh xạ mã candidates cho CHẨN_ĐOÁN và THUỐC.
    4. Bổ sung/hiệu chỉnh các thuộc tính ngữ cảnh (assertions) bằng Rule Engine.
    """
    aligned = []
    
    for ent in entities:
        text = ent.get("text", "").strip()
        etype = ent.get("type", "").strip()
        assertions = ent.get("assertions", [])
        candidates = ent.get("candidates", [])
        
        if not text or not etype:
            continue
            
        # Lấy vị trí bắt đầu thô do LLM gợi ý làm gốc tính khoảng cách
        llm_pos = ent.get("position", [0, 0])
        llm_start = llm_pos[0] if isinstance(llm_pos, list) and len(llm_pos) > 0 else 0
        
        # Tìm vị trí thực tế gần nhất
        pos = find_closest_position(doc_text, text, llm_start)
        
        if pos is not None:
            start_idx, end_idx = pos
            exact_text = doc_text[start_idx:end_idx]
            
            # Luôn luôn ưu tiên chạy bộ liên kết thực thể để ghi đè mã chuẩn từ CSDL
            if etype in ["CHẨN_ĐOÁN", "THUỐC"]:
                db_candidates = linker.link_entity(exact_text, etype)
                if db_candidates:
                    candidates = db_candidates
            
            # Áp dụng Rule Engine để cập nhật assertions (chỉ áp dụng cho TRIỆU_CHỨNG, CHẨN_ĐOÁN, THUỐC)
            if etype in ["TRIỆU_CHỨNG", "CHẨN_ĐOÁN", "THUỐC"]:
                assertions = check_assertions_with_rules(doc_text, start_idx, end_idx, assertions)
                
            # Khởi tạo thực thể đã chuẩn hóa
            aligned_ent = {
                "text": exact_text,
                "position": [start_idx, end_idx],
                "type": etype,
                "assertions": assertions,
                "candidates": candidates
            }
            aligned.append(aligned_ent)
        else:
            print(f"⚠️ Bỏ qua thực thể không khớp vị trí trong văn bản gốc: {text}")
            
    return aligned

# Số lượng file test tối đa muốn xử lý (đặt None nếu muốn chạy hết 100% mẫu)
LIMIT_SAMPLES = None 

txt_files = list(glob.glob(f"{INPUT_TEST_DIR}/*.txt"))
# Sắp xếp theo thứ tự số của file để dễ theo dõi (1.txt, 2.txt,...)
txt_files.sort(key=lambda x: int(os.path.splitext(os.path.basename(x))[0]) if os.path.splitext(os.path.basename(x))[0].isdigit() else 9999)

if LIMIT_SAMPLES is not None:
    txt_files = txt_files[:LIMIT_SAMPLES]
    print(f"--> [Chế độ chạy thử nhanh] Chỉ xử lý {LIMIT_SAMPLES} file test đầu tiên...")
else:
    print(f"--> Bắt đầu xử lý toàn bộ {len(txt_files)} file test...")

for idx, fpath in enumerate(txt_files):
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        text = f.read()
    
    # Chia nhỏ văn bản thành các chunks nhỏ hơn để tối ưu hóa trích xuất
    chunks = split_text_into_chunks(text, max_words=256, overlap_words=60)
    
    all_raw_ents = []
    for chunk in chunks:
        chunk_text = chunk["text"]
        offset = chunk["start_offset"]
        
        # Dự đoán bằng mô hình trên chunk
        chunk_ents = run_inference(chunk_text)
        if chunk_ents and isinstance(chunk_ents, list):
            for ent in chunk_ents:
                pos = ent.get("position")
                if pos and isinstance(pos, list) and len(pos) >= 2 and pos[0] is not None and pos[1] is not None:
                    ent["position"] = [pos[0] + offset, pos[1] + offset]
                    all_raw_ents.append(ent)
                    
    # Sửa vị trí và chuẩn hóa mã ICD-10/RxNorm
    final_result = align_and_link_entities(all_raw_ents, text)
    
    # Loại bỏ thực thể trùng ranh giới/nhãn và trùng lặp lặp từ
    final_result = deduplicate_entities(final_result)
    
    # Lưu file JSON tương ứng
    out_fname = fname.replace(".txt", ".json")
    out_path = os.path.join(OUTPUT_TEST_DIR, out_fname)
    with open(out_path, "w", encoding="utf-8") as out_file:
        json.dump(final_result, out_file, ensure_ascii=False, indent=2)
        
    if (idx + 1) % 10 == 0:
        print(f"   Đã hoàn thành {idx + 1}/{len(txt_files)} files...")

# Đóng kết nối DB
linker.close()

# ==========================================
# 7. ĐÓNG GÓI THÀNH FILE SUBMISSION.ZIP
# ==========================================
json_files = glob.glob(f"{OUTPUT_TEST_DIR}/*.json")
print(f"--> Hoàn thành! Số lượng file JSON được tạo ra: {len(json_files)} / 100.")

shutil.make_archive("submission", 'zip', OUTPUT_TEST_DIR)
print("--> 🎉 Tạo file submission.zip thành công!")

# ==========================================
# 8. THỐNG KÊ VÀ KIỂM TRA ĐỘ HỢP LỆ (SANITY CHECK)
# ==========================================
import matplotlib.pyplot as plt

entity_counts = {"CHẨN_ĐOÁN": 0, "THUỐC": 0, "TRIỆU_CHỨNG": 0, "TÊN_XÉT_NGHIỆM": 0, "KẾT_QUẢ_XÉT_NGHIỆM": 0}
assertion_counts = {"isNegated": 0, "isHistorical": 0, "isFamily": 0}
parse_errors = 0

for j_file in json_files:
    try:
        with open(j_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                parse_errors += 1
                continue
            for ent in data:
                etype = ent.get("type")
                if etype in entity_counts:
                    entity_counts[etype] += 1
                for ass in ent.get("assertions", []):
                    if ass in assertion_counts:
                        assertion_counts[ass] += 1
    except Exception:
        parse_errors += 1

print("\n" + "="*40)
print("📊 BÁO CÁO THỐNG KÊ DỰ ĐOÁN (SANITY CHECK)")
print("="*40)
print(f"Tổng số file xử lý: {len(json_files)}")
print(f"Số file bị lỗi định dạng: {parse_errors}")
print("\n--- Phân phối thực thể dự đoán ---")
for k, v in entity_counts.items():
    print(f"  {k:22}: {v} nhãn")
print("\n--- Thuộc tính ngữ cảnh (Assertions) ---")
for k, v in assertion_counts.items():
    print(f"  {k:22}: {v} nhãn")
print("="*40)

# Vẽ biểu đồ phân phối thực thể cứu nguy khi chạy ngầm
plt.figure(figsize=(10, 5))
plt.bar(entity_counts.keys(), entity_counts.values(), color='#1f77b4', alpha=0.8)
plt.title("Phân phối các thực thể dự đoán trên tập Test (V3)")
plt.ylabel("Số lượng")
plt.grid(axis='y', linestyle='--', alpha=0.5)
plt.savefig("entity_distribution.png", dpi=100)
print("--> Đã vẽ và lưu biểu đồ phân phối thực thể tại entity_distribution.png")
plt.show()

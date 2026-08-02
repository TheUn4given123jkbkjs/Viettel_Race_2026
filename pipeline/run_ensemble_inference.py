import os
# Force single GPU usage to avoid bitsandbytes multi-GPU issues
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import json
import glob
import re
import shutil
import torch
import sqlite3
import sys
import unicodedata
import difflib
from pathlib import Path
import numpy as np

# Ensure UTF-8 printing
sys.stdout.reconfigure(encoding='utf-8')

# Install dependencies if not present
# !pip install -U xformers --index-url https://download.pytorch.org/whl/cu121
# !pip install unsloth
# !pip install rapidfuzz sentence-transformers

from unsloth import FastLanguageModel
from transformers import AutoTokenizer, AutoModelForTokenClassification

# Fuzzy matching setup
try:
    from rapidfuzz import process as fuzz_process
    from rapidfuzz import utils as fuzz_utils
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

# ==========================================
# 1. SYNONYMS & HYBRID LINKER DEFINITION
# ==========================================
_SYNONYMS = {
    "tiểu đường":          "đái tháo đường",
    "tieu duong":          "đái tháo đường",
    "tiểu đường type 2":   "đái tháo đường không phụ thuộc insuline",
    "tiểu đường type 1":   "đái tháo đường phụ thuộc insuline",
    "tiểu đường tuýp 2":   "đái tháo đường không phụ thuộc insuline",
    "tieu duong type 2":   "đái tháo đường không phụ thuộc insuline",
    "đái tháo đường type 2": "đái tháo đường không phụ thuộc insuline",
    "đái tháo đường tuýp 2": "đái tháo đường không phụ thuộc insuline",
    "tăng huyết áp":       "tăng huyết áp",
    "tăng ha":             "tăng huyết áp",
    "cao huyết áp":        "tăng huyết áp",
    "nhồi máu cơ tim":     "nhồi máu cơ tim cấp",
    "tai biến":            "tai biến mạch máu não",
    "đột quỵ":             "tai biến mạch máu não",
    "viêm phổi":           "viêm phổi",
    "nhiễm trùng tiểu":    "nhiễm khuẩn đường tiết niệu",
    "nhiễm trùng tiết niệu": "nhiễm khuẩn đường tiết niệu",
    "g6pd":                "thiếu máu do thiếu men glucose-6-phosphate dehydrogenase",
    "thiếu men g6pd":      "thiếu máu do thiếu men glucose-6-phosphate dehydrogenase",
    "thieu men g6pd":      "thiếu máu do thiếu men glucose-6-phosphate dehydrogenase",
    "tha":                 "tăng huyết áp",
}

_ICD_PREFIX_RE = re.compile(
    r'^(bệnh lý|bệnh|hội chứng|rối loạn|tình trạng|nhiễm|tổn thương)\s+',
    re.IGNORECASE
)

class HybridLinker:
    def __init__(self, db_path, use_semantic=False):
        self.db_conn = sqlite3.connect(str(db_path))
        self.cursor = self.db_conn.cursor()
        self.use_semantic = use_semantic
        self._load_references()

    def _load_references(self):
        self.cursor.execute("SELECT code, name_vi FROM icd10")
        rows = self.cursor.fetchall()
        self.icd_dict = {}
        for code, name_vi in rows:
            if name_vi:
                key = self._normalize_icd_name(name_vi.lower().strip())
                self.icd_dict[key] = code
                self.icd_dict[name_vi.lower().strip()] = code
        self.icd_names = list(self.icd_dict.keys())
        self.icd_names_stripped = [self._strip_diacritics(n) for n in self.icd_names]

        self.cursor.execute("SELECT rxcui, name FROM rxnorm")
        rows = self.cursor.fetchall()
        self.rx_dict = {}
        for rxcui, name in rows:
            if name:
                key = name.lower().strip()
                if key not in self.rx_dict:
                    self.rx_dict[key] = str(rxcui)
        self.rx_names = list(self.rx_dict.keys())
        self.rx_names_stripped = [self._strip_diacritics(n) for n in self.rx_names]

    @staticmethod
    def _normalize_icd_name(name: str) -> str:
        return _ICD_PREFIX_RE.sub('', name).strip()

    @staticmethod
    def _strip_diacritics(text: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

    def _clean_text(self, text, etype):
        text = text.lower().strip()
        text = _SYNONYMS.get(text, text)
        if etype == "THUỐC":
            text = re.sub(r'[\d.,]+\s*(mg|ml|mcg|g|iu|%)(/\s*(ml|kg|m2))?', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s+', ' ', text).strip()
        elif etype == "CHẨN_ĐOÁN":
            text = re.sub(r'^(bệnh nhân bị|bệnh lý|tiền sử bị|mắc bệnh|chẩn đoán|nghi ngờ|bệnh)\s+', '', text)
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
                # ── Layer 2: Fuzzy Match ──
                best_code = self._fuzzy_match(cleaned, ref_names, ref_dict, ref_names_stripped)
                if best_code:
                    codes = [best_code]
        return [c.replace('*', '').replace('†', '').strip() for c in codes if c]

    def _fuzzy_match(self, query, ref_names, ref_dict, ref_names_stripped, threshold=80.0):
        if HAS_RAPIDFUZZ:
            result = fuzz_process.extractOne(query, ref_names, processor=fuzz_utils.default_process)
            if result and result[1] >= threshold:
                return ref_dict[result[0]]
            query_stripped = self._strip_diacritics(query)
            result2 = fuzz_process.extractOne(query_stripped, ref_names_stripped, processor=fuzz_utils.default_process)
            if result2 and result2[1] >= threshold:
                original_name = ref_names[result2[2]]
                return ref_dict[original_name]
        else:
            matches = difflib.get_close_matches(query, ref_names, n=1, cutoff=threshold / 100.0)
            if matches:
                return ref_dict[matches[0]]
            query_stripped = self._strip_diacritics(query)
            stripped_to_idx = {s: i for i, s in enumerate(ref_names_stripped)}
            matches2 = difflib.get_close_matches(query_stripped, ref_names_stripped, n=1, cutoff=threshold / 100.0)
            if matches2:
                idx = stripped_to_idx.get(matches2[0])
                if idx is not None:
                    return ref_dict[ref_names[idx]]
        return None

    def close(self):
        self.db_conn.close()


# ==========================================
# 2. AUTO-PATH DISCOVERY
# ==========================================
# Search roots for local and cloud platforms
search_roots = [Path("."), Path(".."), Path("/kaggle/input"), Path("/content")]

# Find SQLite DB
db_candidates = []
for root in search_roots:
    if root.exists():
        db_candidates.extend(list(root.rglob("medical_codes.db")))
DB_PATH = str(db_candidates[0]) if db_candidates else "db/medical_codes.db"

# Find Qwen adapter folder
adapter_candidates = []
for root in search_roots:
    if root.exists():
        adapter_candidates.extend(list(root.rglob("adapter_config.json")))
ADAPTER_PATH = str(adapter_candidates[0].parent) if adapter_candidates else "qwen2.5-7b-lora-adapter"

# Find PhoBERT NER model folder (config.json has model_type == roberta)
PHOBERT_MODEL_PATH = None
for root in search_roots:
    if not root.exists(): continue
    configs = list(root.rglob("config.json"))
    for cfg_path in configs:
        try:
            with open(cfg_path, "r") as f:
                cfg = json.load(f)
            if cfg.get("model_type") == "roberta" or "RobertaForTokenClassification" in cfg.get("architectures", []):
                PHOBERT_MODEL_PATH = str(cfg_path.parent)
                break
        except Exception:
            continue
    if PHOBERT_MODEL_PATH:
        break

# Find Input .txt files
INPUT_TEST_DIR = "input"
for root in search_roots:
    if not root.exists(): continue
    txt_candidates = list(root.rglob("*.txt"))
    # Filter out workspace files/logs
    txt_candidates = [p for p in txt_candidates if "logs" not in str(p) and "Long_Logs" not in str(p)]
    if txt_candidates:
        INPUT_TEST_DIR = str(txt_candidates[0].parent)
        break

OUTPUT_TEST_DIR = "submission_output"
if os.path.exists(OUTPUT_TEST_DIR):
    shutil.rmtree(OUTPUT_TEST_DIR)
os.makedirs(OUTPUT_TEST_DIR, exist_ok=True)

print("="*60)
print(f"DB Path:      {DB_PATH}")
print(f"Qwen Path:    {ADAPTER_PATH}")
print(f"PhoBERT Path: {PHOBERT_MODEL_PATH}")
print(f"Input Dir:    {INPUT_TEST_DIR}")
print("="*60)

linker = HybridLinker(db_path=DB_PATH, use_semantic=False)

# ==========================================
# 3. INITIALIZE MODELS
# ==========================================
# A. Qwen 2.5 7B QLoRA
print("--> Loading Qwen 2.5 7B...")
model_qwen, tokenizer_qwen = FastLanguageModel.from_pretrained(
    model_name = "Qwen/Qwen2.5-7B-Instruct",
    max_seq_length = 2048,
    dtype = None,
    load_in_4bit = True,
)
model_qwen.load_adapter(ADAPTER_PATH)
FastLanguageModel.for_inference(model_qwen)

# B. PhoBERT NER
if PHOBERT_MODEL_PATH:
    print(f"--> Loading PhoBERT NER model from {PHOBERT_MODEL_PATH}...")
    tokenizer_phobert = AutoTokenizer.from_pretrained("vinai/phobert-base", use_fast=False)
    model_phobert = AutoModelForTokenClassification.from_pretrained(PHOBERT_MODEL_PATH)
    device_phobert = "cuda" if torch.cuda.is_available() else "cpu"
    model_phobert.to(device_phobert)
    model_phobert.eval()
else:
    print("⚠️ Warning: PhoBERT model path not found. Running in Qwen-only mode!")
    model_phobert = None


# ==========================================
# 4. INFERENCE ENGINE (SLIDING WINDOW & BIO)
# ==========================================
def clean_and_validate_entity(text_nfd, start_nfd, end_nfd, ent_type):
    # Trim punctuations
    while start_nfd < end_nfd and (text_nfd[start_nfd].isspace() or text_nfd[start_nfd] in ".,:;-–—_/+*()[]{}"):
        start_nfd += 1
    while end_nfd > start_nfd and (text_nfd[end_nfd - 1].isspace() or text_nfd[end_nfd - 1] in ".,:;-–—_/+*()[]{}"):
        end_nfd -= 1
        
    text = text_nfd[start_nfd:end_nfd].strip()
    if not text:
        return None
        
    # Strip prefixes
    prefixes = ["là ", "là ", "bị ", "bị ", "và ", "và ", "thì ", "thì ", "do "]
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
                
    # Symptom correction
    text_clean = text.lower()
    if text_clean in {
        "đau", "sốt", "ho", "ngứa", "nôn", "mệt", "ớn lạnh", "khó thở", "chóng mặt", 
        "đau đầu", "đau ngực", "đau bụng", "buồn nôn", "mệt mỏi", "đánh trống ngực", 
        "bí tiểu", "tiêu chảy", "táo bón", "chướng bụng", "dịch báng"
    }:
        ent_type = "TRIỆU_CHỨNG"
        
    return {
        "text": text,
        "position": [start_nfd, end_nfd],
        "type": ent_type
    }

def get_offset_mapper(text_src, text_tgt):
    matcher = difflib.SequenceMatcher(None, text_src, text_tgt)
    matching_blocks = matcher.get_matching_blocks()
    def map_index(idx_src):
        for a, b, size in matching_blocks:
            if a <= idx_src <= a + size:
                return b + (idx_src - a)
        return idx_src
    return map_index

class PhobertPredictor:
    def __init__(self):
        self.model = model_phobert
        self.tokenizer = tokenizer_phobert
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def split_text_into_chunks(self, text_nfc, max_words=120, overlap_words=60):
        words_data = []
        for m in re.finditer(r'\w+|[^\w\s]', text_nfc):
            words_data.append({"word": m.group(), "start": m.start(), "end": m.end()})
        if not words_data:
            return [{"text": text_nfc, "start_offset": 0}]
        chunks = []
        total_words = len(words_data)
        start_idx = 0
        while start_idx < total_words:
            end_idx = start_idx
            token_count = 0
            while end_idx < total_words:
                word_tokens = self.tokenizer.tokenize(words_data[end_idx]["word"])
                if token_count + len(word_tokens) > 240:
                    break
                token_count += len(word_tokens)
                end_idx += 1
            if end_idx == start_idx:
                end_idx = start_idx + 1
            char_start = words_data[start_idx]["start"]
            char_end = words_data[end_idx - 1]["end"]
            chunk_text = text_nfc[char_start:char_end]
            chunks.append({"text": chunk_text, "start_offset": char_start})
            if end_idx == total_words:
                break
            next_start_idx = end_idx - overlap_words
            start_idx = max(start_idx + 1, next_start_idx)
        return chunks

    def run_phobert_inference(self, text_nfc):
        words_data = []
        for m in re.finditer(r'\w+|[^\w\s]', text_nfc):
            words_data.append({"word": m.group(), "start": m.start(), "end": m.end()})
        if not words_data:
            return []
        input_ids = [self.tokenizer.bos_token_id]
        token_word_indices = [None]
        for w_idx, w_item in enumerate(words_data):
            w_tokens = self.tokenizer.tokenize(w_item["word"])
            if not w_tokens: continue
            w_ids = self.tokenizer.convert_tokens_to_ids(w_tokens)
            input_ids.extend(w_ids)
            token_word_indices.extend([w_idx] * len(w_ids))
        input_ids.append(self.tokenizer.eos_token_id)
        token_word_indices.append(None)
        
        input_tensor = torch.tensor([input_ids]).to(self.device)
        with torch.no_grad():
            outputs = self.model(input_tensor)
            logits = outputs.logits[0].cpu().numpy()
        probs = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
        probs = probs / np.sum(probs, axis=-1, keepdims=True)
        predictions = probs.argmax(axis=-1)
        pred_probs = probs.max(axis=-1)
        
        id2label = self.model.config.id2label
        entities = []
        curr_entity = None
        for idx, (label_id, w_idx) in enumerate(zip(predictions, token_word_indices)):
            if w_idx is None: continue
            label = id2label[str(label_id)] if str(label_id) in id2label else id2label[label_id]
            prob = pred_probs[idx]
            if label != "O" and prob >= 0.55:
                parts = label.split("-")
                ent_type = parts[1]
                is_start = parts[0] == "B"
                if curr_entity and not is_start and curr_entity["type"] == ent_type:
                    curr_entity["word_indices"].append(w_idx)
                else:
                    if curr_entity: entities.append(curr_entity)
                    curr_entity = {"type": ent_type, "word_indices": [w_idx]}
            else:
                if curr_entity: entities.append(curr_entity)
                curr_entity = None
        if curr_entity: entities.append(curr_entity)
        
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
        text_nfc = preprocess_text_spelling(unicodedata.normalize("NFC", text_nfd))
        map_fn = get_offset_mapper(text_nfc, text_nfd)
        chunks = self.split_text_into_chunks(text_nfc)
        all_nfc_ents = []
        for chunk in chunks:
            chunk_text = chunk["text"]
            offset = chunk["start_offset"]
            ents = self.run_phobert_inference(chunk_text)
            for ent in ents:
                pos = ent["position"]
                ent["position"] = [pos[0] + offset, pos[1] + offset]
                all_nfc_ents.append(ent)
        
        all_nfd_ents = []
        for ent in all_nfc_ents:
            pos_nfc = ent["position"]
            start_nfd = map_fn(pos_nfc[0])
            end_nfd = map_fn(pos_nfc[1])
            cleaned = clean_and_validate_entity(text_nfd, start_nfd, end_nfd, ent["type"])
            if cleaned: all_nfd_ents.append(cleaned)
            
        if not all_nfd_ents: return []
        all_nfd_ents.sort(key=lambda x: x["position"][0])
        merged = []
        curr = all_nfd_ents[0]
        for nxt in all_nfd_ents[1:]:
            has_newline = "\n" in text_nfd[curr["position"][1]:nxt["position"][0]]
            if nxt["type"] == curr["type"] and (nxt["position"][0] - curr["position"][1]) <= 3 and not has_newline:
                if (nxt["position"][1] - curr["position"][0]) <= 50:
                    curr["position"] = [curr["position"][0], nxt["position"][1]]
                    curr["text"] = text_nfd[curr["position"][0]:nxt["position"][1]]
                else:
                    merged.append(curr)
                    curr = nxt
            else:
                merged.append(curr)
                curr = nxt
        merged.append(curr)
        return merged

def preprocess_text_spelling(text):
    replacements = {
        "bịchảy": "bị chảy", "bịho": "bị ho", "bịsốt": "bị sốt", "bịngứa": "bị ngứa",
        "bịnôn": "bị nôn", "đauđầu": "đau đầu", "đauhọng": "đau họng", "đauhụng": "đau bụng",
        "đaugực": "đau ngực", "đaulưng": "đau lưng", "đaukhớp": "đau khớp", "chảymáu": "chảy máu",
        "nổimề": "nổi mề", "đáitháo": "đái tháo"
    }
    for k, v in replacements.items():
        text = re.sub(re.escape(k), v, text, flags=re.IGNORECASE)
    return text


# Qwen Prompt & Run
def run_qwen_inference(text):
    messages = [
        {
            "role": "user",
            "content": f"""Bạn là một chuyên gia y tế AI. Hãy phân tích đoạn văn bản lâm sàng tiếng Việt sau đây, trích xuất tất cả các thực thể y tế và trả về dưới dạng một danh sách JSON.
Với mỗi thực thể, bạn cần xác định:
1. `text`: Đoạn văn bản chính xác của thực thể (bắt buộc là chuỗi con trong văn bản gốc, giữ nguyên lỗi chính tả/viết tắt).
2. `position`: Vị trí ký tự bắt đầu và kết thúc [start, end] trong văn bản gốc.
3. `type`: Nhãn thực thể, nhận một trong các giá trị: TRIỆU_CHỨNG, TÊN_XÉT_NGHIỆM, KẾT_QUẢ_XÉT_NGHIỆM, CHẨN_ĐOÁN, THUỐC.
4. `assertions`: Mảng các thuộc tính ngữ cảnh (chỉ dành cho TRIỆU_CHỨNG, CHẨN_ĐOÁN, THUỐC), có thể chứa: "isNegated", "isHistorical", "isFamily".
5. `candidates`: Mảng chứa mã chuẩn hóa (ICD-10 cho CHẨN_ĐOÁN, RxNorm cho THUỐC).

Văn bản lâm sàng:
\"\"\"
{text}
\"\"\""""
        }
    ]
    inputs = tokenizer_qwen.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
    with torch.no_grad():
        outputs = model_qwen.generate(
            input_ids=inputs, max_new_tokens=1024, use_cache=True, do_sample=False,
            repetition_penalty=1.15, eos_token_id=tokenizer_qwen.eos_token_id, pad_token_id=tokenizer_qwen.pad_token_id
        )
    gen_ids = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs, outputs)]
    gen_text = tokenizer_qwen.batch_decode(gen_ids, skip_special_tokens=True)[0]
    try:
        clean_json = re.sub(r'^```json\s*|```$', '', gen_text.strip(), flags=re.MULTILINE)
        return json.loads(clean_json)
    except Exception:
        return []


def split_text_qwen(text, max_words=256, overlap_words=60):
    words = []
    for m in re.finditer(r'\S+', text):
        words.append({"word": m.group(), "start": m.start(), "end": m.end()})
    if not words: return [{"text": text, "start_offset": 0}]
    chunks = []
    total = len(words)
    start = 0
    while start < total:
        end = min(start + max_words, total)
        char_start = words[start]["start"]
        char_end = words[end - 1]["end"]
        chunks.append({"text": text[char_start:char_end], "start_offset": char_start})
        if end == total: break
        start = max(start + 1, end - overlap_words)
    return chunks

def find_closest_position(doc_text, entity_text, llm_start):
    if not doc_text or not entity_text: return None
    # 1. Exact case-insensitive match
    pattern = re.escape(entity_text)
    matches = list(re.finditer(pattern, doc_text, re.IGNORECASE))
    if matches:
        bm = min(matches, key=lambda m: abs(m.start() - llm_start))
        return bm.start(), bm.end()
    # 2. Unicode normalization matching
    doc_nfc = unicodedata.normalize("NFC", doc_text)
    ent_nfc = unicodedata.normalize("NFC", entity_text)
    matches_nfc = list(re.finditer(re.escape(ent_nfc), doc_nfc, re.IGNORECASE))
    if matches_nfc:
        bm = min(matches_nfc, key=lambda m: abs(m.start() - llm_start))
        sn, en = bm.start(), bm.end()
        matcher = difflib.SequenceMatcher(None, doc_nfc, doc_text)
        matching_blocks = matcher.get_matching_blocks()
        def map_idx(idx):
            for a, b, size in matching_blocks:
                if a <= idx <= a + size: return b + (idx - a)
            return idx
        return map_idx(sn), map_idx(en)
    return None

def check_assertions_with_rules(doc_text, start_idx, end_idx, current_assertions):
    delimiters = [".", "?", "!", "\n"]
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
    window_before = sentence[max(0, rel_start - 40): rel_start].lower()
    
    assertions = set(current_assertions)
    neg_kws = ["không", "chưa phát hiện", "chưa thấy", "âm tính", "không ghi nhận", "không có", "loại trừ", "chưa ghi nhận", "bình thường", "không mắc"]
    hist_kws = ["tiền sử", "tiền căn", "đã từng", "đã bị", "lịch sử", "cũ", "năm ngoái", "trước kia", "phát hiện từ"]
    fam_kws = ["bố", "mẹ", "ông", "bà", "cha", "anh", "chị", "em", "di truyền", "gia đình"]
    
    def has_kw(text, kws):
        for kw in kws:
            if re.search(rf"(?:^|[\s.,;:?!\-])({re.escape(kw)})(?:$|[\s.,;:?!\-])", text): return True
        return False
        
    if has_kw(window_before, neg_kws): assertions.add("isNegated")
    if has_kw(window_before, hist_kws): assertions.add("isHistorical")
    if has_kw(window_before, fam_kws): assertions.add("isFamily")
    return list(assertions)


# ==========================================
# 5. ENSEMBLE MERGER (QWEN + PHOBERT)
# ==========================================
def compute_iou(pos1, pos2):
    s1, e1 = pos1
    s2, e2 = pos2
    overlap_start = max(s1, s2)
    overlap_end = min(e1, e2)
    if overlap_start >= overlap_end: return 0.0
    overlap = overlap_end - overlap_start
    union = (e1 - s1) + (e2 - s2) - overlap
    return overlap / union if union > 0 else 0.0

def merge_entities(qwen_ents, phobert_ents, iou_threshold=0.5):
    merged = []
    matched_q = set()
    matched_p = set()
    
    for idx_q, ent_q in enumerate(qwen_ents):
        type_q = ent_q.get("type", "")
        pos_q = ent_q.get("position", [0, 0])
        best_p_idx = -1
        best_iou = -1.0
        
        for idx_p, ent_p in enumerate(phobert_ents):
            if idx_p in matched_p: continue
            if type_q != ent_p.get("type", ""): continue
            iou = compute_iou(pos_q, ent_p.get("position", [0, 0]))
            if iou >= iou_threshold and iou > best_iou:
                best_iou = iou
                best_p_idx = idx_p
                
        if best_p_idx != -1:
            matched_q.add(idx_q)
            matched_p.add(best_p_idx)
            ent_p = phobert_ents[best_p_idx]
            merged.append({
                "text": ent_p.get("text", ""),
                "position": ent_p.get("position", [0, 0]),
                "type": type_q,
                "assertions": ent_q.get("assertions", []),
                "candidates": ent_q.get("candidates", [])
            })
            
    # Include unmatched
    for idx_q, ent_q in enumerate(qwen_ents):
        if idx_q not in matched_q: merged.append(ent_q)
    for idx_p, ent_p in enumerate(phobert_ents):
        if idx_p not in matched_p:
            ent_p["assertions"] = []
            ent_p["candidates"] = []
            merged.append(ent_p)
            
    merged.sort(key=lambda x: x.get("position", [0, 0])[0])
    return merged


# ==========================================
# 6. PIPELINE RUN
# ==========================================
phobert_predictor = PhobertPredictor() if model_phobert else None

txt_files = glob.glob(f"{INPUT_TEST_DIR}/*.txt")
print(f"Starting end-to-end inference for {len(txt_files)} files...")

for idx, fpath in enumerate(txt_files):
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8") as f:
        text = f.read()
        
    # A. Run Qwen
    qwen_raw = []
    qwen_chunks = split_text_qwen(text)
    for chunk in qwen_chunks:
        chunk_ents = run_qwen_inference(chunk["text"])
        offset = chunk["start_offset"]
        if chunk_ents and isinstance(chunk_ents, list):
            for ent in chunk_ents:
                pos = ent.get("position")
                if pos and len(pos) >= 2:
                    ent["position"] = [pos[0] + offset, pos[1] + offset]
                    qwen_raw.append(ent)
                    
    # Align Qwen positions and apply rules
    qwen_processed = []
    for ent in qwen_raw:
        pos = find_closest_position(text, ent["text"], ent["position"][0])
        if pos:
            ent["position"] = list(pos)
            ent["text"] = text[pos[0]:pos[1]]
            # Apply assertions rules
            ent["assertions"] = check_assertions_with_rules(text, pos[0], pos[1], ent.get("assertions", []))
            
            # Clean candidates list
            cands = ent.get("candidates", [])
            ent["candidates"] = [c.replace('*', '').replace('†', '').strip() for c in cands if c]
            qwen_processed.append(ent)
            
    # B. Run PhoBERT
    phobert_processed = []
    if phobert_predictor:
        phobert_processed = phobert_predictor.predict(text)
        
    # C. Merge Predictions
    final_ents = merge_entities(qwen_processed, phobert_processed)
    
    # D. Link candidates
    for ent in final_ents:
        etype = ent.get("type", "")
        if etype in ["CHẨN_ĐOÁN", "THUỐC"]:
            # Recalculate candidates via database linker
            new_codes = linker.link_entity(ent["text"], etype)
            if new_codes:
                ent["candidates"] = new_codes
                
    # Save output
    out_fname = fname.replace(".txt", ".json")
    with open(os.path.join(OUTPUT_TEST_DIR, out_fname), "w", encoding="utf-8") as out_f:
        json.dump(final_ents, out_f, ensure_ascii=False, indent=2)

linker.close()

# Package submission
shutil.make_archive("submission", 'zip', OUTPUT_TEST_DIR)
print("--> 🎉 Zip package created successfully at submission.zip!")

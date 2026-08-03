import json
import sqlite3
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np  # Always available in ML stacks; needed for semantic search

sys.stdout.reconfigure(encoding='utf-8')

# Fuzzy matching: try rapidfuzz first, fallback to difflib
try:
    from rapidfuzz import process as fuzz_process
    from rapidfuzz import utils as fuzz_utils
    HAS_RAPIDFUZZ = True
except ImportError:
    import difflib
    HAS_RAPIDFUZZ = False
    print("[INFO] rapidfuzz not installed. Using difflib fallback for fuzzy matching.")

# Semantic search: optional
# Safe check if installed without importing/loading DLLs to prevent crash
import importlib.util
HAS_TRANSFORMERS = importlib.util.find_spec("sentence_transformers") is not None
if not HAS_TRANSFORMERS:
    print("[INFO] sentence-transformers is not installed. Semantic search (Layer 3) disabled.")

# Resolve paths relative to this script's location (pipeline/ -> project root -> db/)
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "db" / "medical_codes.db"

# Vietnamese clinical synonym map: common terms -> formal ICD Vietnamese names
# Key = common/abbreviated term (lowercase); Value = normalized form closer to ICD DB entries
_SYNONYMS = {
    # === Diabetes ===
    "tiểu đường":            "đái tháo đường",
    "tieu duong":            "đái tháo đường",
    "tiểu đường type 2":     "đái tháo đường không phụ thuộc insuline",
    "tiểu đường típ 2":      "đái tháo đường không phụ thuộc insuline",
    "tiểu đường tuýp 2":     "đái tháo đường không phụ thuộc insuline",
    "tiểu đường type 1":     "đái tháo đường phụ thuộc insuline",
    "tieu duong type 2":     "đái tháo đường không phụ thuộc insuline",
    "đái tháo đường type 2": "đái tháo đường không phụ thuộc insuline",
    "đái tháo đường típ 2":  "đái tháo đường không phụ thuộc insuline",
    "đái tháo đường tuýp 2": "đái tháo đường không phụ thuộc insuline",
    # === Hypertension ===
    "tăng huyết áp":         "tăng huyết áp",
    "tăng ha":               "tăng huyết áp",
    "cao huyết áp":          "tăng huyết áp",
    # === Heart ===
    "nhồi máu cơ tim":       "nhồi máu cơ tim cấp",
    "tai biến":              "tai biến mạch máu não",
    "đột quỵ":               "tai biến mạch máu não",
    "rung nhĩ":              "rung và cuồng nhĩ",
    "rung nhĩ và nhịp nhanh trên thất": "rung và cuồng nhĩ",
    "suy tim":               "suy tim",
    "suy tim sung huyết":    "suy tim sung huyết",
    # === GI (Gastro) ===
    "viêm bao tử":           "viêm dạ dày",
    "viêm hang vị sung huyết": "viêm dạ dày",
    "viêm hang vị":          "viêm dạ dày",
    "viêm dạ dày":           "viêm dạ dày",
    "trào ngược dạ dày":     "trào ngược dạ dày-thực quản",
    "trào ngược":            "trào ngược dạ dày-thực quản",
    "xơ gan":                "xơ gan",
    "xơ gan mất bù":         "xơ gan",
    "viêm gan":              "viêm gan",
    # === Respiratory ===
    "viêm phổi":             "viêm phổi",
    "viêm phổi bệnh viện":   "viêm phổi do vi sinh vật khác",
    "bệnh phổi kẽ":          "bệnh phổi kẽ khác",
    "thuyên tắc phổi":       "thuyên tắc phổi",
    "thuyên tắc phổi hai bên": "thuyên tắc phổi",
    "tràn dịch màng phổi":   "tràn dịch màng phổi",
    "tràn dịch màng phổi trái": "tràn dịch màng phổi",
    "tràn dịch màng phổi phải": "tràn dịch màng phổi",
    "ngưng thở khi ngủ":     "ngưng thở khi ngủ",
    "áp-xe phổi":            "áp xe phổi",
    "áp xe phổi":            "áp xe phổi",
    # === Infections ===
    "nhiễm trùng tiểu":      "nhiễm khuẩn đường tiết niệu",
    "nhiễm trùng tiết niệu": "nhiễm khuẩn đường tiết niệu",
    "nhiễm trùng huyết":     "nhiễm khuẩn huyết",
    "nhiễm virus herpes simplex": "nhiễm virus herpes",
    "vi-rút dại":            "bệnh dại",
    # === Skin ===
    "mày đay vô căn":        "mày đay",
    "mày đay mạn tính":      "mày đay",
    "mày đay":               "mày đay",
    "nấm bẹn":               "nấm da",
    # === Musculoskeletal ===
    "giả gout":              "viêm khớp do lắng đọng tinh thể",
    # === Renal ===
    "suy thận":              "suy thận",
    "bệnh thận mạn":         "suy thận mạn tính",
    "bàng quang thần kinh":  "rối loạn thần kinh-cơ của bàng quang",
    # === Psych ===
    "rối loạn lo âu":        "rối loạn lo âu",
    "rối loạn cảm xúc":      "rối loạn cảm xúc",
    # === Blood ===
    "thiếu men g6pd":        "thiếu máu do rối loạn enzym",
    # === Neuro ===
    "cơn rối loạn ý thức thoáng qua": "rối loạn ý thức thoáng qua",
    "đau nửa đầu":           "đau nửa đầu",
    "bệnh lý đau nửa đầu":   "đau nửa đầu",
    "phù gai thị":            "phù gai thị",
    # === Oncology ===
    "ung thư vú":            "u ác tuyến vú",
    "ung thư vú di căn":     "u ác tuyến vú",
    "ung thư":               "u ác",
    "u nang tuyến vú":       "u lành tuyến vú",
    # === Liver / Hepato ===
    "tăng men gan":          "bệnh gan",
    "tăng bilirubin máu":    "rối loạn chuyển hóa bilirubin",
    # === Trauma ===
    "tụ máu ngoài màng cứng":       "chấn thương nội sọ",
    "tụ máu ngoài màng cứng phải":  "chấn thương nội sọ",
    "tụ máu ngoài màng cứng trái":  "chấn thương nội sọ",
    "loét tì đè":            "loét do tỳ đè",
    "loét đè ép":             "loét do tỳ đè",
    # === Gynecology ===
    "tắc ống dẫn trứng":     "tắc vòi trứng",
    "teo niêm mạc tử cung":  "viêm tử cung",
    # === Urology ===
    "giãn thừng tinh":       "giãn tĩnh mạch thừng tinh",
    # === Vascular ===
    "động mạch vành":        "bệnh tim do thiếu máu cục bộ mạn",
    # === Endocrine ===
    "bệnh graves":           "nhiễm độc giáp",
    "graves":                "nhiễm độc giáp",
    "cường giáp":            "nhiễm độc giáp",
}

# NER false-positive filter: texts commonly mis-tagged as THUỐC by NER models
_DRUG_BLACKLIST = {
    "hệ sau", "hệ 1", "hệ 2", "hệ trước", "bậc thấp", "bậc cao",
    "tiêm", "tiêm vaccine", "tiêm chủng",
    "thuốc chống trầm cảm", "thuốc giảm đau opioid",
    "kháng histamin h1", "corticosteroid bôi tại chỗ",
    "thuốc",  # generic "thuốc" alone is not a drug name
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

    def __init__(self, db_path=DB_PATH, use_semantic=True):
        self.db_conn = sqlite3.connect(str(db_path))
        self.cursor = self.db_conn.cursor()
        self.use_semantic = use_semantic and HAS_TRANSFORMERS

        # Load reference data from SQLite
        self._load_references()

        # Build semantic index if enabled
        if self.use_semantic:
            try:
                print("[Layer 3] Loading SentenceTransformer model...")
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
                self._build_semantic_index()
            except Exception as e:
                print(f"[WARNING] Failed to load SentenceTransformer: {e}. Semantic search (Layer 3) disabled.")
                self.use_semantic = False

    def _load_references(self):
        """Load ICD-10 and RxNorm dictionaries from SQLite."""
        # ICD-10: code, name_vi
        self.cursor.execute("SELECT code, name_vi FROM icd10")
        rows = self.cursor.fetchall()
        self.icd_dict = {}  # normalized_name_vi_lower -> code
        for code, name_vi in rows:
            if name_vi:
                # Normalize DB key same way as queries: strip formal prefixes
                key = self._normalize_icd_name(name_vi.lower().strip())
                # Allow both normalized and original as lookup keys
                self.icd_dict[key] = code
                self.icd_dict[name_vi.lower().strip()] = code  # keep original too
        self.icd_names = list(self.icd_dict.keys())
        # Pre-compute diacritics-stripped variants for fuzzy fallback
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
        # Pre-compute diacritics-stripped variants for fuzzy fallback
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

        # Normalize Vietnamese type variants: típ/tuýp -> type (for synonym dict)
        text = re.sub(r'\b(típ|tuýp|loại)\b', 'type', text)

        # Strip parenthetical annotations: "bệnh X (loại Y)" -> "bệnh X"
        text = re.sub(r'\s*\([^)]*\)\s*', ' ', text).strip()

        # Apply synonym expansion (common clinical Vietnamese -> ICD names)
        text = _SYNONYMS.get(text, text)

        if etype == "THUỐC":
            # Strip dosage info: 500mg, 10ml, 5mg/ml, 2.5g, 0.4 MG/ML etc.
            text = re.sub(r'[\d.,]+\s*(mg|ml|mcg|g|iu|%|viên|ống|gói)(/\s*(ml|kg|m2))?', '', text, flags=re.IGNORECASE)
            # Strip stars/asterisks (masked data)
            text = re.sub(r'\*+', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
        elif etype == "CHẨN_ĐOÁN":
            # Strip common Vietnamese diagnostic prefixes from query
            text = re.sub(
                r'^(bệnh nhân bị|bệnh lý|tiền sử bị|mắc bệnh|chẩn đoán|nghi ngờ|bệnh)\s+',
                '', text
            )
            # Strip trailing qualifiers: ", không đặc hiệu" etc.
            text = re.sub(r',\s*(không đặc hiệu|không xác định|chưa xác định)$', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
        return text

    def link_entity(self, text, etype):
        """
        Main linking method. Returns list of candidate codes.
        Only applies to CHẨN_ĐOÁN and THUỐC entity types.
        """
        if etype not in ("CHẨN_ĐOÁN", "THUỐC"):
            return []

        cleaned = self._clean_text(text, etype)
        if not cleaned:
            return []

        # Filter NER false positives for THUỐC
        if etype == "THUỐC" and cleaned in _DRUG_BLACKLIST:
            return []

        ref_dict = self.icd_dict if etype == "CHẨN_ĐOÁN" else self.rx_dict
        ref_names = self.icd_names if etype == "CHẨN_ĐOÁN" else self.rx_names
        ref_names_stripped = self.icd_names_stripped if etype == "CHẨN_ĐOÁN" else self.rx_names_stripped

        # ── Layer 1: Exact Match ──
        if cleaned in ref_dict:
            return [ref_dict[cleaned]]

        # ── Layer 2: Fuzzy Match (with diacritics-stripped fallback) ──
        best_code = self._fuzzy_match(cleaned, ref_names, ref_dict, ref_names_stripped)
        if best_code:
            return [best_code]

        # ── Layer 3: Semantic Match ──
        if self.use_semantic:
            best_code = self._semantic_match(cleaned, etype, ref_names, ref_dict)
            if best_code:
                return [best_code]

        return []

    def _fuzzy_match(self, query, ref_names, ref_dict, ref_names_stripped, threshold=88.0):
        """
        Layer 2: Fuzzy string matching.
        Attempt 1: match original accented query against accented ref names.
        Attempt 2: strip diacritics from both query and ref names, then retry.
        Threshold: 88% — high precision to avoid false positives (giang mai/lậu matching).
        Relies on expanded _SYNONYMS dict for recall.
        """
        if HAS_RAPIDFUZZ:
            # Attempt 1: accented match
            result = fuzz_process.extractOne(query, ref_names, processor=fuzz_utils.default_process)
            if result and result[1] >= threshold:
                return ref_dict[result[0]]
            # Attempt 2: diacritics-stripped fallback
            query_stripped = self._strip_diacritics(query)
            result2 = fuzz_process.extractOne(query_stripped, ref_names_stripped, processor=fuzz_utils.default_process)
            if result2 and result2[1] >= threshold:
                original_name = ref_names[result2[2]]  # result2[2] is the index in ref_names_stripped
                return ref_dict[original_name]
        else:
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
        """Layer 3: Semantic embedding cosine similarity."""
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

    def close(self):
        self.db_conn.close()

    # ── Context manager support (Fix #3) ──
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False  # Don't suppress exceptions



# ── Self-test ──
if __name__ == "__main__":
    tests = [
        ("Tăng huyết áp",        "CHẨN_ĐOÁN"),   # Layer 1 exact
        ("tieu duong type 2",     "CHẨN_ĐOÁN"),   # Layer 2 stripped fallback
        ("Đái tháo đường type 2", "CHẨN_ĐOÁN"),   # Layer 2 accented
        ("Amlodipine 5mg",        "THUỐC"),        # Layer 2 + dosage strip
        ("ceftriaxon 1g",         "THUỐC"),        # Layer 2
        ("Aspirin",               "THUỐC"),        # Layer 1 exact
        ("ho khan",               "TRIỆU_CHỨNG"), # Skipped (not CHẨN_ĐOÁN/THUỐC)
    ]

    with HybridLinker(use_semantic=False) as linker:  # context manager
        print("\n--- Hybrid Linker Test Results ---")
        for text, etype in tests:
            codes = linker.link_entity(text, etype)
            print(f"  '{text}' ({etype}) -> {codes}")

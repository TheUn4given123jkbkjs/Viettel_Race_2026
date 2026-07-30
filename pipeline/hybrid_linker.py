import os
import json
import sqlite3
import re
import sys
from pathlib import Path

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
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    print("[INFO] sentence-transformers not installed. Semantic search (Layer 3) disabled.")

BASE_DIR = Path("d:/record_by_me/Viettel_race")
DB_PATH = BASE_DIR / "db" / "medical_codes.db"


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
                self.icd_dict[name_vi.lower().strip()] = code
        self.icd_names = list(self.icd_dict.keys())

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

    def _clean_text(self, text, etype):
        """Normalize entity text before lookup."""
        text = text.lower().strip()
        if etype == "THUỐC":
            # Strip dosage info: 500mg, 10ml, 5mg/ml, 0.4 MG/ML etc.
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
        """
        Main linking method. Returns list of candidate codes.
        Only applies to CHẨN_ĐOÁN and THUỐC entity types.
        """
        if etype not in ("CHẨN_ĐOÁN", "THUỐC"):
            return []

        cleaned = self._clean_text(text, etype)
        if not cleaned:
            return []

        ref_dict = self.icd_dict if etype == "CHẨN_ĐOÁN" else self.rx_dict
        ref_names = self.icd_names if etype == "CHẨN_ĐOÁN" else self.rx_names

        # ── Layer 1: Exact Match ──
        if cleaned in ref_dict:
            return [ref_dict[cleaned]]

        # ── Layer 2: Fuzzy Match ──
        best_code = self._fuzzy_match(cleaned, ref_names, ref_dict)
        if best_code:
            return [best_code]

        # ── Layer 3: Semantic Match ──
        if self.use_semantic:
            best_code = self._semantic_match(cleaned, etype, ref_names, ref_dict)
            if best_code:
                return [best_code]

        return []

    def _fuzzy_match(self, query, ref_names, ref_dict, threshold=85.0):
        """Layer 2: Fuzzy string matching."""
        if HAS_RAPIDFUZZ:
            result = fuzz_process.extractOne(query, ref_names, processor=fuzz_utils.default_process)
            if result:
                match_name, score, _ = result
                if score >= threshold:
                    return ref_dict[match_name]
        else:
            matches = difflib.get_close_matches(query, ref_names, n=1, cutoff=threshold / 100.0)
            if matches:
                return ref_dict[matches[0]]
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


# ── Self-test ──
if __name__ == "__main__":
    linker = HybridLinker(use_semantic=False)

    tests = [
        ("Tăng huyết áp", "CHẨN_ĐOÁN"),
        ("tieu duong type 2", "CHẨN_ĐOÁN"),
        ("Amlodipine 5mg", "THUỐC"),
        ("ceftriaxon 1g", "THUỐC"),
        ("Aspirin", "THUỐC"),
        ("ho khan", "TRIỆU_CHỨNG"),
    ]

    print("\n--- Hybrid Linker Test Results ---")
    for text, etype in tests:
        codes = linker.link_entity(text, etype)
        print(f"  '{text}' ({etype}) -> {codes}")

    linker.close()

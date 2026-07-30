import os
import json
import sqlite3
import re
import sys
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
output_dir = BASE_DIR / "sample_D" / "output"

def main():
    missing_drugs = []
    missing_diseases = []
    
    for jf in output_dir.rglob("*.json"):
        try:
            entities = json.loads(jf.read_text(encoding="utf-8"))
        except:
            entities = json.loads(jf.read_text(encoding="utf-8-sig", errors="replace"))
            
        for ent in entities:
            etype = ent.get("type", "")
            text = ent.get("text", "")
            candidates = ent.get("candidates", [])
            
            if not candidates:
                if etype == "THUỐC":
                    missing_drugs.append(text)
                elif etype == "CHẨN_ĐOÁN":
                    missing_diseases.append(text)
                    
    print("=" * 80)
    print("  DANH SÁCH 30 THUỐC THIẾU CANDIDATES NHIỀU NHẤT")
    print("=" * 80)
    for term, cnt in Counter(missing_drugs).most_common(30):
        print(f"  - [{cnt:3d}x] '{term}'")
        
    print("\n" + "=" * 80)
    print("  DANH SÁCH 30 CHẨN ĐOÁN THIẾU CANDIDATES NHIỀU NHẤT")
    print("=" * 80)
    for term, cnt in Counter(missing_diseases).most_common(30):
        print(f"  - [{cnt:3d}x] '{term}'")

if __name__ == "__main__":
    main()

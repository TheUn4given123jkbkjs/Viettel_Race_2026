import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = Path(__file__).resolve().parent.parent
input_dir = BASE_DIR / "sample_D" / "input"

def main():
    if not input_dir.exists():
        print(f"Error: {input_dir} does not exist.")
        return
        
    all_words = []
    txt_files = list(input_dir.rglob("*.txt"))
    for f in txt_files:
        try:
            text = f.read_text(encoding="utf-8")
        except:
            text = f.read_text(encoding="utf-8-sig", errors="replace")
        words = re.findall(r'\b\w+\b', text.lower())
        all_words.extend(words)
        
    total_tokens = len(all_words)
    unique_types = len(set(all_words))
    ttr = (unique_types / total_tokens) * 100 if total_tokens > 0 else 0
    print(f"Total tokens: {total_tokens}")
    print(f"Unique types: {unique_types}")
    print(f"TTR: {ttr:.2f}%")

if __name__ == "__main__":
    main()

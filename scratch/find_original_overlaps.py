import os
import glob
import hashlib

TEST_DIR = r"D:\AI Race\Viettel_Race_2026\input_turn2_vong1\input"
SAMPLE_DIRS = [
    r"D:\AI Race\Viettel_Race_2026\sample_A",
    r"D:\AI Race\Viettel_Race_2026\sample_C",
    r"D:\AI Race\Viettel_Race_2026\sample_D",
    r"D:\AI Race\Viettel_Race_2026\sample_E",
    r"D:\AI Race\Viettel_Race_2026\sample_Long",
]

def hash_text(text):
    # Normalize whitespaces and newlines
    clean = " ".join(text.lower().split())
    return hashlib.md5(clean.encode('utf-8')).hexdigest()

def find_overlaps():
    # Hash all test files
    test_files = glob.glob(os.path.join(TEST_DIR, "*.txt"))
    test_hashes = {}
    
    for fpath in test_files:
        with open(fpath, "r", encoding="utf-8") as f:
            content = f.read()
            test_hashes[hash_text(content)] = (os.path.basename(fpath), fpath)
            
    print(f"Total test files hashed: {len(test_hashes)}")
    
    overlaps = []
    
    for sdir in SAMPLE_DIRS:
        if not os.path.exists(sdir):
            continue
        print(f"Scanning sample directory: {sdir}")
        sample_txt_files = glob.glob(os.path.join(sdir, "**", "*.txt"), recursive=True)
        for sfile in sample_txt_files:
            with open(sfile, "r", encoding="utf-8") as f:
                content = f.read()
                h = hash_text(content)
                if h in test_hashes:
                    test_name, test_path = test_hashes[h]
                    overlaps.append((test_name, sfile))
                    
    print(f"\nFound {len(overlaps)} overlapping files!")
    for idx, (tname, sfile) in enumerate(overlaps[:10]):
        print(f"  Test: {tname} matches Sample File: {sfile}")
    if len(overlaps) > 10:
        print(f"  ... and {len(overlaps) - 10} more.")

if __name__ == "__main__":
    find_overlaps()

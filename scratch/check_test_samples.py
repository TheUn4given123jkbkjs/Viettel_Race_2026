import os
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

for i in [1, 2, 10, 50, 100]:
    path = f"input_turn2_vong1/input/{i}.txt"
    if os.path.exists(path):
        print(f"=== TEST FILE {i}.txt (Length: {os.path.getsize(path)} bytes) ===")
        with open(path, "r", encoding="utf-8") as f:
            print(f.read()[:300])
        print("\n" + "-"*40 + "\n")

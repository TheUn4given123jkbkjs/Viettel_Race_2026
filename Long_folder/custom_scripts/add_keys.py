import sys
import os
import json
import argparse
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_KEYS_FILE = os.path.join(BASE_DIR, "custom_scripts", "master_keys.json")
REFRESH_SCRIPT = os.path.join(BASE_DIR, "custom_scripts", "refresh_keys.py")

def main():
    parser = argparse.ArgumentParser(description="Thêm API Keys mới vào Kho Master Registry và tự động Refresh .env")
    parser.add_argument("--provider", type=str, required=True, choices=["gemini", "groq", "ninerouter"], help="Tên dịch vụ (gemini, groq, ninerouter)")
    parser.add_argument("--account", type=str, required=True, help="Tên/Mã tài khoản (Ví dụ: cho_hong, acc1, test_1)")
    parser.add_argument("--keys", type=str, nargs="+", required=True, help="Danh sách các API Key cần thêm (cách nhau bởi khoảng trắng)")
    args = parser.parse_args()

    if not os.path.exists(MASTER_KEYS_FILE):
        data = {"ninerouter": [], "groq": [], "gemini": []}
    else:
        with open(MASTER_KEYS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    if args.provider not in data:
        data[args.provider] = []

    added_count = 0
    existing_keys = {item["key"].strip() for item in data[args.provider]}

    for k in args.keys:
        clean_k = k.strip()
        if clean_k and clean_k not in existing_keys:
            data[args.provider].append({
                "account_id": args.account.lower().strip(),
                "key": clean_k
            })
            existing_keys.add(clean_k)
            added_count += 1

    with open(MASTER_KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Đã thêm mới {added_count} API Key cho dịch vụ '{args.provider.upper()}' (Tài khoản: {args.account}) vào master_keys.json.")
    print("🔄 Đang tự động gọi refresh_keys.py để kiểm tra sức khỏe và lưu vào .env...\n")

    subprocess.run([sys.executable, REFRESH_SCRIPT], check=True)

if __name__ == "__main__":
    main()

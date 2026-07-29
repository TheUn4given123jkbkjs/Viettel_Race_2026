import sys
import os
import requests
import json
import concurrent.futures
import time
import random

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(BASE_DIR) == "Long_folder":
    BASE_DIR = os.path.dirname(BASE_DIR)
MASTER_KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "master_keys.json")
ENV_FILE = os.path.join(BASE_DIR, ".env")

def load_master_keys():
    if not os.path.exists(MASTER_KEYS_FILE):
        print(f"❌ Không tìm thấy file master registry tại {MASTER_KEYS_FILE}")
        return {}
    with open(MASTER_KEYS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

MODELS_REGISTRY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models_registry.json")

def get_default_model_for_provider(provider: str) -> str:
    """Nạp động model đầu tiên có priority cao nhất từ models_registry.json"""
    if os.path.exists(MODELS_REGISTRY_FILE):
        try:
            with open(MODELS_REGISTRY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                models = [m for m in data.get(provider, []) if m.get("is_active", True) and m.get("isUsed", True) and not m.get("out_of_quota", False)]
                if models:
                    models.sort(key=lambda x: x.get("priority", 99))
                    return models[0]["id"]
        except Exception:
            pass
    fallback_defaults = {
        "gemini": "gemini-3.1-flash-lite",
        "groq": "llama-3.3-70b-versatile",
        "sambanova": "DeepSeek-V3.1",
        "ninerouter": "medical-gen"
    }
    return fallback_defaults.get(provider, "")

def test_single_key(provider, account_id, idx, key):
    # Dãn cách an toàn 0.8 - 1.5s tránh spam dồn dập
    time.sleep(random.uniform(0.8, 1.5))
    model_id = get_default_model_for_provider(provider)

    if provider == "ninerouter":
        url = "http://localhost:20128/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"model": model_id, "messages": [{"role": "user", "content": "Hi"}]}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            if res.status_code == 200:
                return provider, account_id, idx, key, True, "200 OK"
            return provider, account_id, idx, key, False, f"HTTP {res.status_code}"
        except Exception as e:
            return provider, account_id, idx, key, False, f"Lỗi: {e}"

    elif provider == "groq":
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"model": model_id, "messages": [{"role": "user", "content": "Hi"}]}
        for attempt in range(2):
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=25)
                if res.status_code == 200:
                    return provider, account_id, idx, key, True, "200 OK"
                elif res.status_code == 429:
                    return provider, account_id, idx, key, False, "429 Rate Limit"
                return provider, account_id, idx, key, False, f"HTTP {res.status_code}"
            except requests.exceptions.Timeout:
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                return provider, account_id, idx, key, False, "Timeout mạng"
            except Exception as e:
                return provider, account_id, idx, key, False, f"Lỗi: {e}"

    elif provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": "Hi"}]}]}
        for attempt in range(2):
            try:
                res = requests.post(url, json=payload, timeout=25)
                if res.status_code == 200:
                    return provider, account_id, idx, key, True, "200 OK"
                elif res.status_code == 429:
                    return provider, account_id, idx, key, False, "429 Rate Limit"
                return provider, account_id, idx, key, False, f"HTTP {res.status_code}"
            except requests.exceptions.Timeout:
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                return provider, account_id, idx, key, False, "Timeout mạng"
            except Exception as e:
                return provider, account_id, idx, key, False, f"Lỗi: {e}"

    elif provider == "sambanova":
        url = "https://api.sambanova.ai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"model": model_id, "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 5}
        for attempt in range(2):
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=25)
                if res.status_code == 200:
                    return provider, account_id, idx, key, True, "200 OK"
                elif res.status_code == 429:
                    return provider, account_id, idx, key, False, "429 Rate Limit"
                return provider, account_id, idx, key, False, f"HTTP {res.status_code}"
            except requests.exceptions.Timeout:
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                return provider, account_id, idx, key, False, "Timeout mạng"
            except Exception as e:
                return provider, account_id, idx, key, False, f"Lỗi: {e}"

def check_and_update_models_registry(alive_keys_by_provider):
    """Kiểm tra sức khỏe từng Model trong models_registry.json và cập nhật trạng thái out_of_quota/is_active trực tiếp vào file"""
    if not os.path.exists(MODELS_REGISTRY_FILE):
        return
        
    print("\n🔍 ĐANG KIỂM TRA SỨC KHỎE DANH MỤC MODELS VÀ CẬP NHẬT FILE 'models_registry.json'...")
    try:
        with open(MODELS_REGISTRY_FILE, "r", encoding="utf-8") as f:
            registry_data = json.load(f)
            
        updated_count = 0
        for provider, m_list in registry_data.items():
            keys = alive_keys_by_provider.get(provider, [])
            if not keys:
                continue
            
            # Thử tối đa 5 key đại diện từ các tài khoản khác nhau để tránh 429 giả do 1 key duy nhất
            sample_keys = keys[:min(5, len(keys))]
            
            for m in m_list:
                if not m.get("isUsed", True) or not m.get("is_active", True):
                    continue
                model_id = m["id"]
                model_is_alive = False
                is_quota_exceeded = False
                last_status = 0
                
                for test_key in sample_keys:
                    if provider == "gemini":
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={test_key}"
                        payload = {"contents": [{"parts": [{"text": "Hi"}]}]}
                        try:
                            res = requests.post(url, json=payload, timeout=15)
                            last_status = res.status_code
                            if res.status_code == 200:
                                model_is_alive = True
                                break
                            elif res.status_code == 429 and ("limit: 0" in res.text or "Quota exceeded" in res.text):
                                is_quota_exceeded = True
                        except Exception:
                            pass

                    elif provider == "groq":
                        url = "https://api.groq.com/openai/v1/chat/completions"
                        headers = {"Authorization": f"Bearer {test_key}", "Content-Type": "application/json"}
                        payload = {"model": model_id, "messages": [{"role": "user", "content": "Hi"}]}
                        try:
                            res = requests.post(url, headers=headers, json=payload, timeout=15)
                            last_status = res.status_code
                            if res.status_code == 200:
                                model_is_alive = True
                                break
                            elif res.status_code == 429 and ("limit: 0" in res.text or "Quota exceeded" in res.text):
                                is_quota_exceeded = True
                        except Exception:
                            pass

                if model_is_alive:
                    m["is_active"] = True
                    m["out_of_quota"] = False
                    print(f"  🟢 [MODEL OK] {provider.upper():10} | {model_id:32} -> SỐNG (200 OK)")
                elif is_quota_exceeded:
                    m["out_of_quota"] = True
                    print(f"  🛑 [MODEL QUOTA] {provider.upper():10} | {model_id:32} -> HẾT QUOTA (HTTP 429 limit:0)")
                else:
                    # Nếu chỉ nảy 429 tạm thời (RPM limit) hoặc lag mạng, GIỮ NGUYÊN trạng thái out_of_quota=False để các key khác dùng tiếp
                    m["out_of_quota"] = False
                    print(f"  🟢 [MODEL BUSY] {provider.upper():10} | {model_id:32} -> Đang nghẽn tạm thời (Giữ trạng thái Sống)")
                updated_count += 1

        with open(MODELS_REGISTRY_FILE, "w", encoding="utf-8") as f:
            json.dump(registry_data, f, ensure_ascii=False, indent=2)
            
        print(f"✅ ĐÃ ĐỒNG BỘ THÀNH CÔNG TRẠNG THÁI SỨC KHỎE CỦA MODELS VÀO FILE 'models_registry.json'!\n")
    except Exception as e:
        print(f"❌ Lỗi cập nhật models_registry.json: {e}")

def refresh_and_update_env():
    print("=" * 80)
    print("⚡ BẮT ĐẦU KIỂM TRA SỨC KHỎE TỰ ĐỘNG (DÃN CÁCH 1S) & CẬP NHẬT FILE .ENV")
    print("=" * 80)
    
    master = load_master_keys()
    if not master:
        return
        
    tasks = []
    total_tested = 0
    
    for provider, items in master.items():
        acc_counter = {}
        for item in items:
            account_id = item["account_id"]
            key = item["key"]
            acc_counter[account_id] = acc_counter.get(account_id, 0) + 1
            idx = acc_counter[account_id]
            tasks.append((provider, account_id, idx, key))
            total_tested += 1
            
    print(f"📌 Đã tải {total_tested} API Keys từ kho trung tâm master_keys.json.")
    print("🔄 Đang quét êm 4 luồng (dãn cách 1s/key) tránh nảy 429 giả & timeout...\n")
    
    alive_keys = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(test_single_key, *t) for t in tasks]
        for future in concurrent.futures.as_completed(futures):
            provider, account_id, idx, key, is_alive, msg = future.result()
            tag = f"{provider.upper()}_{account_id.upper()}_{idx}"
            if is_alive:
                print(f"  🟢 [{provider.upper():10}] {tag:30} -> SỐNG 🌟 ({msg})")
                alive_keys.append((provider, account_id, idx, key))
            else:
                print(f"  🛑 [{provider.upper():10}] {tag:30} -> ĐÓNG BĂNG/LỖI ({msg})")

    print("\n" + "=" * 80)
    print(f"🏆 TỔNG TỔNG CỘNG: Tìm thấy {len(alive_keys)}/{total_tested} API Keys đang SỐNG HOÀN HẢO 100%!")
    print("=" * 80)

    # Ghi file .env chỉ chứa các Key sống 100%
    lines = [
        "# ==============================================================================",
        "# FILE .ENV TỰ ĐỘNG CẬP NHẬT CHỈ CHỨA CÁC KEY SỐNG 100%",
        "# (Tự động sinh bởi script refresh_keys.py)",
        "# ==============================================================================\n"
    ]
    
    grouped = {}
    for provider, account_id, idx, key in alive_keys:
        if provider not in grouped:
            grouped[provider] = []
        grouped[provider].append((account_id, idx, key))

    for provider, items in grouped.items():
        lines.append(f"# --- KHÓA DỊCH VỤ {provider.upper()} ({len(items)} keys) ---")
        for account_id, idx, key in items:
            env_var = f"{provider.upper()}_KEY_{account_id.upper()}_{idx}={key}"
            lines.append(env_var)
        lines.append("")

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ ĐÃ TỰ ĐỘNG LƯU {len(alive_keys)} KEY SỐNG VÀO FILE .ENV TẠI '{ENV_FILE}'!")

    # Cập nhật tự động trạng thái của Models vào file models_registry.json
    alive_keys_dict = {}
    for provider, account_id, idx, key in alive_keys:
        if provider not in alive_keys_dict:
            alive_keys_dict[provider] = []
        alive_keys_dict[provider].append(key)

    check_and_update_models_registry(alive_keys_dict)

    print("🚀 Dàn script sinh dữ liệu và file .bat đã sẵn sàng khởi chạy ngay lập tức!")
    
    # Tự động tính toán số Worker tối ưu và cập nhật trực tiếp vào các file .bat
    try:
        from auto_adjust_workers import calculate_optimal_workers, update_batch_files
        opt = calculate_optimal_workers()
        update_batch_files(opt)
    except Exception as e:
        print(f"⚠️ Không thể tự động chỉnh worker: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Tool kiểm tra sức khỏe và tự động refresh API Keys")
    parser.add_argument("--loop", type=int, default=0, help="Thời gian tự động lặp lại tính theo phút (Ví dụ: --loop 20)")
    args = parser.parse_args()

    if args.loop > 0:
        print(f"🔁 ĐÃ BẬT CHẾ ĐỘ QUÉT TỰ ĐỘNG LẶP LAI MỖI {args.loop} PHÚT.")
        try:
            while True:
                refresh_and_update_env()
                print(f"\n⏳ Tạm nghỉ {args.loop} phút trước lượt quét kế tiếp...")
                time.sleep(args.loop * 60)
        except KeyboardInterrupt:
            print("\n🛑 Đã dừng tiến trình quét tự động.")
    else:
        refresh_and_update_env()

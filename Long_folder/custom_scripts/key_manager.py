import os
import sys
import time
import random
import threading
from typing import Dict, List, Optional, Tuple

# Đảm bảo unicode không lỗi
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.basename(BASE_DIR) == "Long_folder":
    BASE_DIR = os.path.dirname(BASE_DIR)

MODELS_REGISTRY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models_registry.json")

class KeyInfo:
    def __init__(self, key: str, account_id: str, provider: str):
        self.key = key.strip()
        self.account_id = account_id
        self.provider = provider
        self.cooldown_until = 0.0
        self.last_used_time = 0.0
        self.fail_count = 0
        self.success_count = 0

    def is_available(self, min_spacing: float = 2.0) -> bool:
        now = time.time()
        # Key khả dụng nếu hết Cooldown 429 và đã nghỉ tối thiểu min_spacing (tính theo RPM) kể từ lần gọi trước
        return (now >= self.cooldown_until) and (now - self.last_used_time >= min_spacing)

    def mark_used(self):
        self.last_used_time = time.time()

    def mark_rate_limited(self, cooldown_seconds: float = 60.0):
        self.cooldown_until = time.time() + cooldown_seconds
        self.fail_count += 1

    def mark_success(self):
        self.success_count += 1

class AccountRoundRobinKeyManager:
    """
    Trình quản lý API Key và Models tập trung (Configuration-Driven & Data-Driven Architecture).
    - Tự động nạp Metadata Models từ `models_registry.json`.
    - Tự động nạp API Keys từ file `.env` (Hot Reload khi file thay đổi).
    - Quản lý xoay vòng kép: Xoay Account (Key) + Xoay Model khả dụng.
    """
    def __init__(self, env_path: Optional[str] = None):
        self._lock = threading.Lock()
        if env_path is None:
            env_path = os.path.join(BASE_DIR, ".env")
        self.env_path = env_path
        self.last_env_mtime = 0.0
        self.last_models_mtime = 0.0
        
        self.keys_by_provider: Dict[str, Dict[str, List[KeyInfo]]] = {
            "gemini": {},
            "groq": {},
            "sambanova": {},
            "ninerouter": {}
        }
        self.account_indices: Dict[str, int] = {"gemini": 0, "groq": 0, "sambanova": 0, "ninerouter": 0}
        self.key_indices_per_account: Dict[str, Dict[str, int]] = {"gemini": {}, "groq": {}, "sambanova": {}, "ninerouter": {}}
        self.account_in_use: Dict[str, Dict[str, int]] = {"gemini": {}, "groq": {}, "sambanova": {}, "ninerouter": {}}
        self.account_last_used: Dict[str, Dict[str, float]] = {"gemini": {}, "groq": {}, "sambanova": {}, "ninerouter": {}}
        
        self.models_by_provider: Dict[str, List[dict]] = {}
        self.model_indices: Dict[str, int] = {}

        self._load_models_registry()
        self._load_keys_from_env(self.env_path)

    def _load_models_registry(self):
        """Nạp động danh sách Models từ models_registry.json"""
        if not os.path.exists(MODELS_REGISTRY_FILE):
            print(f"⚠️  Cảnh báo: Không tìm thấy file registry models tại '{MODELS_REGISTRY_FILE}'")
            return
            
        try:
            self.last_models_mtime = os.path.getmtime(MODELS_REGISTRY_FILE)
            import json
            with open(MODELS_REGISTRY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            self.models_by_provider = {}
            for provider, m_list in data.items():
                active_models = [
                    m for m in m_list 
                    if m.get("is_active", True) and m.get("isUsed", True) and not m.get("out_of_quota", False)
                ]
                active_models.sort(key=lambda x: x.get("priority", 99))
                self.models_by_provider[provider] = active_models
                if provider not in self.model_indices:
                    self.model_indices[provider] = 0
            
            total_active = sum(len(m) for m in self.models_by_provider.values())
            print(f"  ✓ [REGISTRY] Nạp thành công {total_active} active models từ models_registry.json")
        except Exception as e:
            print(f"❌ Lỗi nạp models_registry.json: {e}")

    def get_next_model(self, provider: str = "gemini") -> Optional[dict]:
        """Lấy model tiếp theo khả dụng từ registry theo cơ chế Round-Robin"""
        with self._lock:
            self._check_and_reload_files()
            provider = provider.lower()
            m_list = self.models_by_provider.get(provider, [])
            if not m_list:
                return None
            idx = self.model_indices.get(provider, 0)
            model_info = m_list[idx % len(m_list)]
            self.model_indices[provider] = (idx + 1) % len(m_list)
            return model_info

    def get_next_gemini_model(self) -> str:
        """Hàm tương thích lấy ID model Gemini tiếp theo"""
        m = self.get_next_model("gemini")
        return m["id"] if m else "gemini-3.1-flash-lite"

    def update_model_status_in_registry(self, provider: str, model_id: str, is_active: bool = True, out_of_quota: bool = False):
        """Đồng bộ trạng thái Model trực tiếp vào file models_registry.json trên đĩa"""
        with self._lock:
            if not os.path.exists(MODELS_REGISTRY_FILE):
                return
            try:
                import json
                with open(MODELS_REGISTRY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                provider = provider.lower()
                if provider in data:
                    updated = False
                    for m in data[provider]:
                        if m.get("id") == model_id:
                            m["is_active"] = is_active
                            m["out_of_quota"] = out_of_quota
                            updated = True
                            break
                    if updated:
                        with open(MODELS_REGISTRY_FILE, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        print(f"  📝 [REGISTRY UPDATED] Đã cập nhật Model '{model_id}' ({provider.upper()}) -> active={is_active}, out_of_quota={out_of_quota}")
                        self._load_models_registry()
            except Exception as e:
                print(f"❌ Lỗi ghi file models_registry.json: {e}")

    def mark_model_out_of_quota(self, provider: str, model_id: str):
        """Đánh dấu Model bị cạn Quota và lưu vào file models_registry.json"""
        self.update_model_status_in_registry(provider, model_id, is_active=True, out_of_quota=True)

    def _check_and_reload_files(self):
        """Hot-Reload tự động khi file .env hoặc models_registry.json thay đổi trên đĩa"""
        if os.path.exists(self.env_path):
            try:
                mtime = os.path.getmtime(self.env_path)
                if mtime > self.last_env_mtime and self.last_env_mtime > 0:
                    print(f"\n🔄 [HOT-RELOAD] Phát hiện file .env vừa cập nhật! Nạp lại danh sách Key mới...")
                    self._load_keys_from_env(self.env_path)
            except Exception:
                pass
                
        if os.path.exists(MODELS_REGISTRY_FILE):
            try:
                mtime = os.path.getmtime(MODELS_REGISTRY_FILE)
                if mtime > self.last_models_mtime and self.last_models_mtime > 0:
                    print(f"\n🔄 [HOT-RELOAD] Phát hiện models_registry.json vừa cập nhật! Nạp lại danh sách Models...")
                    self._load_models_registry()
            except Exception:
                pass

    def _load_keys_from_env(self, env_path: str):
        if not os.path.exists(env_path):
            print(f"⚠️  Cảnh báo: Không tìm thấy file .env tại '{env_path}'")
            return
            
        try:
            self.last_env_mtime = os.path.getmtime(env_path)
        except Exception:
            pass
            
        # Giữ lại trạng thái cooldown/fail_count của các key cũ
        old_key_states = {}
        for p, accs in self.keys_by_provider.items():
            for acc, k_list in accs.items():
                for k_info in k_list:
                    old_key_states[k_info.key] = (k_info.cooldown_until, k_info.last_used_time, k_info.fail_count, k_info.success_count)

        # Reset danh sách
        self.keys_by_provider = {
            "gemini": {},
            "groq": {},
            "sambanova": {},
            "ninerouter": {}
        }
        self.account_indices = {"gemini": 0, "groq": 0, "sambanova": 0, "ninerouter": 0}
        self.key_indices_per_account = {"gemini": {}, "groq": {}, "sambanova": {}, "ninerouter": {}}

        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                parts = line.split("=", 1)
                var_name = parts[0].strip()
                var_val = parts[1].strip()
                
                if not var_val:
                    continue

                if var_name.startswith("GEMINI_KEY_"):
                    sub = var_name[len("GEMINI_KEY_"):]
                    account_id = sub.rsplit("_", 1)[0].lower()
                    self._add_key("gemini", account_id, var_val)
                    
                elif var_name.startswith("GROQ_KEY_"):
                    sub = var_name[len("GROQ_KEY_"):]
                    account_id = sub.rsplit("_", 1)[0].lower()
                    self._add_key("groq", account_id, var_val)

                elif var_name.startswith("NINEROUTER_KEY_"):
                    sub = var_name[len("NINEROUTER_KEY_"):]
                    account_id = sub.rsplit("_", 1)[0].lower()
                    self._add_key("ninerouter", account_id, var_val)

                elif var_name.startswith("SAMBANOVA_KEY_"):
                    sub = var_name[len("SAMBANOVA_KEY_"):]
                    account_id = sub.rsplit("_", 1)[0].lower()
                    self._add_key("sambanova", account_id, var_val)

        # Khôi phục trạng thái cũ nếu key vẫn còn
        for p, accs in self.keys_by_provider.items():
            for acc, k_list in accs.items():
                for k_info in k_list:
                    if k_info.key in old_key_states:
                        cd, lut, fc, sc = old_key_states[k_info.key]
                        k_info.cooldown_until = cd
                        k_info.last_used_time = lut
                        k_info.fail_count = fc
                        k_info.success_count = sc

        # Đếm tổng số key nạp được
        for provider, accounts in self.keys_by_provider.items():
            total = sum(len(keys) for keys in accounts.values())
            print(f"  ✓ Nạp thành công {total} keys {provider.upper()} từ {len(accounts)} tài khoản: {list(accounts.keys())}")

    def _add_key(self, provider: str, account_id: str, key_str: str):
        if account_id not in self.keys_by_provider[provider]:
            self.keys_by_provider[provider][account_id] = []
            self.key_indices_per_account[provider][account_id] = 0
            
        key_info = KeyInfo(key_str, account_id, provider)
        self.keys_by_provider[provider][account_id].append(key_info)

    def release_key(self, key_info: KeyInfo):
        """Giải phóng trạng thái BẬN của tài khoản khi Worker hoàn thành request"""
        if not key_info:
            return
        provider = key_info.provider.lower()
        acc_name = key_info.account_id.lower()
        if provider in self.account_in_use and acc_name in self.account_in_use[provider]:
            curr = self.account_in_use[provider][acc_name]
            self.account_in_use[provider][acc_name] = max(0, curr - 1)

    def get_next_key(self, provider: str = "gemini") -> Optional[Tuple[str, str, KeyInfo]]:
        """
        Thuật toán Smart Idle-Account Priority Scheduler (LRU Account Allocation):
        1. Lọc tất cả các Tài khoản đang HOÀN TOÀN RẢNH (in_use == 0) và không dính 429.
        2. Sắp xếp ưu tiên chọn Tài khoản NGHỈ LÂU NHẤT (last_used_time nhỏ nhất).
        3. Tự động đánh dấu BẬN (in_use += 1) để các Worker khác KHÔNG trùng vào cùng tài khoản này.
        """
        with self._lock:
            self._check_and_reload_files()
            provider = provider.lower()
            accounts_dict = self.keys_by_provider.get(provider, {})
            if not accounts_dict:
                print(f"❌ Không tìm thấy API key cho dịch vụ '{provider}'")
                return None
                
            now = time.time()
            account_stats = []
            
            # Xáo trộn danh sách tài khoản ngẫu nhiên theo PID của tiến trình
            # Tránh việc mọi tiến trình Worker song song đều chọn cùng tài khoản đầu tiên khi last_used bằng nhau
            acc_names = list(accounts_dict.keys())
            rng = random.Random(os.getpid() + int(time.time() * 1000) % 1000)
            rng.shuffle(acc_names)
            
            for acc_name in acc_names:
                keys_in_acc = accounts_dict[acc_name]
                if not keys_in_acc:
                    continue
                # Tìm các key khả dụng trong tài khoản
                available_keys = [k for k in keys_in_acc if k.is_available(min_spacing=1.0)]
                if not available_keys:
                    continue
                
                in_use = self.account_in_use[provider].get(acc_name, 0)
                last_used = self.account_last_used[provider].get(acc_name, 0.0)
                account_stats.append({
                    "acc_name": acc_name,
                    "in_use": in_use,
                    "last_used": last_used,
                    "available_keys": available_keys,
                    "keys_in_acc": keys_in_acc
                })

            if not account_stats:
                # Nếu tất cả các Key đều đang bị dính Cooldown Rate-Limit
                min_cooldown = float("inf")
                best_key = None
                for acc_name, keys_in_acc in accounts_dict.items():
                    for k_info in keys_in_acc:
                        if k_info.cooldown_until < min_cooldown:
                            min_cooldown = k_info.cooldown_until
                            best_key = k_info

                wait_time = max(1.0, min_cooldown - time.time())
                print(f"⚠️  TOÀN BỘ Key {provider.upper()} đang dính Cooldown. Cần chờ {wait_time:.1f}s...")
                return None if best_key is None else (best_key.key, best_key.account_id, best_key)

            # Sắp xếp ưu tiên tuyệt đối:
            # Tier 1: in_use ASC (tài khoản rảnh 0 worker đang dùng được xếp đầu)
            # Tier 2: last_used ASC (tài khoản nghỉ lâu nhất xếp đầu)
            account_stats.sort(key=lambda x: (x["in_use"], x["last_used"]))
            
            chosen_acc = account_stats[0]
            acc_name = chosen_acc["acc_name"]
            available_keys = chosen_acc["available_keys"]
            keys_in_acc = chosen_acc["keys_in_acc"]
            
            # Chọn key theo Round Robin trong tài khoản
            start_key_idx = self.key_indices_per_account[provider].get(acc_name, 0)
            k_idx = start_key_idx % len(available_keys)
            key_info = available_keys[k_idx]
            
            # Cập nhật trạng thái bận & thời gian sử dụng
            key_info.mark_used()
            self.key_indices_per_account[provider][acc_name] = (start_key_idx + 1) % len(keys_in_acc)
            self.account_in_use[provider][acc_name] = self.account_in_use[provider].get(acc_name, 0) + 1
            self.account_last_used[provider][acc_name] = now
            
            return key_info.key, key_info.account_id, key_info

    def mark_rate_limited(self, key_info: KeyInfo, cooldown_seconds: float = 120.0):
        with self._lock:
            provider = key_info.provider.lower()
            account_id = key_info.account_id.lower()
            if provider in self.keys_by_provider and account_id in self.keys_by_provider[provider]:
                for k_info in self.keys_by_provider[provider][account_id]:
                    k_info.mark_rate_limited(cooldown_seconds)
            print(f"  🛑 Đã đóng băng 429 toàn bộ Key thuộc Tài Khoản '{account_id.upper()}' trong {cooldown_seconds}s.")
            self.release_key(key_info)

    def mark_success(self, key_info: KeyInfo):
        with self._lock:
            key_info.mark_success()
            self.release_key(key_info)

# Khởi tạo Singleton Global Instance
key_manager = AccountRoundRobinKeyManager()

if __name__ == "__main__":
    print("\n--- KIỂM TRA XOAY VÒNG DUAL (KEY + MODEL ROUTER) ---")
    print("Xoay thử 5 lần liên tiếp với Gemini:")
    for step in range(1, 6):
        res = key_manager.get_next_key("gemini")
        m_info = key_manager.get_next_model("gemini")
        if res and m_info:
            k_str, acc_id, k_obj = res
            print(f" Lần {step}: Key [{k_str[:12]}...] (TK: {acc_id.upper()}) | Model: [{m_info['id']}] (RPD: {m_info['rpd']})")
        time.sleep(0.2)

    print("\nXoay thử 5 lần liên tiếp với Groq:")
    for step in range(1, 6):
        res = key_manager.get_next_key("groq")
        m_info = key_manager.get_next_model("groq")
        if res and m_info:
            k_str, acc_id, k_obj = res
            print(f" Lần {step}: Key [{k_str[:12]}...] (TK: {acc_id.upper()}) | Model: [{m_info['id']}] (RPD: {m_info['rpd']})")
        time.sleep(0.2)

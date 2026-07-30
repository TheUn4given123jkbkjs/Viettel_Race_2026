"""
═══════════════════════════════════════════════════════════════════
  GROQ_RUNNER.py — Groq-Only Smart Parallel Runner V1.0
  Du an: Viettel AI Race 2026
  -----------------------------------------------------------------
  CHIEN LUOC TOI UU GROQ (based on GROQ_API_ANALYSIS_REPORT.md):

  Van de cot loi: Quota tinh theo CAP TAI KHOAN (Account Level),
  KHONG theo API Key. Nhieu key cung tai khoan = cung 1 be quota.

  Giai phap:
    - Xoay vong THEO ACCOUNT (khong phai theo key)
    - Doc response headers real-time de biet remaining tokens/requests
    - Tu dong chon model phu hop theo do phuc tap yeu cau:
        TOP 1: llama-3.3-70b-versatile  (12K TPM / 1K RPD per account)
        TOP 2: qwen/qwen3.6-27b         (8K  TPM / 1K RPD per account)
        TOP 3: groq/compound            (70K TPM / 250 RPD per account)
    - Back-pressure dua tren x-ratelimit-remaining-tokens header
    - Fallback giua model khi 1 model bi rate-limit

  Cong thuc tinh delay an toan:
    - TPM = tokens/phut. Moi request y khoa ~ 800-1200 tokens.
    - llama-3.3-70b: 12000 TPM -> max ~12 req/phut/account -> delay >= 5.2s
    - qwen3.6-27b  : 8000  TPM -> max ~8  req/phut/account -> delay >= 7.7s
    - groq/compound: 70000 TPM -> max ~38 req/phut/account -> delay >= 1.6s
      NHUNG bi gioi han 250 RPD -> chi dung cho benh an dai phuc tap
═══════════════════════════════════════════════════════════════════
"""
import os
import sys
import json
import time
import math
import random
import re
import threading
import argparse
import subprocess
import requests
from typing import Dict, List, Optional, Tuple

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ─── PATH SETUP ───────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
LONG_FOLDER = os.path.dirname(SCRIPT_DIR)
BASE_DIR    = os.path.dirname(LONG_FOLDER)
if os.path.basename(LONG_FOLDER) != "Long_folder":
    BASE_DIR = LONG_FOLDER

MASTER_KEYS_FILE = os.path.join(SCRIPT_DIR, "master_keys.json")

# ─── TOP 3 GROQ MODELS (theo GROQ_API_ANALYSIS_REPORT.md) ─────────
#
# Thong so gioi han PER-ACCOUNT (khong phai per-key):
#   tpm       = Token Per Minute toi da cho 1 account
#   rpd       = Request Per Day toi da cho 1 account
#   avg_tokens= Uoc tinh token trung binh moi request y khoa
#   safe_delay= Delay toi thieu giua 2 request (giay) de khong vuot TPM
#               = (60 / (tpm / avg_tokens)) * 1.15  (safety factor 15%)
#
GROQ_MODELS = [
    {
        "id"         : "llama-3.3-70b-versatile",
        "displayName": "Llama 3.3 70B",
        "priority"   : 1,
        "tpm"        : 12000,
        "rpd"        : 1000,
        "avg_tokens" : 900,
        "safe_delay" : 5.2,   # = (60 / (12000/900)) * 1.15
        "use_for"    : "chat luong cao, ICD-10/RxNorm chinh xac",
    },
    {
        "id"         : "qwen/qwen3.6-27b",
        "displayName": "Qwen 3.6 27B",
        "priority"   : 2,
        "tpm"        : 8000,
        "rpd"        : 1000,
        "avg_tokens" : 900,
        "safe_delay" : 7.7,   # = (60 / (8000/900)) * 1.15
        "use_for"    : "suy luan logic, tuan thu JSON nghiem ngat",
    },
    {
        "id"         : "llama-3.1-8b-instant",
        "displayName": "Llama 3.1 8B Instant",
        "priority"   : 3,
        "tpm"        : 6000,
        "rpd"        : 14400,
        "avg_tokens" : 900,
        "safe_delay" : 10.0,
        "use_for"    : "nhân bản dữ liệu siêu tốc, 14.4K RPD/tài khoản",
    },
]


# ─── GROQ ACCOUNT MANAGER ─────────────────────────────────────────

class GroqAccountManager:
    """
    Quan ly xoay vong API theo ACCOUNT (khong theo key).
    Vì Groq tinh quota theo tai khoan, khong phai theo key,
    xoay key trong cung account KHONG giup thoat rate limit.

    Thay vao do: xoay ACCOUNT, theo doi state per-account x per-model.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self.accounts: Dict[str, dict] = {}
        self._account_order: List[str] = []
        self._account_idx = 0
        self._load_accounts()

    def _load_accounts(self):
        if not os.path.exists(MASTER_KEYS_FILE):
            print(f"[ERROR] Khong tim thay {MASTER_KEYS_FILE}")
            return

        with open(MASTER_KEYS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        groq_keys = data.get("groq", [])
        grouped: Dict[str, List[str]] = {}
        for entry in groq_keys:
            aid = entry["account_id"]
            grouped.setdefault(aid, []).append(entry["key"])

        for account_id, keys in grouped.items():
            model_states = {}
            for m in GROQ_MODELS:
                model_states[m["id"]] = {
                    "remaining_requests": m["rpd"],
                    "remaining_tokens"  : m["tpm"],
                    "cooldown_until"    : 0.0,
                    "daily_used"        : 0,
                    "last_call_time"    : 0.0,
                    "consecutive_fails" : 0,
                }
            self.accounts[account_id] = {
                "keys"           : keys,
                "current_key_idx": 0,
                "models"         : model_states,
            }

        self._account_order = list(self.accounts.keys())
        print(f"[OK] Da nap {len(self._account_order)} Groq accounts: {', '.join(self._account_order)}")
        for m in GROQ_MODELS:
            daily_total = len(self._account_order) * m["rpd"]
            print(f"     #{m['priority']} {m['displayName']:20s} "
                  f"TPM={m['tpm']:,}/acc  RPD={m['rpd']:,}/acc  "
                  f"delay={m['safe_delay']}s  "
                  f"=> ~{daily_total:,} req/ngay tong cong")

    def _get_key_for_account(self, account_id: str) -> str:
        """Xoay key trong account (chi de phan tan analytics, khong thoat quota)"""
        acc = self.accounts[account_id]
        idx = acc["current_key_idx"] % len(acc["keys"])
        acc["current_key_idx"] = idx + 1
        return acc["keys"][idx]

    def _parse_reset_seconds(self, reset_str: Optional[str]) -> float:
        """
        Parse header 'x-ratelimit-reset-requests' thanh float seconds.
        Vi du: '1m26.4s' -> 86.4, '6s' -> 6.0, '185ms' -> 0.185
        """
        if not reset_str:
            return 60.0
        total = 0.0
        m = re.search(r"(\d+\.?\d*)m", reset_str)
        if m:
            total += float(m.group(1)) * 60
        s = re.search(r"(\d+\.?\d*)s", reset_str)
        if s:
            total += float(s.group(1))
        ms = re.search(r"(\d+\.?\d*)ms", reset_str)
        if ms:
            total += float(ms.group(1)) / 1000
        return max(total, 1.0)

    def get_next_available_slot(self) -> Optional[Tuple[str, str, dict]]:
        """
        Tim (account_id, api_key, model_cfg) kha dung.
        Uu tien: account chua cooldown + model priority cao nhat + du RPD + du safe_delay.
        """
        with self._lock:
            now = time.time()
            n = len(self._account_order)
            for offset in range(n):
                account_id = self._account_order[(self._account_idx + offset) % n]
                acc = self.accounts[account_id]

                for model_cfg in GROQ_MODELS:
                    mid = model_cfg["id"]
                    ms  = acc["models"][mid]

                    if now < ms["cooldown_until"]:
                        continue
                    if ms["daily_used"] >= model_cfg["rpd"]:
                        continue
                    elapsed = now - ms["last_call_time"]
                    if elapsed < model_cfg["safe_delay"]:
                        continue

                    # Slot kha dung
                    self._account_idx = (self._account_idx + 1) % n
                    api_key = self._get_key_for_account(account_id)
                    return account_id, api_key, model_cfg

        return None

    def wait_for_slot(self, max_wait: float = 300.0) -> Optional[Tuple[str, str, dict]]:
        """Cho den khi co slot kha dung, toi da max_wait giay"""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            slot = self.get_next_available_slot()
            if slot:
                return slot
            time.sleep(0.5)
        return None

    def mark_used(self, account_id: str, model_id: str,
                  remaining_requests: Optional[int] = None,
                  remaining_tokens: Optional[int] = None):
        """Cap nhat state sau khi goi thanh cong"""
        with self._lock:
            ms = self.accounts[account_id]["models"][model_id]
            ms["last_call_time"] = time.time()
            ms["daily_used"] += 1
            ms["consecutive_fails"] = 0
            if remaining_requests is not None:
                ms["remaining_requests"] = remaining_requests
            if remaining_tokens is not None:
                ms["remaining_tokens"] = remaining_tokens

    def mark_rate_limited(self, account_id: str, model_id: str,
                          reset_requests: Optional[str] = None,
                          reset_tokens: Optional[str] = None):
        """Dat cooldown khi bi 429, dua tren reset header chinh xac"""
        with self._lock:
            ms = self.accounts[account_id]["models"][model_id]
            ms["consecutive_fails"] += 1
            cooldown = self._parse_reset_seconds(reset_requests or reset_tokens)
            cooldown += random.uniform(2.0, 8.0)  # jitter tranh thundering herd
            ms["cooldown_until"] = time.time() + cooldown
            print(f"  [429] [{account_id}] {model_id[:20]} -> cooldown {cooldown:.1f}s "
                  f"(reset_req={reset_requests}, reset_tok={reset_tokens})")

    def mark_exhausted(self, account_id: str, model_id: str):
        """Danh dau account+model het RPD ngay"""
        with self._lock:
            for m in GROQ_MODELS:
                if m["id"] == model_id:
                    self.accounts[account_id]["models"][model_id]["daily_used"] = m["rpd"]
                    break

    def get_status_summary(self) -> str:
        now = time.time()
        lines = ["\n=== GROQ ACCOUNT STATUS ==="]
        for aid in self._account_order:
            acc = self.accounts[aid]
            parts = []
            for m in GROQ_MODELS:
                mid = m["id"]
                ms  = acc["models"][mid]
                if now < ms["cooldown_until"]:
                    wait = int(ms["cooldown_until"] - now)
                    parts.append(f"{m['displayName'][:8]}:COOL({wait}s)")
                elif ms["daily_used"] >= m["rpd"]:
                    parts.append(f"{m['displayName'][:8]}:DONE")
                else:
                    left = m["rpd"] - ms["daily_used"]
                    parts.append(f"{m['displayName'][:8]}:OK({left})")
            lines.append(f"  [{aid:12s}] {' | '.join(parts)}")
        return "\n".join(lines)


# ─── CORE API CALL ────────────────────────────────────────────────

def call_groq_api(api_key: str, model_id: str, messages: list,
                  max_tokens: int = 1500, temperature: float = 0.7,
                  timeout: int = 60) -> Tuple[Optional[str], dict]:
    """
    Goi Groq API, tra ve (content, rate_info).
    BAT BUOC co User-Agent de vuot Cloudflare WAF (tranh HTTP 403 Error 1010).
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type" : "application/json",
        # QUAN TRONG: phai co User-Agent de vuot Cloudflare WAF
        "User-Agent"   : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    payload = {
        "model"      : model_id,
        "messages"   : messages,
        "max_tokens" : max_tokens,
        "temperature": temperature,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        rate_info = {
            "limit_requests"    : resp.headers.get("x-ratelimit-limit-requests"),
            "limit_tokens"      : resp.headers.get("x-ratelimit-limit-tokens"),
            "remaining_requests": resp.headers.get("x-ratelimit-remaining-requests"),
            "remaining_tokens"  : resp.headers.get("x-ratelimit-remaining-tokens"),
            "reset_requests"    : resp.headers.get("x-ratelimit-reset-requests"),
            "reset_tokens"      : resp.headers.get("x-ratelimit-reset-tokens"),
            "status_code"       : resp.status_code,
        }
        if resp.status_code == 200:
            body    = resp.json()
            content = body["choices"][0]["message"]["content"]
            return content, rate_info
        else:
            rate_info["error_body"] = resp.text[:500]
            return None, rate_info
    except requests.exceptions.Timeout:
        return None, {"status_code": -1, "error_body": "TIMEOUT"}
    except Exception as e:
        return None, {"status_code": -2, "error_body": str(e)}


# ─── SMART CALL WITH BACK-PRESSURE ───────────────────────────────

def smart_call(manager: GroqAccountManager, messages: list,
               max_tokens: int = 1500, temperature: float = 0.7,
               max_retries: int = 5) -> Optional[str]:
    """
    Goi API thong minh: tu chon account+model, doc headers,
    tu back-pressure khi token buffer gan can.
    """
    for attempt in range(max_retries):
        slot = manager.wait_for_slot(max_wait=300.0)
        if slot is None:
            print("  [ERR] Khong tim slot nao kha dung sau 5 phut.")
            return None

        account_id, api_key, model_cfg = slot
        model_id = model_cfg["id"]

        content, rate_info = call_groq_api(
            api_key=api_key, model_id=model_id,
            messages=messages, max_tokens=max_tokens, temperature=temperature,
        )
        code = rate_info.get("status_code", -1)

        if code == 200:
            rem_req = rate_info.get("remaining_requests")
            rem_tok = rate_info.get("remaining_tokens")
            try:
                rem_req = int(rem_req) if rem_req else None
                rem_tok = int(rem_tok) if rem_tok else None
            except (ValueError, TypeError):
                rem_req = rem_tok = None

            manager.mark_used(account_id, model_id, rem_req, rem_tok)

            # Back-pressure: neu token buffer < 20% -> nghi them
            if rem_tok is not None and rem_tok < model_cfg["tpm"] * 0.2:
                extra = model_cfg["safe_delay"] * 2
                print(f"  [BACKPRESSURE] [{account_id}] rem_tok={rem_tok} < 20% -> sleep {extra:.1f}s")
                time.sleep(extra)

            print(f"  [OK] [{account_id}] {model_cfg['displayName']} | "
                  f"rem_req={rem_req} rem_tok={rem_tok}")
            return content

        elif code == 429:
            manager.mark_rate_limited(
                account_id, model_id,
                reset_requests=rate_info.get("reset_requests"),
                reset_tokens  =rate_info.get("reset_tokens"),
            )
            continue  # thu ngay voi account khac, manager tu xu ly cooldown

        elif code == 403:
            print(f"  [403] [{account_id}] Cloudflare WAF block (attempt {attempt+1})")
            manager.mark_rate_limited(account_id, model_id, "5m")
            continue

        elif code in (-1, -2):
            print(f"  [ERR] [{account_id}] {rate_info.get('error_body')} (attempt {attempt+1})")
            time.sleep(5)
            continue

        else:
            err = rate_info.get("error_body", "")
            print(f"  [ERR] [{account_id}] HTTP {code}: {err[:200]}")
            if "decommissioned" in err.lower() or "model not found" in err.lower():
                manager.mark_exhausted(account_id, model_id)
            else:
                time.sleep(3)
            continue

    print(f"  [FAIL] Het {max_retries} lan thu.")
    return None


# ─── WORKER LAUNCHER ─────────────────────────────────────────────

def calculate_groq_optimal_workers(num_accounts: int) -> int:
    """
    Tinh so worker toi uu cho Groq-only mode.

    Throughput an toan = num_accounts * (60 / safe_delay_model1) * 0.85
    Moi worker xu ly ~20s/mau (co overhead parse + write)
    Optimal = floor(throughput / (60/20)) capped [2, 20]
    """
    primary_delay = GROQ_MODELS[0]["safe_delay"]  # 5.2s cho llama-3.3-70b
    max_rpm_safe  = num_accounts * (60.0 / primary_delay) * 0.85
    worker_cycle  = 20.0  # giay / mau
    optimal       = math.floor(max_rpm_safe / (60.0 / worker_cycle))
    return max(2, min(20, optimal))


def launch_groq_workers(member: str, num_samples: int, workers: int = 8, model_id: str = None, background: bool = False):
    """Tính worker tối ưu và khởi chạy song song với provider=groq hỗ trợ Model Isolation"""
    manager_probe = GroqAccountManager()
    num_accounts  = len(manager_probe.accounts)

    if num_accounts == 0:
        print("[ERR] Khong co Groq account nao. Huy.")
        return

    if workers > 0:
        num_workers = min(workers, 20)
    else:
        num_workers = calculate_groq_optimal_workers(num_accounts)
    chunk = math.ceil(num_samples / num_workers)
    ranges = []
    for i in range(num_workers):
        s = i * chunk + 1
        e = min((i + 1) * chunk, num_samples)
        if s <= num_samples:
            ranges.append((s, e))

    print("\n" + "=" * 72)
    print("  GROQ RUNNER -- TOI UU HOA GROQ PARALLEL (MODEL ISOLATION)")
    print("=" * 72)
    print(f"  Groq accounts doc lap  : {num_accounts}")
    print(f"  So worker toi uu       : {num_workers}")
    print(f"  Model phan lap chuyên : {model_id if model_id else 'LUÂN PHIÊN TAT CA'}")
    print(f"  Tong mau can sinh      : {num_samples}")
    print(f"  Thanh vien / thu muc   : sample_{member}")
    print(f"  Che do chay            : {'BACKGROUND (ngam)' if background else 'CMD NOI'}")
    print("=" * 72 + "\n")

    model_cmd_flag = f"--model {model_id}" if model_id else ""

    if background:
        log_dir = os.path.join(LONG_FOLDER, "logs", f"sample_{member}")
        os.makedirs(log_dir, exist_ok=True)
        for idx, (s, e) in enumerate(ranges, 1):
            log_suffix = f"groq_{model_id.replace('/', '_')}_worker_{idx}.log" if model_id else f"groq_worker_{idx}.log"
            log_path = os.path.join(log_dir, log_suffix)
            f_log = open(log_path, "a", encoding="utf-8")
            cmd_args = [
                sys.executable,
                os.path.join(SCRIPT_DIR, "generate_train_data_v3.py"),
                "--member", member, "--provider", "groq",
                "--start_idx", str(s), "--end_idx", str(e),
            ]
            if model_id:
                cmd_args.extend(["--model", model_id])
            flags = 0x08000000 if os.name == "nt" else 0
            subprocess.Popen(cmd_args, cwd=LONG_FOLDER,
                             stdout=f_log, stderr=f_log, creationflags=flags)
        print(f"[OK] Da kich hoat {len(ranges)} Groq Workers ngam ({model_id if model_id else 'ALL'})!")
    else:
        for idx, (s, e) in enumerate(ranges, 1):
            tag = model_id.split('/')[-1] if model_id else "ALL"
            title = f"[sample_{member}] Groq Worker {idx} ({tag}) [{s}-{e}]"
            cmd = (
                f'start "{title}" cmd /k "'
                f'python custom_scripts\\generate_train_data_v3.py '
                f'--member {member} --provider groq '
                f'--start_idx {s} --end_idx {e} {model_cmd_flag}"'
            )
            subprocess.run(cmd, shell=True, cwd=LONG_FOLDER)
        print(f"[OK] Da bat {len(ranges)} cua so CMD Groq Workers ({tag})!")


# ─── ENTRYPOINT ──────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Groq-Only Smart Parallel Runner -- Viettel AI Race 2026"
    )
    parser.add_argument("--member",      type=str, default="C",
                        help="Ten thanh vien / thu muc dau ra (sample_<member>)")
    parser.add_argument("--num_samples", type=int, default=2000,
                        help="Tong so mau can sinh")
    parser.add_argument("--workers",     type=int, default=0,
                        help="So luong worker chay song song (0 = tu dong tinh toan, >0 = ep so worker)")
    parser.add_argument("--model",       type=str, default=None,
                        help="ID model phan lap (Model Isolation Architecture)")
    parser.add_argument("--background",  action="store_true",
                        help="Chay ngam khong hien cua so CMD")
    parser.add_argument("--status",     action="store_true",
                        help="Chi hien thi trang thai accounts")
    parser.add_argument("--test_call",  action="store_true",
                        help="Chay 1 test call kiem tra key va rate-limit headers")
    args = parser.parse_args()

    manager = GroqAccountManager()

    if args.status:
        print(manager.get_status_summary())

    elif args.test_call:
        print("\n[TEST] Kiem tra key Groq va doc rate-limit headers real-time")
        print("-" * 60)
        msgs = [{"role": "user", "content": "Reply with exactly: GROQ_OK"}]
        result = smart_call(manager, msgs, max_tokens=20, temperature=0.0)
        if result:
            print(f"\n[OK] Response: {result.strip()}")
        else:
            print("[FAIL] Test call that bai.")
        print(manager.get_status_summary())

    else:
        launch_groq_workers(args.member, args.num_samples, workers=args.workers, model_id=args.model, background=args.background)

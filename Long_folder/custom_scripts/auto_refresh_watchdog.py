"""
auto_refresh_watchdog.py
========================
Chạy nền, cứ 20 phút thực hiện chu kỳ:
  1. Kill tất cả worker Python (trừ bản thân watchdog)
  2. Đợi 60s cho mọi rate-limit ngắn hạn tự hết
  3. Xóa cooldown đã hết hạn trong key_manager_state.json
  4. Chạy refresh_keys.py (loại key chết, cập nhật .env)
  5. Tìm các mẫu còn thiếu và restart đúng worker gap

Usage:
    python auto_refresh_watchdog.py --member C --output_dir sample_C
"""

import argparse
import json
import os
import subprocess
import sys
import time

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))   # custom_scripts/
LONG_FOLDER = os.path.dirname(SCRIPT_DIR)                  # Long_folder/
BASE_DIR    = os.path.dirname(LONG_FOLDER)                  # project root

REFRESH_SCRIPT = os.path.join(SCRIPT_DIR, "refresh_keys.py")
STATE_FILE     = os.path.join(SCRIPT_DIR, "key_manager_state.json")
LOGS_DIR       = os.path.join(LONG_FOLDER, "logs")

INTERVAL_SECONDS   = 20 * 60   # 20 phút giữa mỗi chu kỳ
KILL_WAIT_SECONDS  = 60        # đợi sau khi kill để rate-limit hết
MAX_GAP_WORKERS    = 12        # số worker tối đa khi restart

# ─── Helpers ──────────────────────────────────────────────────────────────────
def log(msg: str):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [WATCHDOG] {msg}", flush=True)


def kill_workers_except_self() -> int:
    """Kill tất cả python.exe trừ PID của watchdog này."""
    my_pid = os.getpid()
    try:
        cmd = f'taskkill /F /FI "IMAGENAME eq python.exe" /FI "PID ne {my_pid}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        killed = result.stdout.count("SUCCESS")
        return killed
    except Exception as e:
        log(f"Loi kill workers: {e}")
        return 0


def clear_expired_cooldowns() -> int:
    """Xóa cooldown đã hết hạn trong key_manager_state.json."""
    if not os.path.exists(STATE_FILE):
        return 0
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        now = time.time()
        cleared = 0
        for provider, cds in state.get("key_cooldowns", {}).items():
            expired = [k for k, until in cds.items() if until <= now]
            for k in expired:
                del cds[k]
                cleared += 1

        if cleared > 0:
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
            os.rename(tmp, STATE_FILE)
        return cleared
    except Exception as e:
        log(f"Loi xoa cooldown: {e}")
        return 0


def run_refresh() -> bool:
    """Chạy refresh_keys.py, trả True nếu thành công."""
    try:
        result = subprocess.run(
            [sys.executable, REFRESH_SCRIPT],
            cwd=LONG_FOLDER,
            timeout=180,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        # In dòng summary quan trọng
        for line in result.stdout.splitlines():
            upper = line.upper()
            if any(kw in upper for kw in ["TONG CONG", "WORKER", "KEYS SONG", "KEY SONG"]):
                log(f"  >> {line.strip()}")
                break
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log("refresh_keys.py timeout sau 180s!")
        return False
    except Exception as e:
        log(f"Loi chay refresh_keys.py: {e}")
        return False


def find_missing_samples(output_dir: str, total: int = 2000) -> list:
    """Trả danh sách index còn thiếu trong output_dir."""
    done = set()
    if os.path.isdir(output_dir):
        for root, _, files in os.walk(output_dir):
            for fn in files:
                if fn.endswith(".json"):
                    try:
                        done.add(int(os.path.splitext(fn)[0]))
                    except ValueError:
                        pass
    return [i for i in range(1, total + 1) if i not in done]


def group_into_contiguous_ranges(missing: list) -> list:
    """Gộp danh sách index rời rạc thành các khoảng liên tiếp [(start, end), ...]."""
    if not missing:
        return []
    ranges = []
    start = prev = missing[0]
    for n in missing[1:]:
        if n != prev + 1:
            ranges.append((start, prev))
            start = n
        prev = n
    ranges.append((start, prev))
    return ranges


def restart_workers(member: str, output_subdir: str, total_samples: int = 2000):
    """Tìm mẫu còn thiếu và launch worker gap độc lập (DETACHED)."""
    output_dir = os.path.join(BASE_DIR, output_subdir)
    missing = find_missing_samples(output_dir, total_samples)

    if not missing:
        log("Tat ca mau da sinh xong! Khong can restart worker.")
        return 0

    ranges = group_into_contiguous_ranges(missing)
    log(f"Con {len(missing)} mau chua sinh | {len(ranges)} gap range")

    # Giới hạn số worker
    if len(ranges) > MAX_GAP_WORKERS:
        # Merge các range nhỏ liền nhau nếu vượt quá MAX
        ranges = ranges[:MAX_GAP_WORKERS]

    os.makedirs(LOGS_DIR, exist_ok=True)

    launched = 0
    for i, (s, e) in enumerate(ranges, 1):
        log_path = os.path.join(LOGS_DIR, f"worker_gap_{i}.log")
        cmd = (
            f'python -u custom_scripts\\generate_train_data_v3.py '
            f'--member {member} --provider auto '
            f'--start_idx {s} --end_idx {e} '
            f'> "{log_path}" 2>&1'
        )
        # DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP → sống độc lập hoàn toàn
        subprocess.Popen(
            f'cmd /c {cmd}',
            shell=True,
            cwd=LONG_FOLDER,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        log(f"  Launched worker {i} [{s}-{e}] -> worker_gap_{i}.log")
        time.sleep(0.8)
        launched += 1

    return launched


# ─── Main loop ────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Auto-Refresh Watchdog")
    parser.add_argument("--member",     default="C",        help="Member (A/B/C)")
    parser.add_argument("--output_dir", default="sample_C", help="Thu muc output chua mau")
    parser.add_argument("--total",      default=2000, type=int, help="Tong so mau can sinh")
    parser.add_argument("--interval",   default=INTERVAL_SECONDS, type=int, help="Interval (giay)")
    args = parser.parse_args()

    interval = args.interval
    log(f"Khoi dong Auto-Refresh Watchdog")
    log(f"  Member     : {args.member}")
    log(f"  Output dir : {args.output_dir}")
    log(f"  Total mau  : {args.total}")
    log(f"  Interval   : {interval // 60} phut")

    cycle = 0
    while True:
        cycle += 1
        log(f"=== Chu ky #{cycle} bat dau ===")

        # ── 1. Kill workers ───────────────────────────────────────────────────
        killed = kill_workers_except_self()
        if killed:
            log(f"Da kill {killed} worker process.")
        else:
            log("Khong co worker nao dang chay.")

        # ── 2. Đợi 60s cho rate-limit ngắn hạn tự hết ────────────────────────
        log(f"Cho {KILL_WAIT_SECONDS}s de rate-limit ngan han tu het...")
        time.sleep(KILL_WAIT_SECONDS)

        # ── 3. Xóa cooldown hết hạn ───────────────────────────────────────────
        cleared = clear_expired_cooldowns()
        if cleared:
            log(f"Da xoa {cleared} cooldown het han.")
        else:
            log("Khong co cooldown het han trong state file.")

        # ── 4. Refresh keys ───────────────────────────────────────────────────
        log("Chay refresh_keys.py ...")
        ok = run_refresh()
        log("refresh_keys.py hoan thanh." if ok else "refresh_keys.py that bai!")

        # ── 5. Restart workers vào đúng gap ──────────────────────────────────
        n = restart_workers(args.member, args.output_dir, args.total)
        if n:
            log(f"Da khoi dong lai {n} gap workers.")

        # ── 6. Ngủ đến chu kỳ tiếp theo ──────────────────────────────────────
        next_ts = time.strftime("%H:%M:%S", time.localtime(time.time() + interval))
        log(f"Chu ky tiep theo luc: {next_ts}\n")
        time.sleep(interval)


if __name__ == "__main__":
    main()

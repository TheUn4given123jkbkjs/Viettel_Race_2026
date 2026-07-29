import os
import json
import math
from key_manager import key_manager, BASE_DIR, MODELS_REGISTRY_FILE

def calculate_optimal_workers():
    manager = key_manager
    
    # 1. Đếm số tài khoản độc lập có key đang hoạt động
    gemini_accounts = len(manager.keys_by_provider.get("gemini", {}))
    groq_accounts = len(manager.keys_by_provider.get("groq", {}))
    total_accounts = gemini_accounts + groq_accounts
    
    if total_accounts == 0:
        print("⚠️ Không có tài khoản API nào hoạt động. Mặc định chọn 2 workers.")
        return 2

    # 2. Đọc metadata từ models_registry.json
    active_models = []
    if os.path.exists(MODELS_REGISTRY_FILE):
        with open(MODELS_REGISTRY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for provider in ["gemini", "groq"]:
                for m in data.get(provider, []):
                    if m.get("is_active", True) and m.get("isUsed", True) and not m.get("out_of_quota", False):
                        active_models.append(m)

    # Lấy RPM trung bình của các model
    if active_models:
        avg_rpm = sum(m.get("rpm", 15) for m in active_models) / len(active_models)
    else:
        avg_rpm = 15.0

    # Tính toán số Groq keys đang bị đóng băng dài hạn (> 600s) do cạn Quota ngày
    total_groq_keys = sum(len(keys) for keys in manager.keys_by_provider.get("groq", {}).values())
    frozen_groq_keys = 0
    state_file = os.path.join(os.path.dirname(MODELS_REGISTRY_FILE), "key_manager_state.json")
    groq_is_exhausted = False
    
    if os.path.exists(state_file):
        try:
            import time
            now = time.time()
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            key_cooldowns = state.get("key_cooldowns", {}).get("groq", {})
            for key, cd_until in key_cooldowns.items():
                if cd_until - now > 600:
                    frozen_groq_keys += 1
        except Exception:
            pass

    if total_groq_keys > 0 and (frozen_groq_keys / total_groq_keys) >= 0.8:
        groq_is_exhausted = True
        groq_accounts = 0

    # Tính toán dựa trên tài khoản hoạt động thực tế
    # Khi cả 2 provider sống: dùng bottleneck (provider ít TK hơn)
    # Khi Groq chết: dùng Gemini làm nền tính toán
    active_accounts_for_calc = min(gemini_accounts, groq_accounts) if groq_accounts > 0 else gemini_accounts
    target_rpm_per_acc = 2.0  # Mục tiêu 2 req/phút/TK (rất thận trọng so với giới hạn 15 RPM/key)
    max_safe_system_rpm = active_accounts_for_calc * target_rpm_per_acc * 1.5

    if groq_is_exhausted:
        # Groq hết quota TPD — tính lại hoàn toàn dựa trên TK Gemini đang sống thực tế
        # Không dùng hằng số cứng: RPM tối đa = số TK Gemini × target_rpm × safety_factor
        gemini_only_rpm = gemini_accounts * target_rpm_per_acc * 1.5
        max_safe_system_rpm = gemini_only_rpm
        print("  🚨 [TUNER DETECTED] Phát hiện >80% Groq Keys bị đóng băng dài hạn (Hết Quota Token ngày TPD).")
        print(f"  👉 Chế độ Gemini-Only: {gemini_accounts} TK Gemini × {target_rpm_per_acc} RPM × 1.5 = {gemini_only_rpm:.1f} RPM tối đa.")

    # 1 Worker sinh mẫu 600-900 từ mất ~18s -> tốc độ ~3.3 req/phút
    worker_rpm = 3.3
    
    calculated_workers = math.floor(max_safe_system_rpm / worker_rpm)
    
    # Khống chế ngưỡng an toàn tuyệt đối: tối thiểu 2, tối đa 12 Workers (101 keys / 35 TK)
    optimal_workers = max(2, min(12, calculated_workers))
    
    print("\n================================================================================")
    print("📊 PHÂN TÍCH TẢI TỰ ĐỘNG & TÍNH TOÁN WORKER TỐI ƯU (AUTO-WORKER TUNER)")
    print("================================================================================")
    print(f"  ✓ Số tài khoản API độc lập đang SỐNG: {total_accounts} (Gemini: {gemini_accounts} | Groq: {groq_accounts})")
    print(f"  ✓ Số AI Models khả dụng (isUsed=True): {len(active_models)}")
    print(f"  ✓ RPM trung bình mô hình: {avg_rpm:.1f} req/phút")
    print(f"  ✓ Tốc độ an toàn tối đa đề xuất: {max_safe_system_rpm:.1f} req/phút toàn hệ thống")
    print(f"  🏆 SỐ WORKER TỐI ƯU ĐƯỢC CHỌN: {optimal_workers} WORKERS")
    print("================================================================================\n")
    
    return optimal_workers

def generate_worker_ranges(total_samples, num_workers):
    """Chia 2,000 mẫu thành các khoảng [start_idx, end_idx] bằng nhau cho từng worker"""
    chunk_size = math.ceil(total_samples / num_workers)
    ranges = []
    for i in range(num_workers):
        start_idx = i * chunk_size + 1
        end_idx = min((i + 1) * chunk_size, total_samples)
        if start_idx <= total_samples:
            ranges.append((start_idx, end_idx))
    return ranges

def update_batch_files(num_workers):
    """Ghi đè trực tiếp cấu hình số Worker mới vào các file .bat khởi chạy"""
    long_folder = os.path.join(BASE_DIR, "Long_folder")
    total_samples = 2000
    ranges = generate_worker_ranges(total_samples, num_workers)

    # 1. Update run_v3_member_C.bat
    bat_c_path = os.path.join(long_folder, "run_v3_member_C.bat")
    lines_c = [
        '@echo off',
        'cd /d "%~dp0"',
        'echo ==============================================================================',
        'echo  STEP 1: AUTOMATED HEALTH CHECK AND .ENV REFRESH',
        'echo ==============================================================================',
        'python custom_scripts\\refresh_keys.py',
        '',
        'echo.',
        'echo  [INFO] Pausing 5 seconds before launching workers...',
        'timeout /t 5 >nul',
        '',
        'echo.',
        'echo ==============================================================================',
        f'echo  STEP 2: LAUNCHING {num_workers} PARALLEL DATA GENERATOR WORKERS FOR MEMBER C (Q-Z)',
        'echo ==============================================================================',
        ''
    ]
    for idx, (s, e) in enumerate(ranges, 1):
        lines_c.append(f'start "Member C Worker {idx} [{s}-{e}]" cmd /k "python custom_scripts\\generate_train_data_v3.py --member C --provider auto --start_idx {s} --end_idx {e}"')
        lines_c.append('timeout /t 2 >nul\n')
    lines_c.append(f'\necho.\necho  [SUCCESS] {num_workers} CMD workers launched for Member C (Chương Q đến Z)!\npause\n')

    with open(bat_c_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_c))
    print(f"  ✅ Đã cập nhật '{bat_c_path}' -> {num_workers} CMD Workers")

    # 2. Update run_v3_member_A.bat
    bat_a_path = os.path.join(long_folder, "run_v3_member_A.bat")
    lines_a = [
        '@echo off',
        'cd /d "%~dp0"',
        'echo ==============================================================================',
        'echo  STEP 1: AUTOMATED HEALTH CHECK AND .ENV REFRESH',
        'echo ==============================================================================',
        'python custom_scripts\\refresh_keys.py',
        '',
        'echo.',
        'echo  [INFO] Pausing 5 seconds before launching workers...',
        'timeout /t 5 >nul',
        '',
        'echo.',
        'echo ==============================================================================',
        f'echo  STEP 2: LAUNCHING {num_workers} PARALLEL DATA GENERATOR WORKERS FOR MEMBER A (A-H)',
        'echo ==============================================================================',
        ''
    ]
    for idx, (s, e) in enumerate(ranges, 1):
        lines_a.append(f'start "Member A Worker {idx} [{s}-{e}]" cmd /k "python custom_scripts\\generate_train_data_v3.py --member A --provider auto --start_idx {s} --end_idx {e}"')
        lines_a.append('timeout /t 2 >nul\n')
    lines_a.append(f'\necho.\necho  [SUCCESS] {num_workers} CMD workers launched for Member A (Chương A đến H)!\npause\n')

    with open(bat_a_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_a))
    print(f"  ✅ Đã cập nhật '{bat_a_path}' -> {num_workers} CMD Workers")

    # 3. Update run_v3_background.bat (Silent python execution with log redirection and UTF-8 encoding)
    bat_bg_path = os.path.join(long_folder, "run_v3_background.bat")
    lines_bg = [
        '@echo off',
        'cd /d "%~dp0"',
        'set PYTHONIOENCODING=utf-8',
        'echo ==============================================================================',
        'echo  STEP 1: REFRESHING HEALTH CHECK AND KEYS',
        'echo ==============================================================================',
        'python custom_scripts\\refresh_keys.py',
        '',
        'echo.',
        'echo  [INFO] Pausing 5 seconds...',
        'ping -n 6 127.0.0.1 >nul',
        '',
        'echo ==============================================================================',
        f'echo  STEP 2: LAUNCHING {num_workers} SILENT BACKGROUND WORKERS FOR MEMBER C (Q-Z)',
        'echo ==============================================================================',
        'mkdir logs >nul 2>&1',
        ''
    ]
    for idx, (s, e) in enumerate(ranges, 1):
        lines_bg.append(f'start /b python -u custom_scripts\\generate_train_data_v3.py --member C --provider auto --start_idx {s} --end_idx {e} > logs\\worker_{idx}.log 2>&1')
    lines_bg.append(f'\necho.\necho  [SUCCESS] {num_workers} Workers are running SILENTLY in the background!')
    lines_bg.append('echo.')
    lines_bg.append('echo  - To view running python processes : tasklist ^| findstr python')
    lines_bg.append('echo  - To view logs of worker 1         : type logs\\worker_1.log')
    lines_bg.append('echo  - To STOP all background workers   : taskkill /F /IM python.exe')
    lines_bg.append('echo.')
    lines_bg.append('pause\n')

    with open(bat_bg_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_bg))
    print(f"  ✅ Đã cập nhật '{bat_bg_path}' -> {num_workers} Silent Background Workers (with logs)")

if __name__ == "__main__":
    opt_workers = calculate_optimal_workers()
    update_batch_files(opt_workers)

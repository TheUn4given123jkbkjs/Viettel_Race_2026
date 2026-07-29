import os, sys, json, math, argparse, subprocess
from key_manager import key_manager, BASE_DIR, MODELS_REGISTRY_FILE

if sys.stdout.encoding != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass

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

    if active_models:
        avg_rpm = sum(m.get("rpm", 15) for m in active_models) / len(active_models)
    else:
        avg_rpm = 15.0

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

    active_accounts_for_calc = min(gemini_accounts, groq_accounts) if groq_accounts > 0 else gemini_accounts
    target_rpm_per_acc = 2.0
    max_safe_system_rpm = active_accounts_for_calc * target_rpm_per_acc * 1.5

    if groq_is_exhausted:
        gemini_only_rpm = gemini_accounts * target_rpm_per_acc * 1.5
        max_safe_system_rpm = gemini_only_rpm
        print("  🚨 [TUNER DETECTED] Phát hiện >80% Groq Keys bị đóng băng dài hạn (Hết Quota Token ngày TPD).")
        print(f"  👉 Chế độ Gemini-Only: {gemini_accounts} TK Gemini × {target_rpm_per_acc} RPM × 1.5 = {gemini_only_rpm:.1f} RPM tối đa.")

    worker_rpm = 3.3
    calculated_workers = math.floor(max_safe_system_rpm / worker_rpm)
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
    """Chia tổng số mẫu thành các khoảng [start_idx, end_idx] bằng nhau cho từng worker"""
    chunk_size = math.ceil(total_samples / num_workers)
    ranges = []
    for i in range(num_workers):
        start_idx = i * chunk_size + 1
        end_idx = min((i + 1) * chunk_size, total_samples)
        if start_idx <= total_samples:
            ranges.append((start_idx, end_idx))
    return ranges

def launch_dynamic_workers(member, provider, num_samples):
    """Tính toán số worker tối ưu và mở dàn cửa sổ CMD khởi chạy song song"""
    num_workers = calculate_optimal_workers()
    ranges = generate_worker_ranges(num_samples, num_workers)
    long_folder = os.path.join(BASE_DIR, "Long_folder")
    
    print(f"🚀 Đang khởi chạy {num_workers} CMD Workers cho Member [{member}] (Nhà cung cấp: {provider.upper()}, Tổng mẫu: {num_samples})...")
    
    for idx, (s, e) in enumerate(ranges, 1):
        cmd = f'start "[sample_{member}] Worker {idx} [{s}-{e}]" cmd /k "python custom_scripts\\generate_train_data_v3.py --member {member} --provider {provider} --start_idx {s} --end_idx {e}"'
        subprocess.run(cmd, shell=True, cwd=long_folder)

    print(f"\n✅ Đã bật thành công {num_workers} cửa sổ CMD Workers cho thư mục 'sample_{member}'!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto Worker Tuner & Dynamic Launcher")
    parser.add_argument("--member", type=str, default="C", help="Tên thành viên / thư mục đầu ra")
    parser.add_argument("--provider", type=str, default="auto", help="Nhà cung cấp AI")
    parser.add_argument("--num_samples", type=int, default=2000, help="Tổng số mẫu sinh")
    args = parser.parse_args()
    
    launch_dynamic_workers(args.member, args.provider, args.num_samples)

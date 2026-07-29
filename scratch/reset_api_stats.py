"""
Script làm sạch key_stats tích lũy cũ trong key_manager_state.json
và cập nhật lại api_report.md / api_report.json theo dữ liệu mới nhất.
"""
import os, sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUSTOM_SCRIPTS_DIR = os.path.join(BASE_DIR, "Long_folder", "custom_scripts")
if CUSTOM_SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, CUSTOM_SCRIPTS_DIR)

try:
    from key_manager import key_manager
except ImportError:
    sys.path.append(r"d:\AI Race\Viettel_Race_2026\Long_folder\custom_scripts")
    from key_manager import key_manager

def main():
    # Gọi trực tiếp phương thức reset_api_stats tích hợp trong key_manager
    key_manager.reset_api_stats()
    print("✅ Đã reset thành công key_stats (cả bộ nhớ lẫn file state) và xuất báo cáo sạch mới!")

if __name__ == "__main__":
    main()

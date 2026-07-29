"""
Script làm sạch key_stats tích lũy cũ trong key_manager_state.json
và cập nhật lại api_report.md / api_report.json theo dữ liệu mới nhất.
"""
import os, sys

BASE_DIR = r"d:\AI Race\Viettel_Race_2026"
sys.path.append(os.path.join(BASE_DIR, "Long_folder", "custom_scripts"))
from key_manager import key_manager

# Gọi trực tiếp phương thức reset_api_stats tích hợp trong key_manager
key_manager.reset_api_stats()
print("✅ Đã reset thành công key_stats (cả bộ nhớ lẫn file state) và xuất báo cáo sạch mới!")

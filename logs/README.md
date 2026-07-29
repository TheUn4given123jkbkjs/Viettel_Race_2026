# 📋 Nhật ký Thay đổi & Quyết định Dự án (Change Logs Index)

---

### 📌 LOG-20260729-V6.0: Khắc phục lỗi FTS, Smart Mapper & Cân bằng phân bổ V6.0

* **Ngày thực hiện:** `2026-07-29 23:15:00 (UTC+7)`
* **Lý do:** Lỗi FTS5 gây sai lệch ~2,000 nhãn trên 5,995 file cũ, phân bổ bệnh lý bị lệch cục bộ (thiếu bệnh hiếm), và thiếu ràng buộc thuốc lâm sàng hợp lý.
* **Cách khắc phục:** 
  * Phát triển [fix_all_icd_dataset_errors.py](file:///d:/record_by_me/Viettel_race/scratch/fix_all_icd_dataset_errors.py) dọn dẹp triệt để 5,995 file.
  * Xây dựng bộ lọc thông minh [icd10_mapper.py](file:///d:/record_by_me/Viettel_race/scratch/icd10_mapper.py) thay thế FTS.
  * Cấu hình ma trận cân bằng bệnh lý (kèm 10 bệnh hiếm) và ràng buộc lâm sàng thuốc trong [generate_train_data_v4.py](file:///d:/record_by_me/Viettel_race/scratch/generate_train_data_v4.py).
* **Chi tiết Log:** [LOG-20260729-V6.0-BIAS-REDUCTION-AND-MATRIX-BALANCING.md](file:///d:/record_by_me/Viettel_race/logs/LOG-20260729-V6.0-BIAS-REDUCTION-AND-MATRIX-BALANCING.md)

---

### 📌 LOG-20260728-V5.1: Nâng khung trần độ dài Prompt V5.1 (Kéo trung bình >= 436.7 từ gốc)

* **Ngày thực hiện:** `2026-07-28 21:20:00 (UTC+7)`
* **Lý do:** Người dùng muốn độ dài trung bình toàn tập dữ liệu sinh ra phải **vượt mốc >= 436.7 từ** của dữ liệu gốc Turn 2.
* **Cách khắc phục:** 
  * Đã nâng trần ép độ dài trong [generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/generate_train_data_v3.py) lên **600-900 từ** (không ngắn hơn 550 từ).
  * Yêu cầu bổ sung khám chi tiết 5 hệ cơ quan, diễn biến 5-7 ngày trước và chỉ số cận lâm sàng kèm đơn thuốc.
  * Cập nhật đầy đủ báo cáo Markdown Mục 5 trong [diagnose_comparison.ipynb](file:///d:/AI%20Race/Viettel_Race_2026/diagnose_comparison.ipynb).
* **Chi tiết Log:** [LOG-20260728-V5.1-PROMPT-LENGTH-BOOST.md](file:///d:/AI%20Race/Viettel_Race_2026/logs/LOG-20260728-V5.1-PROMPT-LENGTH-BOOST.md)

---


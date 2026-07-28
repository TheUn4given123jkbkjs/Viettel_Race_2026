# 📋 Nhật ký Thay đổi & Quyết định Dự án (Change Logs Index)

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

### 📌 LOG-20260728-V5.0: Nâng cấp Hệ thống Smart Scheduler, Model 70B & Prompt V5.0

* **Ngày thực hiện:** `2026-07-28 19:50:00 (UTC+7)`
* **Lý do:** 74 mẫu đầu tiên của Member C còn thiếu nhãn `isFamily` (0 nhãn), bị lỗi 1 ký tự vị trí do khoảng trắng, dính 429 do nghẽn tài khoản Groq, và lặp kịch bản do `NameError: prompt_scenario`.
* **Cách khắc phục:** 
  * Sửa `process_and_align()` với `text.strip(" \t\n\r,.;")` giúp tỉ lệ khớp vị trí đạt **100% tuyệt đối**.
  * Bổ sung `inject_family` (25% xác suất) sinh 188 nhãn `isFamily`.
  * Xây dựng bộ điều phối **Smart Idle-Account Priority Scheduler (LRU Allocation)** trong [key_manager.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/key_manager.py) chạy 5 Workers tối ưu 0% xung đột.
  * Đặt `llama-3.3-70b-versatile` làm model Groq 70B chính thức trong [models_registry.json](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/models_registry.json).
  * Bổ sung **Multi-Key Fallback Health Check** trong [refresh_keys.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/refresh_keys.py).
* **Chi tiết Log:** [LOG-20260728-V5.0-SYSTEM-AND-PROMPT-UPGRADE.md](file:///d:/AI%20Race/Viettel_Race_2026/logs/LOG-20260728-V5.0-SYSTEM-AND-PROMPT-UPGRADE.md)

---

### 📌 LOG-20260728-PROMPT-V4: Nâng cấp Prompt V4 (Độ dài, Bối cảnh & Cận lâm sàng)

* **Ngày tạo:** `2026-07-28 06:45:00 (UTC+7)`
* **Lý do:** [diagnose_comparison.ipynb](file:///d:/AI%20Race/Viettel_Race_2026/diagnose_comparison.ipynb) phát hiện dữ liệu AI bị ngắn (240 từ vs 436 từ gốc), lặp từ (TTR 1.1%), thiếu nhãn xét nghiệm (6%).
* **Cách khắc phục:** Ép độ dài cứng 450-750 từ, thêm 5 bối cảnh lâm sàng, nâng temp 0.8, bổ sung chỉ số cận lâm sàng (6-10 nhãn/file).
* **File thay đổi:** [scratch/generate_train_data.py](file:///d:/AI%20Race/Viettel_Race_2026/scratch/generate_train_data.py)
* **Chi tiết Log:** [Prompt_V4_Transition_Detail.md](file:///d:/AI%20Race/Viettel_Race_2026/logs/Prompt_V4_Transition_Detail.md)

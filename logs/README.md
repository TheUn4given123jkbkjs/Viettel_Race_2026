# 📋 NHẬT KÝ THAY ĐỔI & QUYẾT ĐỊNH HỆ THỐNG (SYSTEM CHANGE & DECISION LOGS)

> **Dự án:** Viettel AI Race 2026 - Nhận diện Thực thể & Chuẩn hóa Mã Y khoa  
> **Thư mục:** `logs/`  
> **Mục đích:** Lưu trữ toàn bộ Nhật ký Thay đổi (Change Logs) và Nhật ký Quyết định (Decision Logs) của dự án.

---

## 🗂️ DANH SÁCH NHẬT KÝ THAY ĐỔI & QUYẾT ĐỊNH (CHANGE & DECISION LOG REGISTRY)

### 📌 1. LOG-20260728-PROMPT-V4: Nâng cấp Prompt V4 về Độ dài, Bối cảnh & Nhãn Cận lâm sàng

* **ID Nhật ký:** `LOG-20260728-PROMPT-V4`
* **Tên nhật ký:** Nâng cấp Prompt V4 (Khắc phục độ dài văn bản, độ lặp từ vựng và mật độ nhãn cận lâm sàng)
* **Ngày tạo:** `2026-07-28 06:45:00 (UTC+7)`
* **Nguồn gốc phân tích:** [diagnose_comparison.ipynb](file:///d:/AI%20Race/Viettel_Race_2026/diagnose_comparison.ipynb#L315)
* **Lý do / Nguyên nhân thay đổi:**
  1. *Vấn đề Độ dài Văn bản (Text Length Deficit):* Dữ liệu thực tế (`input_turn2_vong1`) đạt trung bình **436.7 từ/file**. Dữ liệu AI trước đó (`sample_A`: 240.8 từ, `sample_Long`: 250.2 từ) bị thiếu ~44% độ dài do LLM tự động tóm tắt ngắn khi xuất định dạng JSON.
  2. *Vấn đề Độ lặp Từ vựng & Cấu trúc (Vocabulary Diversity & Template Fatigue):* Tỷ lệ đa dạng từ vựng Type-Token Ratio (TTR) của AI chỉ đạt **1.01% - 1.15%** (thấp hơn nhiều so với **5.82%** của dữ liệu gốc), cho thấy AI đang bị rập khuôn theo các mẫu câu cố định của prompt.
  3. *Vấn đề Phân bổ Nhãn Xét nghiệm Cận lâm sàng:* Các nhãn `TÊN_XÉT_NGHIỆM` và `KẾT_QUẢ_XÉT_NGHIỆM` chỉ chiếm tỷ lệ mỏng (~6.0% - 6.7%), cần ép mô tả thêm các chỉ số xét nghiệm thực tế (công thức máu, sinh hóa, X-quang, siêu âm, ECG).
* **Giải pháp & Cách khắc phục:**
  1. *Ràng buộc độ dài cứng:* Thêm chỉ thị `STRICT LENGTH REQUIREMENT` bắt buộc trường `text` đạt từ **450 đến 750 từ**, ép mô tả chi tiết diễn tiến bệnh 3-5 ngày và khám từng cơ quan.
  2. *Tăng đa dạng bối cảnh:* Bổ sung mảng `clinical_context` ngẫu nhiên 5 bối cảnh lâm sàng (nội trú, ngoại trú, tóm tắt chuyển viện, tờ điều trị, case report) và nâng `temperature = 0.8`.
  3. *Bổ sung chỉ số xét nghiệm:* Bắt buộc mô tả cụ thể tên và kết quả các xét nghiệm (Công thức máu, Sinh hóa, X-quang, Siêu âm, ECG, CT-Scan) và nâng số lượng trích xuất lên **6 - 10 nhãn/file**.
* **Các file đã thay đổi:**
  * [scratch/generate_train_data.py](file:///d:/AI%20Race/Viettel_Race_2026/scratch/generate_train_data.py#L163)
  * [Long_folder/custom_scripts/generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/generate_train_data_v3.py#L128)
* **Tệp mô tả chi tiết cấu trúc (Tầng 2):** [Prompt_V4_Transition_Detail.md](file:///d:/AI%20Race/Viettel_Race_2026/logs/Prompt_V4_Transition_Detail.md)

---

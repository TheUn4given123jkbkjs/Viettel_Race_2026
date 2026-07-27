# 📋 LOG CHUYỂN ĐỔI CẤU TRÚC PROMPT (PROMPT STRUCTURAL TRANSITION LOG)

---

## 🏛️ TẦNG 1: METADATA & BẢN ĐỒ THAM CHIẾU (TIER 1 - METADATA & REFERENCE MAP)

* **ID Nhật ký:** `LOG-20260728-PROMPT-V4`
* **Thời gian ghi nhận:** `2026-07-28 06:44:00 (UTC+7)`
* **Mức độ ảnh hưởng:** High (Ảnh hưởng trực tiếp đến chất lượng văn bản AI sinh ra)
* **Nguồn gốc phân tích chẩn đoán:** [diagnose_comparison.ipynb](file:///d:/AI%20Race/Viettel_Race_2026/diagnose_comparison.ipynb#L315)
* **Tệp mã nguồn áp dụng chính:**
  * [scratch/generate_train_data.py](file:///d:/AI%20Race/Viettel_Race_2026/scratch/generate_train_data.py#L163)
  * [Long_folder/custom_scripts/generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/generate_train_data_v3.py#L128)
* **Tệp tài liệu tham chiếu kỹ thuật liên quan:**
  * [Long_folder/docs_Long/Prompt_Gap_Analysis.md](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/docs_Long/Prompt_Gap_Analysis.md#L119)
  * [Long_folder/docs_Long/README.md](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/docs_Long/README.md#L71)
* **Tóm tắt tổng quan:** Nhật ký này ghi nhận toàn bộ quá trình nâng cấp cấu trúc Prompt từ V3 lên V4 nhằm xử lý 3 khuyết điểm lớn của dữ liệu AI sinh ra: thiếu độ dài văn bản (chỉ đạt ~240 từ so với 436 từ của dữ liệu gốc), độ đa dạng TTR thấp (1.1%) và mật độ nhãn xét nghiệm cận lâm sàng mỏng (~6%).

---

## 🔬 TẦNG 2: 2. CHI TIẾT CẤU TRÚC CHUYỂN ĐỔI (PROMPT STRUCTURAL TRANSITION DETAILS)

### 2.1 Chuyển đổi Cấu trúc Độ dài Văn bản (Text Length Structure Transition)

* **Cấu trúc cũ (V3):**
  ```python
  length_hint = "ĐỘ DÀI: TRUNG BÌNH (300-500 từ)" if rand_len < 0.40 else "ĐỘ DÀI: DÀI (500-800 từ)"
  ```
  * *Nhược điểm:* Chỉ thị độ dài chung chung khiến LLM khi sinh dưới dạng cấu trúc JSON có xu hướng tóm tắt ngắn (~240 từ).

* **Cấu trúc mới (V4):**
  ```python
  length_hint = """🛑 BẮT BUỘC VỀ ĐỘ DÀI VĂN BẢN (STRICT LENGTH REQUIREMENT):
  - Trường 'text' BẮT BUỘC ĐẠT ĐỘ DÀI TỪ 450 ĐẾN 750 TỪ. 
  - PHẢI viết rất chi tiết: mô tả quá trình diễn biến bệnh lý từ 3-5 ngày trước, liệt kê tiền sử, kết quả khám từng cơ quan (tuần hoàn, hô hấp, tiêu hóa, thần kinh), và đầy đủ các chỉ số xét nghiệm cận lâm sàng kèm đơn thuốc/y lệnh."""
  ```
  * *Cải tiến:* Ép cứng khoảng từ 450 - 750 từ, phân rã yêu cầu viết chi tiết từng mục cụ thể.

---

### 2.2 Chuyển đổi Cấu trúc Bối cảnh & Đa dạng Từ vựng (Context & Diversity Structural Transition)

* **Cấu trúc cũ (V3):** 
  * Chỉ áp dụng 5 `style_id` cố định.
  * Tham số `temperature = 0.7` trên các API provider.

* **Cấu trúc mới (V4):**
  * Bổ sung mảng bối cảnh lâm sàng ngẫu nhiên (`clinical_context`):
    ```python
    contexts = [
        "BỐI CẢNH LÂM SÀNG: Hồ sơ bệnh án điều trị nội trú chi tiết tại Bệnh viện Đa khoa.",
        "BỐI CẢNH LÂM SÀNG: Phiếu khám bệnh ngoại trú và tư vấn y khoa chuyên sâu.",
        "BỐI CẢNH LÂM SÀNG: Tóm tắt hồ sơ bệnh án chuyển viện / Biên bản hội chẩn lâm sàng.",
        "BỐI CẢNH LÂM SÀNG: Tờ điều trị hàng ngày và ghi chú diễn tiến bệnh lý của bác sĩ.",
        "BỐI CẢNH LÂM SÀNG: Báo cáo ca bệnh lâm sàng phức tạp (Complex Case Report)."
    ]
    ```
  * Nâng tham số `temperature` lên **`0.8`** cho toàn bộ các model (Gemini-2.0-flash, Groq Llama-3.3-70B, SambaNova DeepSeek-V3.1, 9router) để giảm hiện tượng lặp lại mẫu câu.

---

### 2.3 Chuyển đổi Cấu trúc Thực thể Cận lâm sàng (Lab Test Entities Structural Transition)

* **Cấu trúc cũ (V3):**
  * Chỉ chỉ thị trích xuất `TÊN_XÉT_NGHIỆM` và `KẾT_QUẢ_XÉT_NGHIỆM` ở kịch bản `scenario_id = 1`.
  * Giới hạn tối đa 5 - 8 nhãn/file.

* **Cấu trúc mới (V4):**
  * Bắt buộc đưa thông tin xét nghiệm cụ thể (*Công thức máu WBC/RBC, Sinh hóa Glucose/Urea/Creatinine/GOT/GPT, X-quang, Siêu âm, ECG, CT-Scan*) vào cả 3 kịch bản `scenario_id` 1, 2 và 3.
  * Nâng số lượng thực thể tối đa trích xuất lên **6 - 10 nhãn/file**.

# 🔬 TẦNG 2: CHI TIẾT CẤU TRÚC CHUYỂN ĐỔI PROMPT V4

* **ID Nhật ký:** `LOG-20260728-PROMPT-V4`
* **Ngày tạo:** `2026-07-28 06:45:00 (UTC+7)`
* **Nguồn gốc phân tích chẩn đoán:** [diagnose_comparison.ipynb](file:///d:/AI%20Race/Viettel_Race_2026/diagnose_comparison.ipynb#L315)
* **File mã nguồn áp dụng:**
  * [scratch/generate_train_data.py](file:///d:/AI%20Race/Viettel_Race_2026/scratch/generate_train_data.py#L163)

---

## 2. CHI TIẾT CẤU TRÚC CHUYỂN ĐỔI (PROMPT STRUCTURAL TRANSITION DETAILS)

### 2.1 Chuyển đổi Cấu trúc Độ dài Văn bản (Text Length Structure Transition)

* **Cấu trúc cũ (V3):**
  ```python
  length_hint = "ĐỘ DÀI: TRUNG BÌNH (300-500 từ)" if rand_len < 0.40 else "ĐỘ DÀI: DÀI (500-800 từ)"
  ```
  * *Nhược điểm:* Chỉ thị chung chung khiến LLM khi sinh dạng JSON bị tóm tắt ngắn (~240 từ).

* **Cấu trúc mới (V4):**
  ```python
  length_hint = """🛑 BẮT BUỘC VỀ ĐỘ DÀI VĂN BẢN (STRICT LENGTH REQUIREMENT):
  - Trường 'text' BẮT BUỘC ĐẠT ĐỘ DÀI TỪ 450 ĐẾN 750 TỪ. 
  - PHẢI viết rất chi tiết: mô tả quá trình diễn biến bệnh lý từ 3-5 ngày trước, liệt kê tiền sử, kết quả khám từng cơ quan (tuần hoàn, hô hấp, tiêu hóa, thần kinh), và đầy đủ các chỉ số xét nghiệm cận lâm sàng kèm đơn thuốc/y lệnh."""
  ```
  * *Cải tiến:* Ép cứng từ 450 - 750 từ, phân rã chi tiết từng phân đoạn.

---

### 2.2 Chuyển đổi Cấu trúc Bối cảnh & Đa dạng Từ vựng (Context & Diversity Structural Transition)

* **Cấu trúc cũ (V3):** Chỉ có 5 `style_id` cố định, `temperature = 0.7`.
* **Cấu trúc mới (V4):** 
  * Bổ sung mảng `clinical_context` ngẫu nhiên 5 bối cảnh lâm sàng:
    ```python
    contexts = [
        "BỐI CẢNH LÂM SÀNG: Hồ sơ bệnh án điều trị nội trú chi tiết tại Bệnh viện Đa khoa.",
        "BỐI CẢNH LÂM SÀNG: Phiếu khám bệnh ngoại trú và tư vấn y khoa chuyên sâu.",
        "BỐI CẢNH LÂM SÀNG: Tóm tắt hồ sơ bệnh án chuyển viện / Biên bản hội chẩn lâm sàng.",
        "BỐI CẢNH LÂM SÀNG: Tờ điều trị hàng ngày và ghi chú diễn tiến bệnh lý của bác sĩ.",
        "BỐI CẢNH LÂM SÀNG: Báo cáo ca bệnh lâm sàng phức tạp (Complex Case Report)."
    ]
    ```
  * Nâng `temperature` lên `0.8` cho tất cả các model (Gemini-2.0-flash, Groq Llama-3.3-70B, SambaNova DeepSeek-V3.1, 9router).

---

### 2.3 Chuyển đổi Cấu trúc Thực thể Cận lâm sàng (Lab Test Entities Structural Transition)

* **Cấu trúc cũ (V3):** Chỉ dặn trích xuất ở `scenario_id = 1`, tối đa 5-8 nhãn/file.
* **Cấu trúc mới (V4):** Bắt buộc đưa thông tin xét nghiệm cụ thể (Công thức máu WBC/RBC, Sinh hóa Glucose/Urea/Creatinine/GOT/GPT, X-quang, Siêu âm, ECG, CT-Scan) vào các scenario 1, 2, 3 và nâng số lượng trích xuất lên **6 - 10 nhãn/file**.

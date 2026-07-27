# 📋 BẢN ĐỒ METADATA & BÁO CÁO NHẬT KÝ VẬN HÀNH (LOGS METADATA MAP)

---

## 🏛️ TẦNG 1: METADATA & NGUYÊN NHÂN BIẾN ĐỘNG (TIER 1 - METADATA & DIAGNOSTIC REASONS)

### 📌 NHẬT KÝ: LOG-20260728-PROMPT-V4

* **ID Nhật ký:** `LOG-20260728-PROMPT-V4`
* **Ngày tạo:** `2026-07-28 06:45:00 (UTC+7)`
* **Nguồn gốc phân tích chẩn đoán:** [diagnose_comparison.ipynb](file:///d:/AI%20Race/Viettel_Race_2026/diagnose_comparison.ipynb#L315)
* **File mã nguồn áp dụng:**
  * [scratch/generate_train_data.py](file:///d:/AI%20Race/Viettel_Race_2026/scratch/generate_train_data.py#L163)
  * [Long_folder/custom_scripts/generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/generate_train_data_v3.py#L128)
* **Tệp mô tả chi tiết Tầng 2:** [Prompt_V4_Transition_Detail.md](file:///d:/AI%20Race/Viettel_Race_2026/logs/Prompt_V4_Transition_Detail.md)

---

### 🔍 1. NGUYÊN NHÂN & LÝ DO ĐIỀU CHỈNH (DIAGNOSTIC REASONS)

1. **Vấn đề Độ dài Văn bản (Text Length Deficit):**
   * *Phân tích từ `diagnose_comparison.ipynb`:* Dữ liệu thực tế (`input_turn2_vong1`) đạt trung bình **436.7 từ/file**. Dữ liệu AI sinh ra trước đó (`sample_A`: 240.8 từ, `sample_Long`: 250.2 từ) bị thiếu ~44% độ dài thực tế do LLM tự động tóm tắt ngắn khi xuất định dạng JSON.

2. **Vấn đề Độ lặp Từ vựng & Cấu trúc (Vocabulary Diversity & Template Fatigue):**
   * *Phân tích từ `diagnose_comparison.ipynb`:* Tỷ lệ đa dạng từ vựng Type-Token Ratio (TTR) của AI chỉ đạt **1.01% - 1.15%** (thấp hơn nhiều so với **5.82%** của dữ liệu gốc), cho thấy AI đang bị rập khuôn theo các mẫu câu cố định của prompt.

3. **Vấn đề Phân bổ Nhãn Xét nghiệm Cận lâm sàng:**
   * Các nhãn `TÊN_XÉT_NGHIỆM` và `KẾT_QUẢ_XÉT_NGHIỆM` chỉ chiếm tỷ lệ mỏng (~6.0% - 6.7%), cần ép mô tả thêm các chỉ số xét nghiệm thực tế (công thức máu, sinh hóa, X-quang, siêu âm, ECG).

---

👉 Xem toàn bộ so sánh mã nguồn chi tiết trước và sau nâng cấp tại Tầng 2: **[Prompt_V4_Transition_Detail.md](file:///d:/AI%20Race/Viettel_Race_2026/logs/Prompt_V4_Transition_Detail.md)**

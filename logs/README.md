# 📋 Nhật ký Thay đổi & Quyết định Dự án (Change Logs Index)

---

### 📌 LOG-20260728-PROMPT-V4: Nâng cấp Prompt V4 (Độ dài, Bối cảnh & Cận lâm sàng)

* **Ngày tạo:** `2026-07-28 06:45:00 (UTC+7)`
* **Lý do:** [diagnose_comparison.ipynb](file:///d:/AI%20Race/Viettel_Race_2026/diagnose_comparison.ipynb#L315) phát hiện dữ liệu AI bị ngắn (240 từ vs 436 từ gốc), lặp từ (TTR 1.1%), thiếu nhãn xét nghiệm (6%).
* **Cách khắc phục:** Ép độ dài cứng 450-750 từ, thêm 5 bối cảnh lâm sàng, nâng temp 0.8, bổ sung chỉ số cận lâm sàng (6-10 nhãn/file).
* **File thay đổi:** [scratch/generate_train_data.py](file:///d:/AI%20Race/Viettel_Race_2026/scratch/generate_train_data.py#L163), [Long_folder/custom_scripts/generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/generate_train_data_v3.py#L128)
* **Chi tiết Tầng 2:** [Prompt_V4_Transition_Detail.md](file:///d:/AI%20Race/Viettel_Race_2026/logs/Prompt_V4_Transition_Detail.md)

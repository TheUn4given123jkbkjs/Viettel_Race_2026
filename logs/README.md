# 📋 Nhật ký Thay đổi & Quyết định Dự án (Change Logs Index)

* 🔗 **[Đường dẫn tải Mô hình (Model Google Drive Links)](file:///d:/AI%20Race/Viettel_Race_2026/logs/MODEL_DRIVE_LINKS.md)**

---

### 📌 LOG-20260801-V6.5: Báo cáo Khắc phục Lỗi Huấn luyện ViDeBERTa-CRF & Tối ưu hóa GPU

* **Ngày thực hiện:** `2026-08-01 16:00:00 (UTC+7)`
* **Lý do:** Khắc phục triệt để lỗi treo tiến trình (OpenMP Deadlock), lỗi Python crash do DLL conflict trên Windows, và lỗi nổ trọng số/NaN loss do underflow số thực float16 khi tải mô hình từ Hub.
* **Cách khắc phục:** 
  * Định cấu hình `torch_dtype=torch.float32` nạp mô hình ở độ chính xác FP32 để ngăn chặn epsilon của AdamW underflow về 0.
  * Hạ học suất Classifier (`1e-4`) và CRF transitions (`2e-4`) để bảo vệ ranh giới rãnh của DeBERTa, bật `max_grad_norm=1.0`.
  * Sắp xếp import datasets trước torch để tránh lỗi DLL, và bỏ giới hạn single-thread để tối ưu hóa CPU-GPU 28x.
* **Chi tiết Log:** [LOG-20260801-V6.5-VIDEBERTA-CRF-STABILITY-FIX.md](file:///d:/record_by_me/Viettel_race/logs/LOG-20260801-V6.5-VIDEBERTA-CRF-STABILITY-FIX.md)

---

### 📌 LOG-20260731-V6.5: Fix Pipeline Paths, Kiểm tra Hybrid Linker & Khởi động Training PhoBERT

* **Ngày thực hiện:** `2026-07-31 22:07:00 (UTC+7)`
* **Lý do:** Toàn bộ 3 file pipeline hard-code `d:/record_by_me/Viettel_race` — đường dẫn sai trên máy hiện tại. Keras 3 conflict cũng khiến `sentence_transformers` và `transformers.Trainer` crash.
* **Cách khắc phục:**
  * Fix path trong `train_phobert.py`, `hybrid_linker.py`, `run_pipeline.py` dùng `Path(__file__).parent`.
  * Fix `evaluation_strategy` → `eval_strategy` (deprecated HuggingFace API).
  * Fix Keras 3 conflict: `except ImportError` → `except (ImportError, ValueError)` cho Layer 3 graceful degradation.
  * Cài `tf-keras` để fix root cause Keras 3 / transformers.Trainer conflict.
  * Xác nhận Hybrid Linker hoạt động: 13,020 ICD-10 + 484 RxNorm terms loaded, Layer 1+2 pass.
  * Khởi động fine-tune `vinai/phobert-base` trên 7,400 mẫu BIO (5 epochs).
* **Chi tiết Log:** [LOG-20260731-V6.5-PIPELINE-PATH-FIX-AND-TRAINING-LAUNCH.md](file:///d:/record_by_me/Viettel_race/logs/LOG-20260731-V6.5-PIPELINE-PATH-FIX-AND-TRAINING-LAUNCH.md)

---

### 📌 LOG-20260730-V6.4: Báo cáo Bàn giao Hợp phần Pipeline & Trạng thái PhoBERT Fine-tune

* **Ngày thực hiện:** `2026-07-30 18:00:00 (UTC+7)`
* **Lý do:** Bàn giao toàn bộ cấu trúc mã nguồn chạy offline, chuẩn bị tập dữ liệu BIO cho PhoBERT và xác định nhiệm vụ chạy train cho nhóm.
* **Cách khắc phục:** 
  * Hoàn thành sinh `train_phobert.jsonl` (7,400 mẫu) và `val_phobert.jsonl` (823 mẫu).
  * Viết và bàn giao `train_phobert.py` cho Thành viên 2 huấn luyện.
  * Bàn giao `hybrid_linker.py`, `ensemble_merger.py`, và `run_pipeline.py` vào thư mục `/pipeline` cho Thành viên 3.
* **Chi tiết Log:** [LOG-20260730-V6.4-PIPELINE-COMPONENTS-DELIVERED.md](file:///d:/record_by_me/Viettel_race/logs/LOG-20260730-V6.4-PIPELINE-COMPONENTS-DELIVERED.md)

---

### 📌 LOG-20260730-V6.3: Thiết lập Pipeline & Kế hoạch Phân chia Công việc Huấn luyện y khoa

* **Ngày thực hiện:** `2026-07-30 17:30:00 (UTC+7)`
* **Lý do:** Thống nhất tập trung triển khai mô hình Giai đoạn 2 (Core Hybrid Pipeline) để tối ưu hóa thời gian và nguồn lực.
* **Cách khắc phục:** 
  * Phân chia 2 thành viên huấn luyện luân phiên LLM với cấu hình checkpoint chi tiết.
  * Phân chia 1 thành viên xây dựng bộ ánh xạ mã 3 tầng Hybrid Linker (Exact -> Fuzzy -> Semantic Search).
* **Chi tiết Log:** [LOG-20260730-V6.3-PIPELINE-SETUP-AND-FINE-TUNING-PLAN.md](file:///d:/record_by_me/Viettel_race/logs/LOG-20260730-V6.3-PIPELINE-SETUP-AND-FINE-TUNING-PLAN.md)

---

### 📌 LOG-20260730-V6.2: Tích hợp Tập dữ liệu bổ sung Sample E & Cập nhật EDA Toàn hệ thống

* **Ngày thực hiện:** `2026-07-30 16:20:00 (UTC+7)`
* **Lý do:** Bổ sung tập dữ liệu phụ trợ `sample_E` gồm 248 file bệnh án để tăng quy mô huấn luyện và mở rộng độ dài văn bản ngữ cảnh.
* **Cách khắc phục:** 
  * Cập nhật các script tạo EDA ([generate_eda_report.py](file:///d:/record_by_me/Viettel_race/scratch/generate_eda_report.py), [generate_eda_html.py](file:///d:/record_by_me/Viettel_race/scratch/generate_eda_html.py)) và script gộp dữ liệu ([merge_datasets.py](file:///d:/record_by_me/Viettel_race/scratch/merge_datasets.py)) để bao gồm `sample_E`.
  * Đồng bộ [diagnose_comparison.ipynb](file:///d:/record_by_me/Viettel_race/diagnose_comparison.ipynb) (Cell 1, 3, 5, 7, 9, 10) để phân tích đầy đủ metrics của `sample_E`.
  * Hợp nhất thành công 8,223 bệnh án ShareGPT vào [train_clean.json](file:///d:/record_by_me/Viettel_race/train_clean.json).
* **Chi tiết Log:** [LOG-20260730-V6.2-INTEGRATING-SAMPLE-E.md](file:///d:/record_by_me/Viettel_race/logs/LOG-20260730-V6.2-INTEGRATING-SAMPLE-E.md)

---

### 📌 LOG-20260730-V6.1: Làm giàu CSDL, Sửa lỗi thiếu Candidates & Đồng bộ Sample D v6.1

* **Ngày thực hiện:** `2026-07-30 14:55:00 (UTC+7)`
* **Lý do:** Phát hiện 1,214 lỗi thiếu mã RxNorm và 218 lỗi thiếu mã ICD-10 trong tập dữ liệu `sample_D` mới sinh do lỗi đè đĩa CSDL (PRIMARY KEY Overwrite) và thiếu hoạt chất mới của V4.
* **Cách khắc phục:** 
  * Nâng cấp Schema CSDL cục bộ (Unique Index thay cho Primary Key) và bổ sung 100+ hoạt chất mới.
  * Tối ưu [icd10_mapper.py](file:///d:/record_by_me/Viettel_race/scratch/icd10_mapper.py) để xử lý chẩn đoán ghép, bóc tách liều dùng thuốc và tiền xử lý dấu ngoặc đơn Down/Hurler/PKU.
  * Sửa lỗi triệt để trên 1,980 file JSON của `sample_D` qua [fix_dataset_candidates.py](file:///d:/record_by_me/Viettel_race/scratch/fix_dataset_candidates.py) và đồng bộ [diagnose_comparison.ipynb](file:///d:/record_by_me/Viettel_race/diagnose_comparison.ipynb).
* **Chi tiết Log:** [LOG-20260730-V6.1-ENRICHED-DATABASE-AND-SAMPLE-D-AUDIT.md](file:///d:/record_by_me/Viettel_race/logs/LOG-20260730-V6.1-ENRICHED-DATABASE-AND-SAMPLE-D-AUDIT.md)

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


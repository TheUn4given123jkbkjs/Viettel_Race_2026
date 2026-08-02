# 📋 Nhật ký Thay đổi & Quyết định Dự án (Change Logs Index)

* 🔗 **[Đường dẫn tải Mô hình (Model Google Drive Links)](file:///d:/record_by_me/Viettel_race/logs/MODEL_DRIVE_LINKS.md)**

---

### 📌 LOG-20260803-V7.8: Phân tích & Khắc phục Điểm thấp (8.81% ➔ 9.73%) của Submission V6 & Giải pháp Ensemble Qwen+PhoBERT
* **Ngày thực hiện:** `2026-08-03 00:45:00 (UTC+7)`
* **Lý do:** Điều tra nguyên nhân điểm số nộp bài V6 trên Kaggle chỉ đạt 8.8140% (sau sửa đổi đạt 9.7334%), phân tích sâu các chỉ số (WER 88.13%, J_assertion 13.31%, J_candidates 5.45%) và triển khai bộ suy luận kết hợp (Ensemble).
* **Cách khắc phục:**
  * Xóa bỏ hoàn toàn logic đè nhãn `check_type_override` vì nó biến đổi các triệu chứng lâm sàng thuộc Chương R (như *khó thở*, *sốt*, *đau ngực*...) thành `CHẨN_ĐOÁN` do chúng nằm trong danh mục ICD-10 ➔ Gây mất điểm kép.
  * Nâng cấp Linker bổ sung Tầng 1.5 Khớp chuỗi con (Substring match) và mở rộng từ điển viết tắt G6PD/THA để sửa lỗi bỏ sót các chẩn đoán ngắn dạng chung.
  * Lập script `repair_submission_v6.py` sửa trực tiếp 78 lỗi đè nhãn triệu chứng và 41 mã ICD-10 trong tệp submission để nộp lại ngay lập tức, nâng điểm lên 9.73%.
  * Viết script suy luận hợp nhất trên Kaggle [run_kaggle_ensemble_inference.py](file:///D:/AI%20Race/Viettel_Race_2026/pipeline/run_kaggle_ensemble_inference.py) nạp đồng thời Qwen (suy luận theo từ) và PhoBERT (NER BIO), giải quyết triệt để vấn đề mất Recall của Qwen đơn lẻ.
* **Chi tiết Log:** [LOG-20260803-V7.8-DIAGNOSED-SUBMISSION-V6-LOW-SCORE-AND-REPAIRED.md](LOG-20260803-V7.8-DIAGNOSED-SUBMISSION-V6-LOW-SCORE-AND-REPAIRED.md)

---

### 📌 LOG-20260802-V7.7: Điều chỉnh Độ dài Phân đoạn (Chunk Size) và Độ gối đầu (Overlap) Cửa sổ Trượt
* **Ngày thực hiện:** `2026-08-02 22:50:00 (UTC+7)`
* **Lý do:** Cải tiến độ phủ ngữ cảnh của thuật toán Cửa sổ trượt (Sliding Window) dựa trên số liệu thống kê độ dài câu thực tế nhằm tăng Recall, tránh mất thực thể ở ranh giới phân đoạn.
* **Cách khắc phục:**
  * Sửa đổi Qwen chunk size lên `256 từ` và overlap lên `60 từ` (tương đương 3 câu) để cải thiện Recall ngữ cảnh.
  * Tăng PhoBERT overlap lên `60 từ` (giữ nguyên chunk size `120 từ` để tránh bị cắt xén do giới hạn 256 tokens).
  * Đồng bộ các script được cập nhật vào `D:\AI Race\script\`.
* **Chi tiết Log:** [LOG-20260802-V7.7-ADJUSTING-SLIDING-WINDOW-CHUNK-SIZES-AND-OVERLAPS.md](file:///D:/AI%20Race/Long_Logs/LOG-20260802-V7.7-ADJUSTING-SLIDING-WINDOW-CHUNK-SIZES-AND-OVERLAPS.md)

---

### 📌 LOG-20260802-V7.6: Sửa lỗi Lệch chuẩn Unicode NFD/NFC & Thuật toán Căn chỉnh Thực thể Mờ (Fuzzy Substring Match)
* **Ngày thực hiện:** `2026-08-02 22:40:00 (UTC+7)`
* **Lý do:** Giải quyết hiện tượng bỏ qua thực thể (Skipped Entities) do lệch định dạng Unicode (NFC/NFD) trong 20% tệp dữ liệu test gốc và sự sai lệch chính tả/tiền tố từ sinh của LLM.
* **Cách khắc phục:**
  * Tích hợp cơ chế chuẩn hóa NFC tự động trong `find_closest_position` và `validate_and_align_positions`.
  * Áp dụng SequenceMatcher để ánh xạ vị trí ký tự động ngược từ NFC về NFD gốc chính xác.
  * Xây dựng bộ quét cửa sổ trượt mờ cục bộ ($\pm 80$ ký tự) lấy phân đoạn có tỷ lệ khớp cao nhất ($\ge 70\%$) và tự động sửa thực thể theo văn bản gốc.
  * Đồng bộ các script được cập nhật vào `D:\AI Race\script\`.
* **Chi tiết Log:** [LOG-20260802-V7.6-FIXING-UNICODE-ALIGNMENT-AND-FUZZY-SUBSTRING-MATCHING.md](LOG-20260802-V7.6-FIXING-UNICODE-ALIGNMENT-AND-FUZZY-SUBSTRING-MATCHING.md)

---

### 📌 LOG-20260802-V7.5: Khắc phục Lỗi Ghi đè Mã ICD-10/RxNorm & Kích hoạt Tìm kiếm Ngữ nghĩa
* **Ngày thực hiện:** `2026-08-02 22:35:00 (UTC+7)`
* **Lý do:** Phân tích nguyên nhân điểm số nộp bài Submission V4 cực thấp (8.4%) và sửa lỗi bỏ qua bộ chuẩn hóa mã `HybridLinker` khi LLM sinh mã ảo giác, đồng thời kích hoạt mặc định Layer 3 (Semantic Search) khi gộp kết quả.
* **Cách khắc phục:**
  * Sửa lỗi trong `run_kaggle_inference.py` để ép buộc `linker.link_entity` ghi đè mã CSDL chuẩn lên trên mã do LLM tự sinh.
  * Sửa đổi `merge_submissions.py` kích hoạt mặc định `use_semantic=True` để giải quyết các trường hợp viết tắt như "G6PD" thông qua tìm kiếm vector.
  * Đồng bộ các script được cập nhật vào `D:\AI Race\script\`.
* **Chi tiết Log:** [LOG-20260802-V7.5-FIXING-CANDIDATES-OVERWRITE-BUG-AND-SEMANTIC-LINKING.md](file:///D:/AI%20Race/Long_Logs/LOG-20260802-V7.5-FIXING-CANDIDATES-OVERWRITE-BUG-AND-SEMANTIC-LINKING.md)

---

### 📌 LOG-20260802-V7.4: Phân tích Xu hướng Hội tụ Epoch 1 & Thiết lập Siêu tham số Tối ưu cho Epoch 2
* **Ngày thực hiện:** `2026-08-02 22:15:00 (UTC+7)`
* **Lý do:** Phân tích đặc tính hội tụ Epoch 1 từ `trainer_state.json` để đưa ra các thiết lập và siêu tham số tối ưu (LR, scheduler, warmup, optimizer) cho huấn luyện tiếp nối (Continued Fine-tuning) Epoch 2.
* **Cách khắc phục:**
  * Viết script `analyze_trainer_state.py` để phân tích độ hội tụ Epoch 1 (Loss giảm 72.85%, grad norm ổn định < 0.40).
  * Điều chỉnh `learning_rate` xuống `5e-5` (tránh quên kiến thức cũ), dùng `cosine` scheduler và `warmup_ratio=0.03`.
  * Đổi bộ tối ưu sang `paged_adamw_8bit` chống tràn VRAM.
  * Cập nhật script `train_epoch2_colab.py` theo cấu hình trên và đồng bộ hóa đường dẫn Drive.
* **Chi tiết Log:** [LOG-20260802-V7.4-ANALYSIS-OF-TRAINING-TRENDS-AND-EPOCH2-HYPERPARAMETERS.md](file:///D:/AI%20Race/Long_Logs/LOG-20260802-V7.4-ANALYSIS-OF-TRAINING-TRENDS-AND-EPOCH2-HYPERPARAMETERS.md)

---

### 📌 LOG-20260802-V7.3: Làm sạch Tập tin Nộp bài V3 (Lọc ký tự đặc biệt) & Nâng cấp Suy luận Qwen lên V4.0 (Sliding Window & Repetition Penalty)
* **Ngày thực hiện:** `2026-08-02 20:45:00 (UTC+7)`
* **Lý do:** Khắc phục lỗi candidates chứa ký tự đặc biệt `*` / `†` kéo tụt điểm J_candidates của lượt nộp V3 xuống 3.54%, và gộp lặp từ để tránh lặp vô hạn. Nâng cấp code chạy Kaggle lên bản V4.0 hỗ trợ sliding window để tăng Recall trên văn bản dài.
* **Cách khắc phục:**
  * Sửa `hybrid_linker.py` để tự động loại bỏ các ký tự đặc biệt `*` và `†` khỏi candidate codes.
  * Cập nhật `merge_submissions.py` để bổ sung cơ chế fallback giữ lại candidates thô (đã làm sạch) của Qwen khi tra cứu DB thất bại.
  * Gộp và nén lại file nộp bài `output_merged_v1.zip` sạch sẽ, giải quyết triệt để vòng lặp lặp từ.
  * Thiết lập và nâng cấp `run_kaggle_inference.py` lên V4.0 tích hợp Sliding Window và repetition penalty 1.15.
  * Sao lưu các scripts quan trọng vào `D:\AI Race\script`.
* **Chi tiết Log:** [LOG-20260802-V7.3-CLEANED-V3-SUBMISSION-AND-UPGRADED-V4-KAGGLE-INFERENCE.md](file:///D:/AI%20Race/Long_Logs/LOG-20260802-V7.3-CLEANED-V3-SUBMISSION-AND-UPGRADED-V4-KAGGLE-INFERENCE.md)

---

### 📌 LOG-20260802-V6.7: Giải quyết Lỗi Chuẩn hóa Unicode NFD/NFC, Cân bằng Word Splitter, Khử Nhiễu Âm Tiết Đơn & Tiền xử lý Dính chữ
* **Ngày thực hiện:** `2026-08-02 19:00:00 (UTC+7)`
* **Lý do:** Khắc phục lỗi vỡ âm tiết do văn bản gốc dạng NFD, lệch word splitter làm dấu câu dính vào thực thể, tràn bộ đếm token gây lỗi CUDA, lọc nhiễu âm tiết đơn lẻ, và xử lý dính chữ lâm sàng (ví dụ "bịchảy").
* **Cách khắc phục:**
  * Thực hiện NFC normalization cấp tài liệu lúc suy luận, sử dụng SequenceMatcher để tạo ánh xạ vị trí ký tự động nhằm khôi phục tọa độ NFD gốc chính xác cho kết quả.
  * Đồng bộ Word Splitter sang `\w+|[^\w\s]` để khớp với lúc huấn luyện.
  * Khống chế token limit theo từ và cắt bớt từ đơn quá dài để bảo vệ GPU.
  * Đặt ngưỡng kích hoạt `0.55` và áp dụng bộ lọc heuristics Whitelist đơn tiết lâm sàng (`ho`, `sốt`, `đau`, `ngứa`, `phù`...) để giữ Recall và sạch Precision.
  * Tiền xử lý tài liệu sửa các lỗi dính chữ phổ biến (`bịchảy` -> `bị chảy`, `đauđầu` -> `đau đầu`).
* **Chi tiết Log:** [LOG-20260802-V6.7-PHOBERT-UNICODE-NFC-ALIGNMENT-AND-NOISE-FILTERING.md](file:///d:/record_by_me/Viettel_race/logs/LOG-20260802-V6.7-PHOBERT-UNICODE-NFC-ALIGNMENT-AND-NOISE-FILTERING.md)

---

### 📌 LOG-20260802-V6.6: Huấn luyện PhoBERT-Softmax & Sửa lỗi Tràn Token để sinh File Nộp bài

* **Ngày thực hiện:** `2026-08-02 18:15:00 (UTC+7)`
* **Lý do:** Hoàn tất huấn luyện mô hình PhoBERT-Softmax không CRF với bộ căn chỉnh subword BIO mới, chạy so sánh đối chiếu với ViDeBERTa-CRF và sửa lỗi tràn token (CUDA out of bounds) gây crash khi chạy thử nghiệm pipeline xử lý 100 văn bản thực tế.
* **Cách khắc phục:**
  * Huấn luyện thành công PhoBERT Softmax đạt F1-Score **`51.05%`** (Precision/Recall lệch chỉ `0.06%`).
  * Thực hiện đánh giá word-level F1: PhoBERT Softmax mới đạt F1 **`51.73%`** (vượt trội +7.16% so với ViDeBERTa-CRF). Sử dụng checkpoint baseline tốt nhất `checkpoint-4630` (F1 `56.08%`) cho pipeline chính thức.
  * Sửa lỗi CUDA assert trong `pipeline/run_pipeline.py` bằng cách đổi tokenizer về `"vinai/phobert-base"` và giảm kích thước cửa sổ trượt thành `max_words=120`, giới hạn độ dài ký tự chunk tối đa `450` ký tự.
  * Thêm các điều kiện kiểm tra an toàn chống giá trị `None` ở các vị trí thực thể.
  * Sinh thành công kết quả trích xuất cho 100 tệp văn bản trong `input_turn2_vong1/output/`.
* **Chi tiết Log:** [LOG-20260802-V6.6-PHOBERT-SOFTMAX-TRAINING-AND-PIPELINE-SUBMISSION.md](file:///d:/record_by_me/Viettel_race/logs/LOG-20260802-V6.6-PHOBERT-SOFTMAX-TRAINING-AND-PIPELINE-SUBMISSION.md)

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

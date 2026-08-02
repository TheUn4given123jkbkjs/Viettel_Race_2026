# 🏆 Viettel AI Race - Medical Entity Extraction & Standardizing System

Hệ thống trích xuất thực thể y khoa (NER), phân tích ngữ cảnh (Assertions) và chuẩn hóa mã định danh bệnh án (ICD-10 & RxNorm Linking) sử dụng kết hợp mô hình ngôn ngữ lớn Qwen 2.5 7B (LoRA) và PhoBERT.

---

## 📂 Bản đồ Thư mục Dự án (Project Directory Map)

Dưới đây là sơ đồ tổ chức các thư mục quan trọng để bạn nhanh chóng tiếp cận:

```
Viettel_Race_2026/
├── 🤖 finetune_qwen_7b/   # Thông tin mô hình LoRA, Drive adapter, kịch bản Colab Epoch 2
├── 🚀 pipeline/            # Quy trình suy luận Ensemble (Qwen + PhoBERT), Linker SQLite, Merger
├── 📓 logs/                # Nhật ký thay đổi (Change Logs), phân tích lỗi điểm số V3/V6
├── 📈 trainer_state.json   # Lưu trữ số liệu loss, learning rate huấn luyện qua các steps
├── 📊 trainer_state_trends # Biểu đồ trực quan hóa tiến độ hội tụ mô hình Epoch 1
├── 📓 diagnose_comparison  # Notebook phân tích, đối sánh định lượng và dữ liệu
├── 🛠️ scratch/             # Tập hợp các kịch bản kiểm tra nhanh, sửa lỗi (auditing) dữ liệu
└── 🗄️ db/                  # Cơ sở dữ liệu SQLite chứa danh mục ICD-10 và RxNorm
```

---

## 📌 Hướng dẫn Điều hướng Nhanh (Navigation Guide)

### 1. 🤖 Huấn luyện Mô hình (Fine-Tuning)
*   **Vào thư mục:** [finetune_qwen_7b/](file:///D:/AI%20Race/Viettel_Race_2026/finetune_qwen_7b/)
*   **Liên kết tải trọng số Epoch 1:** Có sẵn liên kết Google Drive tải tệp `qwen2.5-7b-lora-adapter.zip` trong file README của thư mục này.
*   **Tiếp tục huấn luyện Epoch 2:** Sử dụng kịch bản huấn luyện tiếp nối trên Colab [train_epoch2_colab.py](file:///D:/AI%20Race/script/train_epoch2_colab.py).

### 2. 🚀 Quy trình Suy luận Đầu cuối (End-to-End Inference)
*   **Vào thư mục:** [pipeline/](file:///D:/AI%20Race/Viettel_Race_2026/pipeline/)
*   **Chạy nộp bài chính thức (Ensemble Qwen + PhoBERT):** Sử dụng tệp [run_ensemble_inference.py](file:///D:/AI%20Race/Viettel_Race_2026/pipeline/run_ensemble_inference.py) để gộp kết quả theo IoU, giúp cải thiện tối đa độ phủ (Recall) và ranh giới từ chính xác (Precision).
*   **Chạy mô hình Qwen đơn lẻ:** Sử dụng tệp [run_qwen_inference.py](file:///D:/AI%20Race/Viettel_Race_2026/pipeline/run_qwen_inference.py).

### 3. 📓 Nhật ký Thay đổi & Sửa lỗi (Change Logs & Issues)
*   **Vào thư mục:** [logs/](file:///D:/AI%20Race/Viettel_Race_2026/logs/)
*   **Xem chỉ mục tổng quan:** [logs/README.md](file:///D:/AI%20Race/Viettel_Race_2026/logs/README.md) chứa toàn bộ lộ trình cải tiến thuật toán từ V5.1 đến V7.8.
*   **Xem báo cáo phân tích điểm thấp V6 (9.73%):** Chi tiết tại [LOG-20260803-V7.8-DIAGNOSED-SUBMISSION-V6-LOW-SCORE-AND-REPAIRED.md](file:///D:/AI%20Race/Viettel_Race_2026/logs/LOG-20260803-V7.8-DIAGNOSED-SUBMISSION-V6-LOW-SCORE-AND-REPAIRED.md) để hiểu nguyên lý WER, Jaccard và lý do tại sao PhoBERT là bắt buộc.

### 4. 📉 Theo dõi Tiến trình Hội tụ (Trainer State)
*   **Tệp số liệu thô:** [trainer_state.json](file:///D:/AI%20Race/Viettel_Race_2026/trainer_state.json) chứa các metric loss huấn luyện, grad norm qua từng epoch/step.
*   **Biểu đồ trực quan:** [trainer_state_trends.png](file:///D:/AI%20Race/Viettel_Race_2026/trainer_state_trends.png) giúp đánh giá độ dốc hội tụ (Loss giảm ~72.85% ở Epoch 1).
*   **Kịch bản phân tích:** Sử dụng tiện ích phân tích số liệu tại [scratch/analyze_trainer_state.py](file:///D:/AI%20Race/script/analyze_trainer_state.py) (nếu cần).

### 5. 🔍 Phân tích Đối sánh & Kiểm tra Dữ liệu (Auditing)
*   **Bảng phân tích định lượng:** Mở notebook [diagnose_comparison.ipynb](file:///D:/AI%20Race/Viettel_Race_2026/diagnose_comparison.ipynb) để đối sánh phân phối nhãn và độ dài prompt y khoa.
*   **Các kịch bản kiểm tra (scratch):** Vào thư mục [scratch/](file:///D:/AI%20Race/Viettel_Race_2026/scratch/) chứa các file tiện ích dùng để phát hiện lỗi đè nhãn, chuẩn hóa tọa độ lệch, hoặc lọc ký tự nhiễu.
*   **Cơ sở dữ liệu y khoa chuẩn:** Được nạp sẵn trong tệp SQLite [db/medical_codes.db](file:///D:/AI%20Race/Viettel_Race_2026/db/).

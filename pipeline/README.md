# 🚀 Hướng dẫn các File trong Thư mục Pipeline

Thư mục này chứa các mã nguồn chạy suy luận (Inference), chuẩn hóa mã bệnh (Linker), và gộp mô hình (Ensemble).

---

## 📌 1. Chạy trên Môi trường Cloud (Colab, Kaggle, Runtimes)

### 🌟 [run_ensemble_inference.py](file:///D:/AI%20Race/Viettel_Race_2026/pipeline/run_ensemble_inference.py)
* **Vai trò:** Script chạy chính thức để tạo file nộp bài (đạt điểm cao nhất).
* **Mô tả:** Chạy kết hợp cả **Qwen 2.5** (lấy ngữ cảnh & nhãn phụ) và **PhoBERT** (lấy ranh giới từ chính xác). Tự động quét tìm đường dẫn dữ liệu/mô hình và đóng gói tệp `submission.zip`.

### 🏎️ [run_qwen_inference.py](file:///D:/AI%20Race/Viettel_Race_2026/pipeline/run_qwen_inference.py)
* **Vai trò:** Script chạy đơn lẻ mô hình Qwen.
* **Mô tả:** Chỉ chạy Qwen 2.5, không kết hợp PhoBERT (cho điểm thấp hơn bản Ensemble).

---

## 📌 2. Các mô-đun xử lý cốt lõi (Core Modules)

### 🔗 [hybrid_linker.py](file:///D:/AI%20Race/Viettel_Race_2026/pipeline/hybrid_linker.py)
* **Vai trò:** Ánh xạ từ ngữ lâm sàng sang mã bệnh/thuốc chuẩn (ICD-10 & RxNorm).
* **Mô tả:** Khớp chính xác tên bệnh/thuốc, xử lý các từ viết tắt phổ biến (như `tha`, `g6pd`), khớp chuỗi con, khớp mờ và tìm kiếm ngữ nghĩa bằng Vector.

### 🔀 [ensemble_merger.py](file:///D:/AI%20Race/Viettel_Race_2026/pipeline/ensemble_merger.py)
* **Vai trò:** Thuật toán gộp kết quả dự đoán của Qwen và PhoBERT.
* **Mô tả:** So sánh vị trí thực thể bằng chỉ số trùng khớp IoU. Giữ ranh giới chuẩn từ PhoBERT và các thuộc tính ngữ cảnh (như phủ định, lịch sử bệnh) từ Qwen.

### 🤖 [phobert_predictor.py](file:///D:/AI%20Race/Viettel_Race_2026/pipeline/phobert_predictor.py)
* **Vai trò:** Chạy dự đoán cho mô hình PhoBERT NER.
* **Mô tả:** Tiền xử lý văn bản (sửa lỗi dính chữ, chuẩn hóa Unicode NFC/NFD) và lọc bỏ các từ đơn âm tiết bị nhận diện sai.

---

## 📌 3. Chạy thử nghiệm cục bộ (Offline / Local)

### ⚙️ [run_pipeline.py](file:///D:/AI%20Race/Viettel_Race_2026/pipeline/run_pipeline.py)
* **Vai trò:** Bộ điều phối quy trình đầu cuối (End-to-End) chạy dưới máy Local.

### 🧪 [merge_submissions.py](file:///D:/AI%20Race/Viettel_Race_2026/pipeline/merge_submissions.py)
* **Vai trò:** Gộp các file kết quả dự đoán thô đã xuất sẵn từ Qwen và PhoBERT ở máy Local.

### 📝 [run_submission.py](file:///D:/AI%20Race/Viettel_Race_2026/pipeline/run_submission.py)
* **Vai trò:** Script chạy nhanh mô hình PhoBERT offline trên 100 tệp test.

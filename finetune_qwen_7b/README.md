# 🤖 Huấn luyện Qwen 2.5 7B & Kết quả Dự đoán (Qwen 2.5 7B Fine-Tuning & Submissions)

Thư mục này lưu trữ các kết quả dự đoán (Submissions) của mô hình **Qwen 2.5 7B** đã qua huấn luyện LoRA (Epoch 1) và thông tin liên kết tải trọng số mô hình.

---

## 🔗 Liên kết Tải Trọng số Mô hình (Epoch 1)
*   **Đường dẫn Google Drive:** [Tải LoRA Adapter Epoch 1 tại đây](https://drive.google.com/file/d/13dkzlaNrwoDYB9lYjn_w9tAeXOTDPkHM/view?usp=sharing)
*   **Hướng dẫn nhanh:** Tải tệp `qwen2.5-7b-lora-adapter.zip` từ liên kết trên về, giải nén và nạp đường dẫn thư mục vào Unsloth hoặc LLaMA-Factory để tiếp tục huấn luyện tiếp Epoch 2.

---

## ⚙️ Kịch bản Huấn luyện Tiếp nối (Continued Fine-tuning - Epoch 2)
Để huấn luyện tiếp Epoch 2 từ checkpoint Epoch 1 trên Google Colab, bạn sử dụng kịch bản:
*   **Đường dẫn kịch bản:** [train_epoch2_colab.py](file:///D:/AI%20Race/script/train_epoch2_colab.py)
*   **Mô tả:** Tự động cài đặt thư viện Unsloth tối ưu cho Colab, nạp adapter Epoch 1 từ Google Drive, xử lý tệp dữ liệu y khoa sạch `train_clean.json`, và thực hiện huấn luyện tiếp nối (Continued Fine-tuning) với các siêu tham số tối ưu (như học suất hạ xuống `5e-5` dùng `cosine` scheduler để tránh quên kiến thức cũ).

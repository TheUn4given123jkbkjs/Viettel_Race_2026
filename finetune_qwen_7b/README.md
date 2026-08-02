# 🤖 Huấn luyện Qwen 2.5 7B & Kết quả Dự đoán (Qwen 2.5 7B Fine-Tuning & Submissions)

Thư mục này lưu trữ các kết quả dự đoán (Submissions) của mô hình **Qwen 2.5 7B** đã qua huấn luyện LoRA (Epoch 1) và thông tin liên kết tải trọng số mô hình.

---

## 🔗 Liên kết Tải Trọng số Mô hình (Epoch 1)
*   **Đường dẫn Google Drive:** [Tải LoRA Adapter Epoch 1 tại đây](https://drive.google.com/file/d/13dkzlaNrwoDYB9lYjn_w9tAeXOTDPkHM/view?usp=sharing)
*   **Hướng dẫn nhanh:** Tải tệp `qwen2.5-7b-lora-adapter.zip` từ liên kết trên về, giải nén và nạp đường dẫn thư mục vào Unsloth hoặc LLaMA-Factory để tiếp tục huấn luyện tiếp Epoch 2.

---

## 📂 Danh sách Kết quả Dự đoán (Submissions)
Thư mục này chứa kết quả dự đoán dạng JSON của 100 tệp thử nghiệm y khoa qua các lần chạy:

1.  **[submission/](file:///d:/AI%20Race/Viettel_Race_2026/finetune_qwen_7b/submission) (Lần test thử 1 - Submission V2):** 
    *   Sử dụng cấu hình suy luận và hậu xử lý ban đầu.
2.  **[submissionv3/](file:///d:/AI%20Race/Viettel_Race_2026/finetune_qwen_7b/submissionv3) (Lần test thử 2 - Submission V3):** 
    *   Huấn luyện LoRA 1 epoch kết hợp bộ căn chỉnh nhãn y khoa (HybridLinker).

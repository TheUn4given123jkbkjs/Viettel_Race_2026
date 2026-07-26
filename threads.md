# Luồng Công việc & Phân chia Tiến trình (threads.md)

Tài liệu này chia dự án thành **4 Luồng Công việc (Workstreams / Threads)** chạy độc lập, song song và chỉ hội tụ tại các **Điểm đồng bộ (Sync Points)** cố định.

---

## 1. Bản đồ các Luồng Công việc & Điểm Đồng bộ

```text
LUỒNG 1: CƠ SỞ DỮ LIỆU & RAG
[P1: Thu thập DB] ───────────────────────────► [P7: Xây dựng RAG FAISS] ──┐
                                                                          │
LUỒNG 2: SINH DỮ LIỆU HUẤN LUYỆN                                           │ (Sync Point 3)
[P2: Viết Script Sinh] ──► [P3: Sinh dữ liệu 3 TV] ──► [P4: Gộp/Lọc] ─┐   │   ┌──► [P8: Viết Pipeline] ──► [P9: Test] ──► [P10: Nộp]
                                                                      │   │   │
LUỒNG 3: HUẤN LUYỆN MÔ HÌNH (FINE-TUNE)                               │   │   │
[P5: Viết Script Fine-tune] ──────────────────────────────────────────┴► [P6: Train Colab]
```

### Các Điểm Đồng bộ (Sync Points):
*   **Sync Point 1 (Trước P3):** Bắt buộc phải có tệp CSDL `medical_codes.db` (từ P1) mới có thể chạy script sinh dữ liệu y khoa ở P3.
*   **Sync Point 2 (Trước P6):** Bắt buộc có tệp dữ liệu sạch `train_clean.json` (từ P4) và script `fine_tune_unsloth.ipynb` (từ P5) mới có thể bắt đầu huấn luyện trên Colab.
*   **Sync Point 3 (Trước P8):** Bắt buộc có trọng số mô hình đã huấn luyện (từ P6) và bộ chỉ mục RAG offline (từ P7) mới có thể tích hợp thành pipeline suy luận `run_pipeline.py`.

---

## 2. Chi tiết 4 Luồng Công việc (Threads)

### LUỒNG 1: Cơ sở Dữ liệu & RAG (Thread 1)
*   **Tiến trình P1: Thu thập Master DB**
    *   *Người thực hiện:* **Thành viên A** (tải ICD-10 Bộ Y tế), **Thành viên B & C** (tập hợp thuốc biệt dược/hoạt chất).
    *   *Input:* Danh mục gốc.
    *   *Output:* Tệp SQLite `medical_codes.db`.
*   **Tiến trình P7: Xây dựng RAG & Cache offline**
    *   *Người thực hiện:* **AI**.
    *   *Input:* Tệp `medical_codes.db` (P1).
    *   *Output:* Tệp chỉ mục vector `faiss_index.bin` và tệp Cache ánh xạ nhanh.

### LUỒNG 2: Sinh Dữ liệu Huấn luyện (Thread 2)
*   **Tiến trình P2: Viết Script sinh dữ liệu Train**
    *   *Người thực hiện:* **AI**.
    *   *Input:* Cấu trúc yêu cầu đề bài.
    *   *Output:* Tệp script `generate_train_data.py`.
*   **Tiến trình P3: Chạy sinh dữ liệu Train song song**
    *   *Người thực hiện:* 3 thành viên chạy song song theo chuyên khoa:
        *   **Thành viên A:** Tim mạch, Hô hấp và Cấp cứu.
        *   **Thành viên B:** Tiêu hóa, Nội tiết và Thận - Tiết niệu.
        *   **Thành viên C:** Nhi khoa, Phụ sản và Bệnh truyền nhiễm.
    *   *Input:* Script `generate_train_data.py` (P2) + API Key cá nhân.
    *   *Output:* 3 tệp JSON dữ liệu thô.
*   **Tiến trình P4: Gộp & Làm sạch dữ liệu Train**
    *   *Người thực hiện:* Cả nhóm (phối hợp với AI).
    *   *Input:* 3 tệp JSON thô từ P3.
    *   *Output:* Tệp hợp nhất `train_clean.json`.

### LUỒNG 3: Huấn luyện Mô hình (Thread 3)
*   **Tiến trình P5: Viết Script Fine-tuning Unsloth**
    *   *Người thực hiện:* **AI**.
    *   *Input:* Định dạng `train_clean.json`.
    *   *Output:* Tệp Jupyter Notebook `fine_tune_unsloth.ipynb` (lưu checkpoint lên Drive).
*   **Tiến trình P6: Huấn luyện mô hình tuần tự trên Colab**
    *   *Người thực hiện:* 3 thành viên thay ca chạy tiếp sức nối tiếp checkpoint trên Drive chung:
        *   **Thành viên A** (Ca 1) $\rightarrow$ **Thành viên B** (Ca 2) $\rightarrow$ **Thành viên C** (Ca 3).
    *   *Input:* Notebook `fine_tune_unsloth.ipynb` (P5) + `train_clean.json` (P4).
    *   *Output:* Thư mục trọng số mô hình đã huấn luyện (LoRA Weights) trên Google Drive.

### LUỒNG 4: Suy luận & Đóng gói (Thread 4)
*   **Tiến trình P8: Viết Pipeline Xử lý Inference đầu ra**
    *   *Người thực hiện:* **AI**.
    *   *Input:* Trọng số mô hình (P6) + Chỉ mục RAG offline và Cache (P7).
    *   *Output:* Script chạy hoàn toàn offline `run_pipeline.py`.
*   **Tiến trình P9: Chạy Inference trên 100 tệp test & Xác minh**
    *   *Người thực hiện:* **AI** chạy tự động, **Cả nhóm** kiểm tra thủ công ngẫu nhiên 5-10% kết quả để kiểm chứng độ chính xác.
    *   *Input:* 100 file `.txt` test + `run_pipeline.py`.
    *   *Output:* 100 file `.json` kết quả.
*   **Tiến trình P10: Đóng gói tệp ZIP nộp bài**
    *   *Người thực hiện:* **Thành viên A** (Trưởng nhóm).
    *   *Input:* 100 file `.json` kết quả (P9).
    *   *Output:* Tệp nén thành phẩm `submission.zip` để nộp.

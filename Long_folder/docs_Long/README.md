# 🗺️ BẢN ĐỒ TÀI LIỆU & LUỒNG ĐỌC HƯỚNG DẪN (DOCUMENTATION ROADMAP & INDEX)

> **Dự án:** Viettel AI Race 2026 - Nhận diện Thực thể & Chuẩn hóa Mã Y khoa  
> **Áp dụng chuẩn thiết kế:** Diátaxis Navigation System  
> **Vai trò:** Trạm điều hướng trung tâm (Single Entry Point) cho Lập trình viên & AI Agent  

---

> [!IMPORTANT]
> **HƯỚNG DẪN CHO AI AGENT & DEVELOPER MỚI:**  
> Chào mừng bạn tham gia dự án! Trước khi thực hiện bất kỳ hành động nghiên cứu, viết code, sửa file hay cấu hình nào, bạn **BẮT BUỘC phải đọc tài liệu này trước tiên**. Đây là bản đồ chỉ đường giúp bạn nắm bắt toàn bộ kiến trúc và các tệp tham chiếu mà không làm xáo trộn cấu trúc dự án.

---

## 🚦 LUỒNG ĐỌC TÀI LIỆU (READING FLOW)

Để nhanh chóng nắm bắt dự án một cách khoa học, hãy đọc các tài liệu theo đúng 4 bước dưới đây:

```mermaid
flowchart TD
    Start([Bắt đầu tại docs_Long/README.md]) --> STEP1["Bước 1: Tổng quan Kiến trúc\n(docs_Long/System_Architecture_And_Workflow_Guide.md Tầng 1 & 2)"]
    STEP1 --> STEP2["Bước 2: Phân tích Dữ liệu & Prompt\n(docs_Long/Prompt_Gap_Analysis.md)"]
    STEP2 --> STEP3["Bước 3: Hướng dẫn Vận hành\n(docs_Long/System_Architecture_And_Workflow_Guide.md Tầng 3)"]
    STEP3 --> STEP4["Bước 4: Tra cứu Nhật ký Sự cố\n(docs_Long/Incident_Database_And_Postmortems.md)"]
    STEP4 --> End([Sẵn sàng phát triển & chạy code!])
```

---

## 🗂️ HỆ THỐNG PHÂN TẦNG TÀI LIỆU (DOCUMENTATION HIERARCHY)

Dự án tổ chức tài liệu theo 4 tệp tin cốt lõi, có tính liên kết và tham chiếu chéo lẫn nhau:

### 1. [Bản đồ tài liệu trung tâm (docs_Long/README.md)](file:///d:/AI%20Race/Viettel_Race_2026/docs_Long/README.md)
* **Nội dung:** Giới thiệu tổng quan hệ thống tài liệu, sơ đồ luồng đọc và bản đồ liên kết các tệp.
* **Mục đích:** Giúp lập trình viên/AI Agent định vị nhanh vị trí tài liệu cần đọc mà không phải tìm kiếm thủ công.

### 2. [Kiến trúc hệ thống & Vận hành (docs_Long/System_Architecture_And_Workflow_Guide.md)](file:///d:/AI%20Race/Viettel_Race_2026/docs_Long/System_Architecture_And_Workflow_Guide.md)
* **Nội dung:** 
  * **Tầng 1 (Quyết định):** Các Quyết định Kiến trúc (ADRs) về Xoay vòng Key, Chia Folder dữ liệu, Lớp phòng vệ API.
  * **Tầng 2 (Triển khai):** Sơ đồ luồng dữ liệu Mermaid chi tiết và danh mục tệp tin chức năng.
  * **Tầng 3 (Vận hành):** Hướng dẫn chạy 3 luồng Sweet Spot (`run_v3_3workers.bat`) và cách thêm API Key mới.
* **Mục đích:** Tài liệu kỹ thuật chính phục vụ vận hành và bảo trì code.

### 3. [Phân tích đánh giá Prompt (docs_Long/Prompt_Gap_Analysis.md)](file:///d:/AI%20Race/Viettel_Race_2026/docs_Long/Prompt_Gap_Analysis.md)
* **Nội dung:** Báo cáo đánh giá khoảng cách giữa dữ liệu thực tế lâm sàng Việt Nam và Prompt sinh dữ liệu y khoa của LLM.
* **Mục đích:** Cải tiến prompt để đảm bảo chất lượng tập dữ liệu sinh ra đạt độ phủ cao nhất và sát với đề thi thực tế.

### 4. [Cơ sở dữ liệu Nhật ký Sự cố (docs_Long/Incident_Database_And_Postmortems.md)](file:///d:/AI%20Race/Viettel_Race_2026/docs_Long/Incident_Database_And_Postmortems.md)
* **Nội dung:** Postmortem chi tiết của từng lỗi kỹ thuật phát sinh (`NameError`, `Rate Limit 429`, `AttributeError`...), phân tích nguyên nhân gốc rễ (RCA) và mã nguồn đã khắc phục để phòng ngừa.
* **Mục đích:** Tra cứu nhanh khi gặp lỗi hệ thống hoặc khi muốn mở rộng nâng cấp mã nguồn.

### 5. [Nguyên tắc tổ chức tài liệu (docs_Long/Documentation_Principles.md)](file:///d:/AI%20Race/Viettel_Race_2026/docs_Long/Documentation_Principles.md)
* **Nội dung:** Định nghĩa các nguyên lý Diátaxis, cấu trúc phân lớp tài liệu, quy định về hyperlinking tuyệt đối `file:///` và nguyên tắc bảo vệ tài nguyên an toàn.
* **Mục đích:** Quy chuẩn hóa cách viết tài liệu của các AI Agent và cộng tác viên để duy trì hệ thống thông tin đồng bộ.

---

## 🛠️ BẢN ĐỒ THAM CHIẾU FILE CODE CHÍNH (CODE REFERENCE MAP)

Dưới đây là các file mã nguồn cốt lõi trong thư mục [custom_scripts/](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/) mà bạn có thể cần tra cứu khi vận hành hoặc chỉnh sửa:

* **Trình quản lý Key:** [custom_scripts/key_manager.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/key_manager.py) — Điều phối xoay vòng Key theo tài khoản (Round-Robin), thực hiện Đóng băng Cấp tài khoản và Khóa giãn trễ Pacing Lock.
* **Script sinh dữ liệu:** [custom_scripts/generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/generate_train_data_v3.py) — Script sinh tập tin y khoa chính, chứa logic Fallback 2 cấp Groq và bóc tách Regex JSON siêu bền bỉ.
* **Tool quét Key:** [custom_scripts/refresh_keys.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/refresh_keys.py) — Quét song song sức khỏe API Key và cập nhật đè file `.env`.
* **Tool thêm Key nhanh:** [custom_scripts/add_keys.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/add_keys.py) — Thêm Key mới vào kho dữ liệu master.
* **Kho lưu trữ Key gốc:** [custom_scripts/master_keys.json](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/master_keys.json) — CSDL chứa toàn bộ các API Key y khoa.
* **Script phân chia Folder:** [custom_scripts/reorganize_samples.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/reorganize_samples.py) — Dọn dẹp phân vùng 500 file/folder.

---

## 📝 NHẬT KÝ CẬP NHẬT HỆ THỐNG (SYSTEM CHANGE LOG)

| Phiên bản | Ngày cập nhật | Thành phần nâng cấp | Nội dung thay đổi chi tiết |
| :---: | :---: | :--- | :--- |
| **v4.0** | 2026-07-28 | `generate_train_data_v3.py`<br>`scratch/generate_train_data.py`<br>`diagnose_comparison.ipynb` | 1. **Khắc phục độ dài văn bản:** Bắt buộc trường `text` sinh ra đạt **450 - 750 từ** (tiệm cận độ dài gốc 436 từ của Turn 2).<br>2. **Tăng đa dạng bối cảnh:** Thêm 5 thuộc tính `clinical_context` ngẫu nhiên và nâng `temperature: 0.8`.<br>3. **Cân bằng nhãn xét nghiệm:** Bắt buộc mô tả cụ thể các xét nghiệm cận lâm sàng (`TÊN_XÉT_NGHIỆM`, `KẾT_QUẢ_XÉT_NGHIỆM`) và tăng tối đa 6-10 nhãn/file.<br>4. **Bổ sung Notebook Chẩn đoán:** Thêm Mục 5 đánh giá định lượng & chẩn đoán dữ liệu vào [diagnose_comparison.ipynb](file:///d:/AI%20Race/Viettel_Race_2026/diagnose_comparison.ipynb). |
| **v3.0** | 2026-07-28 | `key_manager.py`<br>`generate_train_data_v3.py` | Tích hợp cơ chế xoay vòng Key theo tài khoản (Account-Level Rotation), Pacing Lock 3.0s, Đóng băng Account khi dính 429. |


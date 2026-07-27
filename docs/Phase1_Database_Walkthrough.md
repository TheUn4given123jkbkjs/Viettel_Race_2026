# Nhật ký Xây dựng CSDL Offline (Phase 1 Walkthrough)

Tài liệu này lưu trữ kiến thức về cách thức xây dựng cơ sở dữ liệu y khoa cục bộ `medical_codes.db` phục vụ tra cứu mã bệnh (ICD-10) và mã thuốc (RxNorm) ngoại tuyến.

---

## 1. Chuẩn hóa & Ánh xạ Danh mục Thuốc

### Thách thức ban đầu:
Danh mục thuốc do Bộ Y tế Việt Nam ban hành trong Thông tư chứa tên tiếng Việt kèm hàm lượng và đường dùng dạng tự do (Ví dụ: *"Dung dịch tiêm ampicilin 500mg"*). Quy chuẩn cuộc thi yêu cầu mã hóa sang hệ thống **RxNorm** của Hoa Kỳ (RxCUI).

### Giải pháp:
1.  **Dịch thuật và Chuẩn hóa:** Dịch toàn bộ danh mục thuốc trong tệp `pill.txt` thành các hoạt chất tiếng Anh lâm sàng chuẩn (Ví dụ: *"ampicilin"* -> `"Ampicillin"`). Lược bỏ các hàm lượng và đường dùng dư thừa để đưa về dạng generic.
2.  **Ánh xạ tự động (API NIH):** Viết script `scratch/map_rxnorm.py` gọi API của NIH RxNav để tự động hóa việc tra cứu. 
    *   **Tỷ lệ thành công:** Ánh xạ thành công **347/348 hoạt chất duy nhất (99.7%)**.
    *   **Tệp đầu ra:** Lưu tại `db/rxnorm_mapped.json` và `db/rxnorm_mapped.csv`.

---

## 2. Xây dựng CSDL SQLite & Lập chỉ mục FTS5

Để phục vụ tìm kiếm thời gian thực dưới 1ms trong quá trình suy luận và sinh dữ liệu, toàn bộ dữ liệu được nạp vào SQLite:

### Bảng `icd10` (Bệnh học):
*   Nguồn dữ liệu: Tệp Excel `.xlsx` chính thức của Bộ Y tế chứa 36,689 dòng.
*   Deduplication (Khử trùng lặp): Do một số mã xuất hiện ở nhiều chuyên khoa khác nhau, SQLite đặt cột `code` làm `PRIMARY KEY` để giữ lại **13,189** mã bệnh duy nhất sạch sẽ.

### Bảng `rxnorm` (Dược phẩm):
*   Nguồn dữ liệu: Tệp ánh xạ offline `db/rxnorm_mapped.json`.
*   Chứa **371** hoạt chất chuẩn y khoa.

### Bảng chỉ mục ảo FTS5 (Tìm kiếm toàn văn):
Để tránh lỗi phân mảnh hoặc lệch chỉ mục trong SQLite FTS5 khi sử dụng bảng nội dung ngoài (`content='icd10'`), câu lệnh đồng bộ bắt buộc phải đồng hành cùng cột `rowid` ẩn:
```sql
-- Đồng bộ bảng ảo bệnh án
INSERT INTO icd10_fts(rowid, code, name_vi) SELECT rowid, code, name_vi FROM icd10;

-- Đồng bộ bảng ảo thuốc
INSERT INTO rxnorm_fts(rowid, rxcui, name) SELECT rowid, rxcui, name FROM rxnorm;
```
Giải pháp đồng bộ `rowid` này giúp khắc phục triệt để lỗi `database disk image is malformed` khi truy vấn FTS5 trên Windows.

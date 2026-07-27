# Kế hoạch Triển khai: Ánh xạ Danh mục Thuốc (pill.txt -> db/rxnorm_mapped.json)

Tiến trình này tách riêng phần logic ánh xạ dược phẩm sang mã RxNorm chuẩn của Mỹ để tạo ra tệp CSDL thô, phục vụ cho việc build database SQLite offline sau này.

---

## 1. Định nghĩa Đầu vào & Đầu ra (Input / Output)

*   **Đầu vào (Input):** Tệp [pill.txt](file:///d:/record_by_me/Viettel_race/pill.txt) chứa danh sách 520+ hoạt chất, sinh phẩm và vắc xin theo phân loại của Bộ Y tế Việt Nam.
*   **Đầu ra (Output):** Thư mục [db/](file:///d:/record_by_me/Viettel_race/db/) chứa tệp kết quả JSON `rxnorm_mapped.json` cấu trúc dạng:
    ```json
    [
      {
        "original_name": "Abacavir (sulfat)",
        "english_name": "abacavir",
        "rxcui": "19053"
      },
      ...
    ]
    ```

---

## 2. Giải pháp Thực hiện

Chúng ta sẽ xây dựng một script độc lập `scratch/map_rxnorm.py` thực hiện các bước sau:

1.  **Đọc và Làm sạch dữ liệu:**
    *   Đọc từng dòng trong `pill.txt`, loại bỏ dòng trống.
    *   Sử dụng Regex để loại bỏ các gốc muối/ghi chú trong ngoặc (ví dụ: `(sulfat)`, `(natri)`, `(valerat)`).
2.  **Chuẩn hóa Ngôn ngữ & Tên thuốc (Translation Layer):**
    *   **Bộ quy tắc Việt-Anh:** Chuyển đổi cách viết phiên âm Việt hóa sang tiếng Anh chuẩn (ví dụ: `clor-` -> `chlor-`, `calci` -> `calcium`, đuôi `-in` -> `-ine`).
    *   **Ánh xạ Vắc xin & Sinh phẩm:** Định nghĩa bảng tra cứu thủ công cho các tên vắc xin/sinh phẩm tiếng Việt phức tạp sang thuật ngữ vắc xin RxNorm tiếng Anh tương ứng (ví dụ: `"Vắc xin phòng Sởi"` -> `"Measles Virus Vaccine"`).
3.  **Tra cứu API NIH RxNav:**
    *   Gửi từng tên thuốc đã chuẩn hóa lên API RxNorm của NIH để lấy mã `rxcui`.
    *   Nếu tra cứu thất bại với tên cụ thể, thử tra cứu với tên gốc (Ingredient).
4.  **Lưu kết quả:** Tạo thư mục `db/` và ghi tệp `rxnorm_mapped.json`.

---

## 3. Các Thay đổi Đề xuất

### [Thành phần: Script ánh xạ thuốc]

#### [NEW] [map_rxnorm.py](file:///d:/record_by_me/Viettel_race/scratch/map_rxnorm.py)
Tệp Python thực thi quy trình đọc, chuẩn hóa tên thuốc, gọi API RxNav và lưu kết quả vào thư mục `db`.

---

## 4. Kế hoạch Xác minh

*   Chạy thử nghiệm script `map_rxnorm.py`.
*   Kiểm tra sự tồn tại của tệp `db/rxnorm_mapped.json`.
*   Đọc thử nội dung JSON để đối chiếu ngẫu nhiên khoảng 5-10 loại thuốc xem mã RxCUI có khớp đúng hoạt chất không (ví dụ: `Aspirin` -> `1191`, `Paracetamol` -> `161`).

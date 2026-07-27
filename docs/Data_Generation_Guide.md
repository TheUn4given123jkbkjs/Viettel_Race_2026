# Hướng dẫn Chạy Script Sinh dữ liệu (Data Generation Guide)

Tài liệu này hướng dẫn cách cài đặt và chạy script sinh dữ liệu huấn luyện lâm sàng Việt-Anh song hành.

---

## 1. Chuẩn bị Môi trường

1.  **Clone repository** về máy:
    ```bash
    git clone https://github.com/TheUn4given123jkbkjs/Viettel_Race_2026.git
    cd Viettel_Race_2026
    ```
2.  **Cài đặt thư viện Python**:
    ```bash
    pip install requests
    ```

---

## 2. Cấu hình Khóa API (Gemini Free Tier)

1.  Truy cập vào trang [Google AI Studio](https://aistudio.google.com/) để tạo một API Key miễn phí (Free API Key).
2.  Cách 1: Tạo một tệp tin đặt tên là **`.env`** tại thư mục gốc và điền nội dung sau:
    ```env
    GEMINI_API_KEY=AIzaSy... (Điền API Key của bạn vào đây)
    ```
3.  Cách 2 (Khuyên dùng khi chạy song song nhiều tiến trình): Cấu hình biến môi trường trực tiếp trong phiên Terminal để chạy song song 2-3 tiến trình với các khóa API khác nhau:
    *   **Trên Windows (PowerShell):**
        ```powershell
        $env:GEMINI_API_KEY="AIzaSy_Khoa_Khac_Nhau_1"; python scratch/generate_train_data.py --member A --num_samples 2000
        ```
    *   **Trên Windows (cmd):**
        ```cmd
        set GEMINI_API_KEY=AIzaSy_Khoa_Khac_Nhau_1 && python scratch/generate_train_data.py --member A --num_samples 2000
        ```

---

## 3. Thực thi tiến trình sinh dữ liệu

Mỗi thành viên được phân công chạy một nhóm chương bệnh ICD-10 riêng biệt. Đầu ra sẽ được ghi vào các thư mục riêng tương ứng (`sample_A`, `sample_B`, `sample_C`) để tránh xung đột ghi đè tệp tin khi chạy song song.

Hãy chạy lệnh tương ứng với phân công của bạn:

*   **Thành viên A (Phụ trách Chương A đến H):**
    ```bash
    python scratch/generate_train_data.py --member A --num_samples 2000
    ```
*   **Thành viên B (Phụ trách Chương I đến P):**
    ```bash
    python scratch/generate_train_data.py --member B --num_samples 2000
    ```
*   **Thành viên C (Phụ trách Chương Q đến Z):**
    ```bash
    python scratch/generate_train_data.py --member C --num_samples 2000
    ```

### Một số lưu ý khi chạy:
*   Script tự động ngủ (sleep) 5 giây giữa các yêu cầu để tránh rate limit của Gemini (15 RPM).
*   Tổng thời gian chạy cho 2,000 mẫu là khoảng **3.3 giờ**. Hãy để script chạy ngầm.
*   Nếu bị gián đoạn, bạn chỉ cần chạy lại lệnh. Script sẽ tự động phát hiện số thứ tự tệp tin hiện có trong `sample_[MEMBER]/input/` để đánh số tiếp theo mà không ghi đè dữ liệu cũ.

---

## 4. Kiểm tra Kết quả và Đẩy lên Git

Sau khi sinh xong, cấu trúc thư mục của bạn sẽ có dạng:
```text
sample_[MEMBER]/
├── input/
│   ├── 1.txt
│   ├── 2.txt
│   └── ...
└── output/
    ├── 1.json
    ├── 2.json
    └── ...
```

Thực hiện Commit và Push kết quả của bạn lên Git:
```bash
git add sample_A/ sample_B/ sample_C/
git commit -m "Thành viên [Tên của bạn] hoàn thành sinh 2000 mẫu"
git push
```

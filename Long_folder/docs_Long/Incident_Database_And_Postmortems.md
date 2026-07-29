# CSDL NHẬT KÝ SỰ CỐ & PHÂN TÍCH SAU SỰ CỐ (INCIDENT DATABASE & POSTMORTEMS)

> **Dự án:** Viettel AI Race 2026 - Nhận diện Thực thể & Chuẩn hóa Mã Y khoa  
> **Định dạng tài liệu:** Chuẩn Postmortem & Root Cause Analysis (RCA) chuyên nghiệp  
> **Cập nhật gần nhất:** 2026-07-28  

Tài liệu này đóng vai trò là cơ sở dữ liệu (Database) ghi nhận toàn bộ các sự cố kỹ thuật phát sinh trong quá trình vận hành hệ thống sinh dữ liệu huấn luyện, phục vụ cho việc theo dõi, tra cứu mã lỗi và rút kinh nghiệm cho các phiên phát triển tiếp theo.

---

## 🗂️ DANH SÁCH LỊCH SỬ SỰ CỐ (INCIDENT REGISTRY)

| ID Sự cố | Ngày phát hiện | Mức độ | Thành phần lỗi | Trạng thái | Lỗi vắn tắt |
| :--- | :--- | :---: | :--- | :---: | :--- |
| **[INC-260728-01](#inc-260728-01)** | 2026-07-28 | **Medium** | `refresh_keys.py` | ✅ **Resolved** | `NameError: name 'time' is not defined` |
| **[INC-260728-02](#inc-260728-02)** | 2026-07-28 | **High** | `key_manager.py` / LPU | ✅ **Resolved** | HTTP 429 Rate Limit khi chạy 5 luồng song song |
| **[INC-260728-03](#inc-260728-03)** | 2026-07-28 | **High** | `generate_train_data_v3.py` | ✅ **Resolved** | Sập nghẽn dồn lưu lượng vào 1 Key Gemini duy nhất |
| **[INC-260728-04](#inc-260728-04)** | 2026-07-28 | **Medium** | `process_and_align` | ✅ **Resolved** | `AttributeError: 'NoneType' object has no attribute 'strip'` |
| **[INC-260728-05](#inc-260728-05)** | 2026-07-28 | **High** | Gemini 2.0 Flash | ✅ **Resolved** | `429 limit: 0` do hardcode model cũ bị Google gán Quota = 0 |
| **[INC-260728-06](#inc-260728-06)** | 2026-07-28 | **Medium** | `key_manager.py` | ✅ **Resolved** | `AttributeError: 'AccountRoundRobinKeyManager' object has no attribute 'get_next_gemini_model'` |
| **[INC-260728-07](#inc-260728-07)** | 2026-07-28 | **Medium** | `refresh_keys.py` | ✅ **Resolved** | `HTTPSConnectionPool Read timed out (10s)` do dồn 8 luồng quét SSL 443 |

---

## 📑 BÁO CÁO PHÂN TÍCH SAU SỰ CỐ CHI TIẾT (DETAILED POSTMORTEMS)

### 🔴 INC-260728-01
* **ID Sự cố:** `INC-260728-01`
* **Ngày phát hiện:** 2026-07-28 00:15 UTC+7
* **Mức độ nghiêm trọng:** **Medium** (Gây sập tiến trình quét sức khỏe API Key)
* **Thành phần ảnh hưởng:** [custom_scripts/refresh_keys.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/refresh_keys.py)
* **Mẫu thông báo lỗi:**
  ```text
  Traceback (most recent call last):
    File "D:\AI Race\Viettel_Race_2026\custom_scripts\refresh_keys.py", line 137, in <module>
      refresh_and_update_env()
    File "D:\AI Race\Viettel_Race_2026\custom_scripts\refresh_keys.py", line 25, in test_single_key
      time.sleep(...)
  NameError: name 'time' is not defined
  ```

#### 🔍 Phân tích Nguyên nhân Gốc rễ (Root Cause Analysis - RCA)
Trong quá trình bổ dung tính năng jitter ngẫu nhiên vào hàm `test_single_key` để tránh spam request đồng loạt lên API Server khi quét sức khỏe, lập trình viên đã viết lệnh `time.sleep()` nhưng quên không khai báo `import time, random` ở đầu tệp tin `refresh_keys.py`.

#### 💥 Tầm ảnh hưởng (Impact)
Hệ thống không thể cập nhật danh sách các key đang sống vào file `.env`, dẫn tới các Worker sinh dữ liệu không thể khởi chạy do thiếu biến môi trường hoạt động.

#### 🛠️ Giải pháp Khắc phục & Phòng ngừa (Resolution & Prevention)
* **Khắc phục:** Bổ sung đầy đủ khai báo thư viện `import time, random` vào đầu tệp [custom_scripts/refresh_keys.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/refresh_keys.py#L6-L8).
* **Phòng ngừa:** Thiết lập kiểm tra chạy thử (Smoke Test) script quét key độc lập trước khi đóng gói hoặc chuyển giao mã nguồn.

---

### 🔴 INC-260728-02
* **ID Sự cố:** `INC-260728-02`
* **Ngày phát hiện:** 2026-07-28 00:25 UTC+7
* **Mức độ nghiêm trọng:** **High** (Làm gián đoạn tiến trình sinh dữ liệu của toàn bộ luồng)
* **Thành phần ảnh hưởng:** [custom_scripts/key_manager.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/key_manager.py) / Groq LPU
* **Mẫu thông báo lỗi:**
  ```text
  🛑 Key [gsk_9WdBGsgU...] (TK: ANIME_BLUE) dính Rate Limit 429. Đang đóng băng 120s an toàn...
  🛑 Key [gsk_XAAZ09Oj...] (TK: CHO_VANG) dính Rate Limit 429. Đang đóng băng 120s an toàn...
  ```

#### 🔍 Phân tích Nguyên nhân Gốc rễ (Root Cause Analysis - RCA)
Hạn mức dịch vụ Groq Free Tier là **30 RPM (Requests Per Minute)** được áp dụng ở **cấp độ Tài khoản (Account / Project)** chứ không phải trên từng Key riêng lẻ. 
Khi chạy 5 CMD Worker song song mà không có cơ chế điều tiết:
1. Tổng số request bắn lên API chạm ngưỡng **60 RPM** (vượt xa giới hạn 30 RPM).
2. Khi Key 1 của tài khoản `CHO_TRANG` bị 429, script lập tức xoay sang Key 2 của tài khoản `CHO_TRANG`. Vì dùng chung tài khoản, Key 2 cũng dính 429 ngay tức khắc, tạo ra phản ứng dây chuyền làm đóng băng toàn bộ các Key Groq chỉ trong 30 giây.

#### 💥 Tầm ảnh hưởng (Impact)
Hệ thống rơi vào trạng thái chờ 120s liên tục, tiến độ sinh dữ liệu bị tê liệt gần như hoàn toàn.

#### 🛠️ Giải pháp Khắc phục & Phòng ngừa (Resolution & Prevention)
* **Khắc phục:** 
  1. Nâng cấp hàm `mark_rate_limited` trong [custom_scripts/key_manager.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/key_manager.py#L165-L172) để khi 1 key dính 429, hệ thống sẽ **đóng băng ngay lập tức toàn bộ các Key thuộc tài khoản đó**.
  2. Tích hợp khóa giãn trễ **Pacing Lock 3.0s/Key** để khống chế tần suất gọi tối đa của mỗi Key không vượt quá 20 RPM.
* **Phòng ngừa:** Giảm số lượng luồng chạy đồng thời từ 5 xuống còn **3 luồng (Sweet Spot)** trong file [run_v3_3workers.bat](file:///d:/AI%20Race/Viettel_Race_2026/run_v3_3workers.bat), khống chế tổng lưu lượng toàn hệ thống ở mức an toàn ~16 RPM.

---

### 🔴 INC-260728-03
* **ID Sự cố:** `INC-260728-03`
* **Ngày phát hiện:** 2026-07-28 00:30 UTC+7
* **Mức độ nghiêm trọng:** **High** (Làm tắc nghẽn luồng dự phòng do chỉ có 1 Key)
* **Thành phần ảnh hưởng:** [custom_scripts/generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/generate_train_data_v3.py)
* **Mẫu thông báo lỗi:**
  ```text
  ⚠️  TOÀN BỘ Key GEMINI đang dính Cooldown. Cần chờ 117.6s...
  ```

#### 🔍 Phân tích Nguyên nhân Gốc rễ (Root Cause Analysis - RCA)
Trong file cấu hình `.env`, dịch vụ Groq có tới 29 keys (10 tài khoản), trong khi Gemini chỉ có duy nhất **1 key hoạt động (`GEMINI_KEY_TIN_3`)**. 
Khi chọn chế độ sinh `--provider auto`, 5 luồng CMD tự động chia 50% số lượng request sang Gemini. Vì Gemini chỉ có 1 key đơn độc gánh tải cho cả 5 luồng, key này bị quá tải và dính 429 lập tức, khiến luồng liên tục in ra cảnh báo Cooldown vô ích.

#### 💥 Tầm ảnh hưởng (Impact)
Làm chậm luồng sinh dữ liệu do liên tục mất thời gian chuyển đổi nhà cung cấp và chờ đợi cooldown của Gemini.

#### 🛠️ Giải pháp Khắc phục & Phòng ngừa (Resolution & Prevention)
* **Khắc phục:** 
  1. Cập nhật logic `available_providers` trong [custom_scripts/generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/generate_train_data_v3.py#L255-L260): **Chỉ cho phép chế độ Auto chọn dịch vụ có từ 2 API Key hoạt động trở lên**. Nếu Gemini chỉ có 1 Key, nó sẽ tự động bị loại để nhường tải cho 29 Key Groq.
  2. Tự động chuyển đổi mô hình trên Groq: Nếu `llama-3.3-70b` bị Rate Limit, tự động fallback sang `llama-3.1-8b-instant` (hạn mức 14.400 RPD độc lập).

---

### 🔴 INC-260728-04
* **ID Sự cố:** `INC-260728-04`
* **Ngày phát hiện:** 2026-07-28 01:03 UTC+7
* **Mức độ nghiêm trọng:** **Medium** (Gây sập luồng đang chạy khi gặp mẫu dữ liệu xấu)
* **Thành phần ảnh hưởng:** Hàm `process_and_align` / Hàm `main`
* **Mẫu thông báo lỗi:**
  ```text
  File "D:\AI Race\Viettel_Race_2026\custom_scripts\generate_train_data_v3.py", line 497, in main
    text_content = raw_sample.get("text", "").strip()
  AttributeError: 'NoneType' object has no attribute 'strip'
  ```

#### 🔍 Phân tích Nguyên nhân Gốc rễ (Root Cause Analysis - RCA)
Đôi khi mô hình LLM sinh ra nội dung không đúng chuẩn hoặc gặp lỗi biên dịch cấu trúc JSON, dẫn tới trường `"text"` trả về có giá trị là `null` (None trong Python) thay vì chuỗi văn bản. Khi chương trình cố gắng gọi `.strip()` trên giá trị `None` này, Python sẽ quăng ra ngoại lệ `AttributeError`.

#### 💥 Tầm ảnh hưởng (Impact)
Làm crash và đóng cửa sổ CMD của Worker đang chạy, buộc người dùng phải khởi động lại luồng đó thủ công.

#### 🛠️ Giải pháp Khắc phục & Phòng ngừa (Resolution & Prevention)
* **Khắc phục:** Tích hợp lớp phòng vệ Type-safety trong tệp [custom_scripts/generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/generate_train_data_v3.py#L381-L411).
  ```python
  text_val = raw_sample.get("text", "")
  text_content = text_val.strip() if isinstance(text_val, str) else ""
  ```
  Nếu giá trị không phải là chuỗi thực tế, hệ thống bỏ qua mẫu đó một cách êm ái mà không gây sụp luồng.

---

### 🔴 INC-260728-05
* **ID Sự cố:** `INC-260728-05`
* **Ngày phát hiện:** 2026-07-28 11:40 UTC+7
* **Mức độ nghiêm trọng:** **High** (Key bị báo 429 giả liên tục)
* **Thành phần ảnh hưởng:** `refresh_keys.py` / `generate_train_data_v3.py`
* **Mẫu thông báo lỗi:**
  ```text
  Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-2.0-flash
  ```

#### 🔍 Phân tích Nguyên nhân Gốc rễ (Root Cause Analysis - RCA)
Mô hình `gemini-2.0-flash` trên Google AI Studio Free Tier bị hạ quota về `limit: 0`. Do mã nguồn trước đó hardcode tên model này nên khi kiểm tra key hoặc gửi request, Google luôn trả về lỗi HTTP 429 `limit: 0`, làm tưởng nhầm toàn bộ key bị dính rate limit 24h.

#### 🛠️ Giải pháp Khắc phục & Phòng ngừa (Resolution & Prevention)
Xây dựng registry cấu hình [models_registry.json](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/models_registry.json), chuyển sang sử dụng các model hỗ trợ Free Tier dạt dào như `gemini-3.1-flash-lite`, `gemini-3.5-flash-lite` (500 RPD) và `gemma-4-31b-it` (14,400 RPD).

---

### 🔴 INC-260728-06
* **ID Sự cố:** `INC-260728-06`
* **Ngày phát hiện:** 2026-07-28 12:09 UTC+7
* **Mức độ nghiêm trọng:** **Medium** (Sập tiến trình khi gọi hàm bị thiếu)
* **Thành phần ảnh hưởng:** [custom_scripts/key_manager.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/key_manager.py)
* **Mẫu thông báo lỗi:**
  ```text
  AttributeError: 'AccountRoundRobinKeyManager' object has no attribute 'get_next_gemini_model'
  ```

#### 🔍 Phân tích Nguyên nhân Gốc rễ (Root Cause Analysis - RCA)
Trong quá trình tái cấu trúc và bổ sung phương thức `update_model_status_in_registry`, phương thức tương thích ngược `get_next_gemini_model()` đã vô tình bị xoá khỏi lớp `AccountRoundRobinKeyManager`.

#### 🛠️ Giải pháp Khắc phục & Phòng ngừa (Resolution & Prevention)
Bổ sung lại phương thức `get_next_gemini_model()` gọi trực tiếp `get_next_model("gemini")` trong [custom_scripts/key_manager.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/key_manager.py#L117-L121).

---

### 🔴 INC-260728-07
* **ID Sự cố:** `INC-260728-07`
* **Ngày phát hiện:** 2026-07-28 12:05 UTC+7
* **Mức độ nghiêm trọng:** **Medium** (Key/Model bị nghẽn timeout do gián đoạn kết nối)
* **Thành phần ảnh hưởng:** [custom_scripts/refresh_keys.py](file:///d:/AI%20Race/Viettel_Race_2026/custom_scripts/refresh_keys.py)
* **Mẫu thông báo lỗi:**
  ```text
  HTTPSConnectionPool(host='generativelanguage.googleapis.com', port=443): Read timed out. (read timeout=10)
  ```

#### 🔍 Phân tích Nguyên nhân Gốc rễ (Root Cause Analysis - RCA)
Script `refresh_keys.py` mở 8 luồng song song quét 90 keys qua kết nối SSL port 443 với `timeout=10s`. Tải quá lớn làm nghẽn socket kết nối mạng Windows, gây ra lỗi timeout hàng loạt và đánh dấu nhầm key/model bị đóng băng.

#### 🛠️ Giải pháp Khắc phục & Phòng ngừa (Resolution & Prevention)
1. Giảm số luồng quét xuống `max_workers=4`, nâng timeout lên 25s và thêm vòng lặp Retry 2 lần.
2. Xử lý ngoại lệ `requests.exceptions.Timeout` riêng: không đánh dấu hết quota đối với lỗi timeout mạng lag.

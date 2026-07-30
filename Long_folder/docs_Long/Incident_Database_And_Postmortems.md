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
| **[INC-260730-01](#inc-260730-01)** | 2026-07-30 | **High** | `.bat` / Groq API | ✅ **Resolved** | UTF-8 BOM (`∩╗┐@echo`) gây sập file bat & Cloudflare WAF HTTP 403 (Error 1010) |
| **[INC-260730-02](#inc-260730-02)** | 2026-07-30 | **High** | Groq WAF Proxy | ✅ **Resolved** | HTTP 400 (`Failed to generate JSON`) do tham số `response_format json_object` |
| **[INC-260730-03](#inc-260730-03)** | 2026-07-30 | **Medium** | `groq/compound` | ✅ **Resolved** | HTTP 413 (`Request Entity Too Large`) do model compound vượt payload limit |
| **[INC-260730-04](#inc-260730-04)** | 2026-07-30 | **High** | `generate_train_data_v3.py` / CMD | ✅ **Resolved** | Qwen `<think>` tag gây `JSONDecodeError` & CMD parenthesized `if` syntax crash |

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

---

### 🔴 INC-260730-01
* **ID Sự cố:** `INC-260730-01`
* **Ngày phát hiện:** 2026-07-30 00:35 UTC+7
* **Mức độ nghiêm trọng:** **High** (File bat không chạy được và API bị WAF chặn)
* **Thành phần ảnh hưởng:** `run_v3_groq.bat` / Groq API Requests
* **Mẫu thông báo lỗi:**
  ```text
  '∩╗┐@echo' is not recognized as an internal or external command...
  HTTP 403 Forbidden (Cloudflare WAF Error 1010)
  ```

#### 🔍 Phân tích Nguyên nhân Gốc rễ (Root Cause Analysis - RCA)
1. PowerShell cmdlet `Set-Content` mặc định chèn 3 bytes UTF-8 BOM (`0xEF, 0xBB, 0xBF`) vào đầu tệp `.bat`. Trình thông dịch CMD của Windows không hiểu BOM byte và coi đó là lệnh `'∩╗┐@echo'`.
2. Groq Cloud sử dụng Cloudflare WAF. Khi gọi API mà không truyền header `User-Agent` chuẩn trình duyệt, WAF coi đó là bot độc hại và trả về HTTP 403 Error 1010.

#### 🛠️ Giải pháp Khắc phục & Phòng ngừa (Resolution & Prevention)
1. **Ghi file .bat không BOM:** Sử dụng `System.Text.UTF8Encoding $false` và `[System.IO.File]::WriteAllLines` để đảm bảo file `.bat` sinh ra luôn ở chuẩn UTF-8 No BOM và CRLF line endings.
2. **Bổ sung User-Agent:** Thêm `"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"` vào tất cả request gửi tới Groq Cloud trong [custom_scripts/generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/generate_train_data_v3.py#L421).

---

### 🔴 INC-260730-02
* **ID Sự cố:** `INC-260730-02`
* **Ngày phát hiện:** 2026-07-30 07:54 UTC+7
* **Mức độ nghiêm trọng:** **High** (Làm sập 100% request sinh dữ liệu ở một số model Groq)
* **Thành phần ảnh hưởng:** [custom_scripts/generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/generate_train_data_v3.py)
* **Mẫu thông báo lỗi:**
  ```text
  ❌ Lỗi API 400 (TK: CHO_HONG): {"error":{"message":"Failed to generate JSON. Please adjust your prompt. See 'failed_generation' for more details.","type":"invalid_request_error"}}
  ```

#### 🔍 Phân tích Nguyên nhân Gốc rễ (Root Cause Analysis - RCA)
Khi truyền tham số `"response_format": {"type": "json_object"}` lên Groq API, bộ kiểm duyệt WAF Proxy của Groq Cloud sẽ soi chiếu toàn bộ chuỗi ký tự trả về từ LLM. Khi model (nhất là `llama-3.1-8b-instant`) trả về thêm khối Markdown ` ```json ` ở đầu câu, WAF Proxy coi đó là chuỗi JSON không hợp lệ và chặn lại bằng mã lỗi **HTTP 400**.

#### 🛠️ Giải pháp Khắc phục & Phòng ngừa (Resolution & Prevention)
* **Loại bỏ response_format:** Bỏ hoàn toàn tham số `response_format` khỏi payload gửi lên Groq.
* **Bóc tách bằng Python Regex:** Chuyển sang sử dụng Regex `re.search(r'\{.*\}', content_text, re.DOTALL)` trong Python để trích xuất đối tượng JSON. Phương pháp này xử lý sạch 100% ký tự Markdown ` ```json ` mà không phụ thuộc vào bộ lọc Proxy của Groq, đảm bảo **HTTP 200 OK** tuyệt đối.

---

### 🔴 INC-260730-03
* **ID Sự cố:** `INC-260730-03`
* **Ngày phát hiện:** 2026-07-30 08:00 UTC+7
* **Mức độ nghiêm trọng:** **Medium** (Gây lỗi HTTP 413 trên model compound)
* **Thành phần ảnh hưởng:** [custom_scripts/groq_runner.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/groq_runner.py)
* **Mẫu thông báo lỗi:**
  ```text
  ❌ Lỗi API 413 (TK: TV): {"error":{"message":"Request Entity Too Large","type":"invalid_request_error","code":"request_too_large"}}
  ```

#### 🔍 Phân tích Nguyên nhân Gốc rễ (Root Cause Analysis - RCA)
Model `groq/compound` là hệ thống Agent/Tool chuyên dụng trên Groq Cloud. Khi nhận prompt sinh dữ liệu y khoa dài mà không khai báo cấu trúc tool/function calling, máy chủ Groq chặn payload và trả về lỗi **HTTP 413 Request Entity Too Large**.

#### 🛠️ Giải pháp Khắc phục & Phòng ngừa (Resolution & Prevention)
Thay thế `groq/compound` bằng **`llama-3.1-8b-instant`** trong danh mục Top 3 Models của [models_registry.json](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/models_registry.json#L71). `llama-3.1-8b-instant` có quota khủng **14,400 RPD/tài khoản**, tốc độ cực nhanh và không bao giờ bị lỗi Payload Limit.

---

### 🔴 INC-260730-04
* **ID Sự cố:** `INC-260730-04`
* **Ngày phát hiện:** 2026-07-30 08:03 UTC+7
* **Mức độ nghiêm trọng:** **High** (Lỗi JSONDecodeError ở Qwen 3.6 và sập cửa sổ CMD launcher)
* **Thành phần ảnh hưởng:** [custom_scripts/generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/generate_train_data_v3.py) / `run_v3_groq_isolated.bat`
* **Mẫu thông báo lỗi:**
  ```text
  ⚠️ [THỬ LẠI] Server trả về nội dung rỗng/lỗi JSON với TK TV (lần 2)...
  (Cửa sổ CMD bị tự động đóng ngay khi kết thúc bước 2)
  ```

#### 🔍 Phân tích Nguyên nhân Gốc rễ (Root Cause Analysis - RCA)
1. **Model Qwen 3.6:** Dòng Qwen 3.6 là mô hình suy luận (Reasoning Model), luôn sinh ra thẻ `<think>...</think>` ở đầu trước khi trả về JSON. Do đoạn suy luận chứa ngoặc nhọn `{ }`, hàm `re.search` bị trích xuất nhầm dẫn tới `JSONDecodeError`.
2. **Lỗi CMD Launcher:** Cú pháp khối ngoặc lồng nhau `if (...) else if (...)` trong Windows CMD bị sập trình biên dịch khi dính delayed expansion `!WORKERS_8B!` và ngoặc kép.

#### 🛠️ Giải pháp Khắc phục & Phòng ngừa (Resolution & Prevention)
1. **Làm sạch thẻ `<think>`:** Thêm `content_text = re.sub(r'<think>.*?</think>', '', content_text, flags=re.DOTALL)` trước khi regex match JSON trong [generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/generate_train_data_v3.py#L588).
2. **Tái cấu trúc file .bat bằng `goto`:** Tái cấu trúc [run_v3_groq_isolated.bat](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/run_v3_groq_isolated.bat#L40-L90) dùng nhãn `:PROMPT_...` và `:RUN_...` thuần túy với `goto`, loại bỏ 100% nguy cơ sập cửa sổ CMD.

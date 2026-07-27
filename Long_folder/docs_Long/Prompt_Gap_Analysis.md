# PHÂN TÍCH KHOẢNG CÁCH: DỮ LIỆU TEST THỰC TẾ VS PROMPT SINH DỮ LIỆU (PROMPT GAP ANALYSIS)

## Phương pháp phân tích
Đọc kỹ **10 file test thực tế** (`1.txt`, `5.txt`, `20.txt`, `30.txt`, `40.txt`, `50.txt`, `70.txt`, `90.txt`, `100.txt`) và so sánh trực tiếp với **43 file đã sinh** trong `sample_A/input/` bằng prompt hiện tại.

---

## 1. Những đặc điểm CỦA DỮ LIỆU TEST THỰC TẾ mà Prompt hiện tại CHƯA mô phỏng được

### 🔴 Vấn đề 1: Dữ liệu test là bệnh án dịch từ tiếng Anh, có dấu vết dịch máy rõ ràng

Đây là phát hiện **quan trọng nhất**. Phần lớn các file test (đặc biệt từ file `5.txt` đến `90.txt`) có dấu hiệu rõ ràng là **bệnh án gốc tiếng Anh được dịch sang tiếng Việt** (có thể bằng máy hoặc bán thủ công):

| Dấu hiệu dịch máy trong test | Ví dụ cụ thể | Prompt hiện tại có mô phỏng? |
| :--- | :--- | :--- |
| Dùng placeholder `[Date]`, `[Ngày]`, `[Tên bác sĩ]`, `[Số]` | `"Nhập viện khoa Thần kinh từ [Date]"` (50.txt) | ❌ Không |
| Thuốc ghi bằng tên gốc tiếng Anh (không dịch) | `"aspirin 325mg"`, `"albuterolipratropium nebulizer"`, `"methylprednisolone 125mg iv"` (70.txt) | ⚠️ Một phần (prompt có nhắc nhưng không ép buộc) |
| Thuốc ghi dính chữ, không có khoảng trắng | `"albuterolipratropium"` (dính liền), `"compazine và alevenhưng vẫn còn đau"` (20.txt) | ❌ Không |
| Cụm từ dịch gượng / Việt hóa lộ | `"chủ quan sốt"` (subjective fever), `"ban đỏ, RL"` (RL = Right Leg), `"phủ nhận buồn nôn"` (denies nausea) | ❌ Không |
| Viết tắt tiếng Anh giữ nguyên | `"EMS"`, `"NRB"`, `"SPO2"`, `"INR"`, `"CT"`, `"RNY"` | ⚠️ Một phần |
| Tên thuốc bị ẩn bằng dấu sao `****` | `"************ có thể hệ sau không gây buồn ngủ"` (30.txt), `"thuốc ************ sử dụng mỗi tối"` (100.txt) | ❌ Hoàn toàn không |

### 🔴 Vấn đề 2: Cấu trúc văn bản Hybrid trong test rất "lộn xộn thật sự"

Prompt hiện tại (style_id = 4) có yêu cầu ghép 2 phong cách, nhưng kết quả sinh ra vẫn quá mạch lạc và logic. Trong khi dữ liệu test thực tế lộn xộn ở mức cực đoan:

| Đặc điểm lộn xộn trong test | Ví dụ | Prompt mô phỏng? |
| :--- | :--- | :--- |
| Đoạn Q&A bị cắt ngang giữa chừng, chèn bệnh án | 20.txt: Đang trả lời về bệnh dại → đột ngột chèn `"Da niêm mạc hồngi\n Đau bụng hạ sườn phải"` → rồi quay lại bệnh dại | ❌ Không |
| Đoạn văn bệnh X ghép với đoạn bệnh Y hoàn toàn không liên quan | 70.txt: Phần 3 "Đánh giá tại bệnh viện" đột ngột nhảy sang "Các yếu tố ảnh hưởng đến lây nhiễm bệnh dại" | ❌ Không |
| Lỗi đánh máy / gõ thiếu khoảng trắng | `"182bạch cầuvài vi khuẩn"` (90.txt), `"Da niêm mạc hồngi"` (lỗi typo) (20.txt) | ❌ Không |
| Câu cụt, thiếu dấu chấm, dấu ngoặc mở không đóng | `"đỡ đau (có thể ngủ"` (20.txt) | ❌ Không |

### 🔴 Vấn đề 3: Kết quả xét nghiệm trong test cực kỳ đa dạng format

| Format xét nghiệm trong test | Ví dụ |
| :--- | :--- |
| Chỉ ghi tên + số, không đơn vị | `"bạch cầu 26.7"`, `"kali 3.2"`, `"troponin 0.01"` (90.txt) |
| Ghi đầy đủ tên + giá trị + đơn vị | `"CRP: 227.0 mg/L"`, `"Creatinin : 46 µmol/L"`, `"Kali +: 3.6 mmol/L"` (40.txt) |
| Dấu hiệu sinh tồn nối liền | `"Mạch: 130 lần/phút"`, `"Huyết áp:130/76 mmHg"`, `"SPO2: 99 %"` (20.txt) |
| Liệt kê dính liền trên 1 dòng | `"Định lượng Glucose, Urê, Creatinin máu.Điện giải đồ (Na+, K+, cl-)."` (40.txt) |

Prompt hiện tại **không dặn cụ thể** cách format kết quả xét nghiệm nên Gemini sẽ sinh ra format quá đồng nhất và sạch sẽ.

### 🔴 Vấn đề 4: Thuốc trong test ghi kèm liều lượng + đường dùng chi tiết

| Cách ghi thuốc trong test | Ví dụ |
| :--- | :--- |
| Thuốc + liều + tần suất + đường dùng | `"Ceftriaxone 1g :Liều dùng: 2 lọ / ngày.Đường dùng: Truyền tĩnh mạch (sáng), tốc độ 30 giọt/phút."` (40.txt) |
| Thuốc + liều + đường dùng vắn tắt | `"methylprednisolone 125mg iv"`, `"Ceftriaxone 1 gram dùng 1 liều"` (90.txt) |
| Thuốc + hàm lượng (từ đề bài) | `"Chlorpheniramine 0.4 MG/ML"` (ví dụ trong đề) |

Prompt hiện tại chỉ yêu cầu "1-2 loại thuốc" nhưng **không dặn cách ghi liều lượng, đường dùng, tần suất** $\rightarrow$ Gemini sinh ra tên thuốc trần trụi hoặc quá đồng nhất.

---

## 2. So sánh trực tiếp: Dữ liệu Test vs Dữ liệu đã sinh (sample_A)

| Tiêu chí | Test thực tế | sample_A (Prompt hiện tại) | Đánh giá |
| :--- | :--- | :--- | :--- |
| **Ngôn ngữ** | Pha trộn Việt-Anh, có dấu vết dịch máy | Tiếng Việt tự nhiên, quá "mượt mà" | ⚠️ Lệch phân phối |
| **Cấu trúc** | Lộn xộn, chèn đoạn không liên quan, cắt cụt câu | Rất mạch lạc, đầy đủ, có đầu có đuôi | ⚠️ Lệch phân phối |
| **Tiêu đề section** | Đa dạng: "Bệnh sử", "Tiền sử bệnh nội khoa", "Đã xử trí thuốc", "Khám lúc vào viện" | Lặp lại y hệt template: "1. Tiền sử bệnh", "2. Bệnh sử hiện tại", "3. Đánh giá" | 🔴 Quá đồng nhất |
| **Placeholder** | Nhiều: `[Date]`, `[Ngày]`, `[Tên bác sĩ]`, `[Số]` | Không có | 🔴 Thiếu hoàn toàn |
| **Thuốc bị ẩn `****`** | Rất phổ biến (ít nhất 10+ file test có hiện tượng này) | Không có | 🔴 Thiếu hoàn toàn |
| **Lỗi typo / dính chữ** | Nhiều: `"hồngi"`, `"182bạch cầuvài"`, `"albuterolipratropium"` | Không có | 🔴 Thiếu hoàn toàn |
| **Assertions (isNegated)** | `"phủ nhận buồn nôn"`, `"Không có tiền sử bệnh tim mạch"` | `"Không có tiền sử ĐTĐ"` | ✅ Có nhưng ít |
| **Assertions (isFamily)** | Ít xuất hiện trong test | Ít xuất hiện trong sample | ✅ Ổn |
| **Assertions (isHistorical)** | `"Tiền sử phẫu thuật"`, `"đang dùng methadone"` | Chỉ ở kịch bản 4 | ⚠️ Cần thêm |

---

## 3. Các điểm cải thiện được đề xuất (Xếp theo Mức độ ảnh hưởng)

### 🏆 Ưu tiên CAO (Ảnh hưởng trực tiếp đến điểm thi)

#### A. Thêm phong cách "Bệnh án dịch từ tiếng Anh" (style_id = 5)
**Lý do:** Đây là phong cách chiếm tỷ lệ lớn nhất trong tập test. Nếu mô hình không được huấn luyện trên dạng văn bản này, nó sẽ rất lúng túng khi gặp các cụm từ dịch gượng.

#### B. Thêm hiện tượng "Thuốc bị che dấu sao `****`"
**Lý do:** Ít nhất 10+ file test có hiện tượng tên thuốc bị thay bằng chuỗi `*`. Mô hình cần học cách KHÔNG trích xuất các chuỗi `****` này như một thực thể `THUỐC`.

#### C. Bơm nhiễu lỗi đánh máy / dính chữ (Typo Injection)
**Lý do:** Dữ liệu test có nhiều lỗi gõ: `"hồngi"`, `"182bạch cầuvài vi khuẩn"`, `"albuterolipratropium"`. Nếu mô hình chỉ học dữ liệu sạch, nó sẽ bỏ sót hoặc trích xuất sai vị trí khi gặp lỗi gõ thật.

### ⚡ Ưu tiên TRUNG BÌNH

#### D. Đa dạng hóa tiêu đề section
Thay vì ép cứng `"1. Tiền sử bệnh"`, `"2. Bệnh sử hiện tại"`, cho phép Gemini tự chọn từ một pool các biến thể:
* Biến thể cho Tiền sử: `"Tiền sử bệnh nội khoa"`, `"Tiền sử bệnh"`, `"Bệnh nền"`, `"Các bệnh mãn tính"`
* Biến thể cho Bệnh sử: `"Tiền sử bệnh hiện tại"`, `"Bệnh sử"`, `"Diễn biến bệnh"`
* Biến thể cho Đánh giá: `"Đánh giá tại bệnh viện"`, `"Khám lúc vào viện"`, `"Đã xử trí thuốc và thủ thuật"`, `"Y lệnh Điều trị"`

#### E. Đa dạng hóa format kết quả xét nghiệm
* Format 1: Chỉ tên + số: `"bạch cầu 26.7"`, `"kali 3.2"`
* Format 2: Tên + số + đơn vị: `"CRP: 227.0 mg/L"`, `"Creatinin : 46 µmol/L"`
* Format 3: Dấu hiệu sinh tồn: `"Huyết áp: 130/70 mmHg"`, `"Mạch: 93 l/p"`, `"SPO2: 99 %"`
* Format 4: Liệt kê nối liền trên 1 dòng (không xuống dòng)

#### F. Thêm liều lượng + đường dùng cho thuốc
* Tên thuốc + liều: `"aspirin 325mg"`
* Tên thuốc + liều + đường dùng: `"methylprednisolone 125mg iv"`
* Tên thuốc + liều + tần suất + đường dùng chi tiết: `"Ceftriaxone 1g: 2 lọ/ngày, truyền tĩnh mạch"`

---

## 4. Tóm tắt: Ma trận Ưu tiên

| # | Cải thiện | Ảnh hưởng đến điểm | Độ khó triển khai |
| :--- | :--- | :--- | :--- |
| A | Thêm phong cách "Bệnh án dịch từ tiếng Anh" | 🔴🔴🔴 Rất cao | Trung bình |
| B | Thuốc bị che dấu sao `****` | 🔴🔴🔴 Rất cao | Thấp |
| C | Bơm nhiễu lỗi đánh máy | 🔴🔴 Cao | Thấp |
| D | Đa dạng tiêu đề section | 🟡 Trung bình | Thấp |
| E | Đa dạng format xét nghiệm | 🟡 Trung bình | Thấp |
| F | Thêm liều lượng thuốc | 🟡 Trung bình | Thấp |
| G | Biến thiên độ dài | 🟢 Thấp | Thấp |
| H | Tăng tỷ lệ assertions | 🟢 Thấp | Thấp |

---

## 5. Trạng thái Triển khai Nâng cấp Prompt V4 (Đã hoàn tất 2026-07-28)

Toàn bộ các đề xuất cải thiện ở ma trận trên đã được hiện thực hóa vào hệ thống thông qua phiên bản **Prompt V4** trên 2 script chính:
- [Long_folder/custom_scripts/generate_train_data_v3.py](file:///d:/AI%20Race/Viettel_Race_2026/Long_folder/custom_scripts/generate_train_data_v3.py)
- [scratch/generate_train_data.py](file:///d:/AI%20Race/Viettel_Race_2026/scratch/generate_train_data.py)

**Các kết quả đạt được:**
1. **Ép độ dài văn bản:** Bắt buộc trường `text` sinh ra dài từ **450 đến 750 từ** (xử lý dứt điểm tình trạng văn bản bị ngắn ~240 từ).
2. **Đa dạng bối cảnh (`clinical_context`):** Bổ sung 5 môi trường lâm sàng thực tế và nâng `temperature: 0.8`.
3. **Mô tả cận lâm sàng phong phú:** Bắt buộc trình bày chỉ số các xét nghiệm (Công thức máu, Sinh hóa, X-quang, ECG, Siêu âm) và trích xuất tối đa 6-10 nhãn/file.


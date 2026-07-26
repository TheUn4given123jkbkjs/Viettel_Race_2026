Dưới đây là **toàn bộ đề bài (từ phần 1 đến phần 6)** được gom gọn trọn vẹn trong **đúng 1 khối mã Markdown duy nhất** để bạn chỉ cần bấm nút **Copy** một lần duy nhất là xong:

```markdown
# Bài 2: Ontological Reasoning in Medical Knowledge Retrieval
**Cuộc thi:** Viettel AI Race 2026 (Vòng 1 - Sơ loại)

---

## 1. Tổng quan & Bối cảnh

### 1.1 Tổng quan
Bài toán tập trung vào việc sử dụng các giải pháp NLP, LLM hoặc hệ thống Multi-Agent nhằm xây dựng một mô hình AI có khả năng thực hiện đồng thời:
1. **Xác định và chuẩn hóa khái niệm y tế chuyên môn** (Entity Extraction & Normalization).
2. **Suy luận bối cảnh & thuộc tính** (Ontological Reasoning) trên dữ liệu văn bản y khoa tự do (*free-form clinical text*).

Hệ thống được cung cấp các cơ sở tri thức y khoa chuẩn là **ICD-10** (cho bệnh/chẩn đoán) và **RxNorm** (cho thuốc). Nhiệm vụ chính của mô hình:
- Phát hiện các thực thể y tế xuất hiện trong văn bản.
- Phân loại thực thể (triệu chứng, kết quả xét nghiệm, chẩn đoán, thuốc...).
- Ánh xạ các thực thể đến các mã định danh chuẩn (ICD-10, RxNorm).
- Xác định bối cảnh/trạng thái (assertions) của từng khái niệm trong đoạn văn.

### 1.2 Bối cảnh
Trong thực tế vận hành y tế, phần lớn dữ liệu lâm sàng vẫn tồn tại dưới dạng văn bản tự do như ghi chú của bác sĩ, mô tả triệu chứng, kết luận chẩn đoán hay báo cáo cận lâm sàng. Các văn bản này thường sử dụng từ viết tắt, thuật ngữ địa phương, có lỗi chính tả hoặc cấu trúc không đồng nhất.

Việc chuẩn hóa các khái niệm y tế tự do sang các hệ mã chuẩn quốc tế (như ICD-10, RxNorm, SNOMED CT...) đóng vai trò nền tảng cho việc liên thông dữ liệu, hỗ trợ chẩn đoán, nghiên cứu dịch tễ và xây dựng các hệ thống AI y khoa quy mô lớn.

---

## 2. Mô tả Bài toán (Input / Output)

### 2.1 Input
* **Định dạng:** Đoạn văn bản y khoa tự do (*free-form text*).
* **Nguồn dữ liệu:** Kết quả khám lâm sàng, giấy xuất viện, ghi chú bác sĩ, kết quả xét nghiệm, hồ sơ sức khỏe điện tử (EHR)...
* **Đặc điểm:** Chứa đồng thời nhiều thuật ngữ y khoa, từ viết tắt và các loại khái niệm khác nhau.

**Ví dụ Input:**
> *"Bệnh nhân nam 70 tuổi bị bệnh 1 tuần nay, ho đờm xanh, tức ngực, đau thượng vị, ợ hơi, được chẩn đoán mắc bệnh trào ngược dạ dày - thực quản. Bệnh nhân có tiền sử sử dụng Chlorpheniramine 0.4 MG/ML, Capsaicin 0.38 MG/ML, đã tiến hành tổng phân tích tế bào máu bằng máy lazer (tbm): WBC:14,43; NEUT% (Tỷ lệ % bạch cầu trung tính):76,4; LYPH% (Tỷ lệ bạch cầu lympho):12,8;"*

### 2.2 Output
Output trả về dưới dạng danh sách các khái niệm y tế (List of Dicts / JSON Array). Mỗi đối tượng khái niệm gồm 5 trường:

1. **`text`** *(string)*: Cụm từ chính xác được trích xuất từ văn bản gốc.
2. **`position`** *(list[int])*: Mảng 2 phần tử `[start, end]` chỉ vị trí ký tự bắt đầu và kết thúc của cụm từ trong văn bản gốc (index tính từ `0` đến `n - 1`).
3. **`type`** *(string)*: Nhãn phân loại khái niệm, nhận 1 trong 5 giá trị:
   - `TRIỆU_CHỨNG`: Tên triệu chứng bệnh nhân gặp phải.
   - `TÊN_XÉT_NGHIỆM`: Tên chỉ số / phương pháp xét nghiệm.
   - `KẾT_QUẢ_XÉT_NGHIỆM`: Giá trị kèm đơn vị đo của xét nghiệm.
   - `CHẨN_ĐOÁN`: Kết luận bệnh của bác sĩ.
   - `THUỐC`: Tên và hàm lượng thuốc điều trị.
4. **`assertions`** *(list[string])*: Thuộc tính ngữ cảnh của khái niệm (chỉ áp dụng cho `CHẨN_ĐOÁN`, `THUỐC`, `TRIỆU_CHỨNG`). Danh sách chứa tối đa 3 nhãn:
   - `"isNegated"`: Bị phủ định (VD: *"không ho"*).
   - `"isFamily"`: Liên quan đến người thân/gia đình (VD: *"bố bệnh nhân bị tiểu đường"*).
   - `"isHistorical"`: Liên quan đến tiền sử bệnh nhân (VD: *"có tiền sử hen suyễn"*).
5. **`candidates`** *(list[string])*: Danh sách mã chuẩn hóa (chỉ áp dụng cho `CHẨN_ĐOÁN` và `THUỐC`):
   - Mã **ICD-10** nếu `type` là `CHẨN_ĐOÁN`.
   - Mã **RxNorm** nếu `type` là `THUỐC`.

---

## 3. Cấu trúc File JSON Output Mẫu

Với ví dụ Input ở trên, file JSON đầu ra tương ứng sẽ có dạng:

```json
[
  {
    "text": "ho đờm xanh",
    "position": [41, 52],
    "type": "TRIỆU_CHỨNG",
    "assertions": [],
    "candidates": []
  },
  {
    "text": "bệnh trào ngược dạ dày - thực quản",
    "position": [108, 142],
    "type": "CHẨN_ĐOÁN",
    "assertions": [],
    "candidates": ["K21.0", "K21.9"]
  },
  {
    "text": "Chlorpheniramine 0.4 MG/ML",
    "position": [178, 204],
    "type": "THUỐC",
    "assertions": ["isHistorical"],
    "candidates": ["360047"]
  },
  {
    "text": "WBC",
    "position": [291, 294],
    "type": "TÊN_XÉT_NGHIỆM",
    "assertions": [],
    "candidates": []
  },
  {
    "text": "14,43",
    "position": [295, 300],
    "type": "KẾT_QUẢ_XÉT_NGHIỆM",
    "assertions": [],
    "candidates": []
  }
]

```

---

## 4. Dữ liệu bài toán

### 4.1 CSDL Chuẩn

* **Bệnh / Chẩn đoán:** Sử dụng cơ sở dữ liệu chuẩn **ICD-10**.
* **Thuốc:** Sử dụng cơ sở dữ liệu chuẩn **RxNorm**.

### 4.2 Cấu trúc Tập Test

* **Số lượng:** Tập test công khai gồm 100 bản ghi.
* **Định dạng nhận được:** File nén `test.zip`. Sau khi giải nén, cấu trúc thư mục như sau:
```text
test/
└── input/
    ├── 1.txt      # Văn bản đầu vào của bản ghi 1
    ├── 2.txt      # Văn bản đầu vào của bản ghi 2
    ├── …
    └── 100.txt    # Văn bản đầu vào của bản ghi 100

```


* **Đặc điểm:** Các file `.txt` chứa văn bản y khoa dạng tự do (*free-form text*). Mỗi văn bản chứa nhiều hơn 1 khái niệm y tế.

### 4.3 Quy cách Nộp bài

* Với mỗi file `X.txt` ở đầu vào, mô hình phải sinh ra file `X.json` tương ứng.
* File JSON chứa một danh sách các đối tượng (`List[Dict]`), thể hiện toàn bộ các khái niệm y tế trích xuất được từ văn bản.
* **Nộp kết quả:** Nén toàn bộ 100 file `.json` vào 1 file `.zip` duy nhất và gửi lên hệ thống chấm điểm.

### 4.4 Dữ liệu Huấn luyện (Train Data)

* Ban tổ chức **không cung cấp tập Train đầy đủ**.
* Thí sinh cần chủ động xây dựng, thu thập hoặc tự sinh thêm dữ liệu ngoài (sử dụng LLM, dữ liệu y khoa mở...) để huấn luyện mô hình.

---

## 5. Phương pháp Đánh giá & Cách tính Điểm (Evaluation Metrics)

Điểm số tổng hợp cuối cùng (**`final_score`**) trên tập kiểm tra được xác định bằng trung bình có trọng số của 3 chỉ số thành phần:

$$\text{final\_score} = 0.3 \cdot \text{text\_score} + 0.3 \cdot \text{assertions\_score} + 0.4 \cdot \text{candidates\_score}$$

### 5.1 Quy tắc Ghép cặp Concept (Matching Logic)

Trước khi chấm điểm các trường thông tin:

* Một khái niệm dự đoán ($\text{pred}$) chỉ được coi là ghép cặp thành công (Match) với đáp án chuẩn ($\text{gold}$) khi **khớp chính xác trường `type**`.
* Nếu dự đoán **đúng đoạn `text**` nhưng **sai `type**` (ví dụ: thực tế là `TRIỆU_CHỨNG` nhưng mô hình dự đoán là `CHẨN_ĐOÁN`), cặp đó sẽ bị coi là dự đoán thừa (False Positive) và **bị tính 0 điểm ở cả 3 metric**.

---

### 5.2 Chi tiết Công thức cho từng Metric

#### A. `text_score` (Độ chính xác về đoạn văn bản) - Trọng số 30%

Đánh giá mức độ sai lệch giữa chuỗi văn bản trích xuất so với đáp án gốc thông qua chỉ số **WER (Word Error Rate - Tỷ lệ lỗi từ)**.

* **Công thức WER cho từng khái niệm:**

$$\text{WER} = \frac{S + D + I}{N}$$



*(Trong đó: $S$ là số từ bị thay thế, $D$ là số từ bị xóa, $I$ là số từ bị thêm vào, $N$ là tổng số từ trong đáp án chuẩn).*
* **Công thức tính điểm `text_score` cho một cặp khái niệm:**

$$\text{score\_text}_i = \max(0, 1 - \text{WER}_i)$$


* **Điểm `text_score` tổng:** Trung bình cộng điểm `score_text` của tất cả các khái niệm khớp nhau trong tập dữ liệu.

---

#### B. `assertions_score` (Độ chính xác về thuộc tính ngữ cảnh) - Trọng số 30%

Sử dụng chỉ số **Jaccard Similarity** để đánh giá mức độ tương đồng giữa tập hợp các nhãn thuộc tính (`assertions`) dự đoán và đáp án chuẩn.

* **Công thức Jaccard cho một khái niệm:**

$$\text{Jaccard\_assertions}_i = \frac{|\text{Assertions}_{\text{pred}} \cap \text{Assertions}_{\text{gold}}|}{|\text{Assertions}_{\text{pred}} \cup \text{Assertions}_{\text{gold}}|}$$


* **Lưu ý quy đổi:**
* Nếu cả đáp án chuẩn và dự đoán đều rỗng (`[]`), điểm đạt **1.0**.
* Nếu một bên rỗng và một bên có chứa nhãn, điểm đạt **0.0**.


* **Điểm `assertions_score` tổng:** Trung bình cộng điểm Jaccard của tất cả các khái niệm thuộc nhóm được đánh giá (`CHẨN_ĐOÁN`, `THUỐC`, `TRIỆU_CHỨNG`).

---

#### C. `candidates_score` (Độ chính xác về mã chuẩn hóa) - Trọng số 40%

Sử dụng chỉ số **Jaccard Similarity** có trọng số để đánh giá độ chính xác của tập hợp các mã ICD-10 hoặc RxNorm.

* **Công thức Jaccard cho tập candidate:**

$$\text{Jaccard\_candidates}_i = \frac{|\text{Candidates}_{\text{pred}} \cap \text{Candidates}_{\text{gold}}|}{|\text{Candidates}_{\text{pred}} \cup \text{Candidates}_{\text{gold}}|}$$


* **Lưu ý quan trọng:** Metric này **chỉ áp dụng đối với các khái niệm loại `CHẨN_ĐOÁN` và `THUỐC**`. Các loại khái niệm khác (`TRIỆU_CHỨNG`, `TÊN_XÉT_NGHIỆM`, `KẾT_QUẢ_XÉT_NGHIỆM`) không tham gia vào tính toán metric này.

---

## 6. Quy định chung & Giới hạn kỹ thuật

* **Giới hạn Mô hình Self-host:** Mô hình ngôn ngữ tự host (nếu sử dụng) không vượt quá quy mô **9 tỷ tham số (9B parameters)**.
* **Tần suất nộp bài:** Tối đa **5 lần / ngày**. Thời gian giãn cách tối thiểu giữa 2 lần nộp liên tiếp là **600 giây (10 phút)**.
* **Yêu cầu Tái lập kết quả (Reproducibility):** Kết thúc vòng thi, Top ~15 đội dẫn đầu bảng xếp hạng sẽ phải gửi toàn bộ mã nguồn (Source Code), trọng số mô hình (Model Weights), dữ liệu huấn luyện và file hướng dẫn `README` để Ban Tổ chức thẩm định.

```

```
# 📊 BÁO CÁO PHÂN TÍCH LỖI DỰ ĐOÁN SUBMISSION V4

## 📅 Thông tin phân tích
* **Thư mục dữ liệu nguồn:** `finetune_qwen_7b/submission_v4`
* **Tổng số tệp tin phân tích:** 100
* **Tổng số thực thể dự đoán:** 879

---

## 📈 Thống kê chung về thực thể

### Phân phối loại thực thể:
* **CHẨN_ĐOÁN:** 329 nhãn
* **TRIỆU_CHỨNG:** 399 nhãn
* **THUỐC:** 110 nhãn
* **KẾT_QUẢ_XÉT_NGHIỆM:** 29 nhãn
* **TÊN_XÉT_NGHIỆM:** 12 nhãn

### Phân tích chuẩn hóa mã (ICD-10 / RxNorm):
* **Tổng số thực thể có thể gắn mã (CHẨN_ĐOÁN & THUỐC):** 439
* **Số thực thể bị LLM gán mã SAI / Ảo giác (Khác CSDL):** 268 (61.05%)
* **Số thực thể trống mã (Không tìm thấy):** 23 (5.24%)

---

## 🔍 Nguyên nhân cốt lõi khiến điểm số thấp (8.4%)

### 1. 🚨 LỖI GHI ĐÈ KHÔNG HOẠT ĐỘNG (THE OVERWRITE BUG)
Trong kịch bản suy luận `run_kaggle_inference.py`, điều kiện để gọi bộ chuẩn hóa mã `HybridLinker` là:
```python
if etype in ["CHẨN_ĐOÁN", "THUỐC"] and not candidates:
    candidates = linker.link_entity(exact_text, etype)
```
Do mô hình Qwen đã được fine-tune, nó luôn tự tin sinh ra trường `"candidates"` chứa mã ICD-10 hoặc RxNorm trực tiếp (thường là mã **ảo giác/sai lệch**). 
Vì `candidates` đã chứa giá trị (không rỗng), điều kiện `not candidates` trả về `False` $\rightarrow$ **Bộ liên kết dữ liệu `HybridLinker` bị bỏ qua hoàn toàn**. Kết quả là 100% các mã ảo giác lỗi của LLM được giữ nguyên và ghi vào file nộp bài!

### 2. 🕳️ Ví dụ thực tế về mã bị ảo giác từ LLM (Discrepancy Samples):

| Tên Tệp | Văn bản thực thể | Loại thực thể | LLM Gợi ý (Sai) | CSDL Chuẩn hóa (Đúng) |
| :--- | :--- | :--- | :--- | :--- |
| 1.json | Thiếu men G6PD | CHẨN_ĐOÁN | `['E71.0']` | `[]` |
| 1.json | thiếu men G6PD | CHẨN_ĐOÁN | `['E71.0']` | `[]` |
| 1.json | thiếu men G6PD | CHẨN_ĐOÁN | `['E70.0']` | `[]` |
| 1.json | Bại não | CHẨN_ĐOÁN | `['P91']` | `['G80']` |
| 1.json | thiếu men G6PD | CHẨN_ĐOÁN | `['E71.0']` | `[]` |
| 1.json | đậu tằm | CHẨN_ĐOÁN | `['R51']` | `['H92.0']` |
| 1.json | thiếu men G6PD | CHẨN_ĐOÁN | `['E71.0']` | `[]` |
| 1.json | thiếu men G6PD | CHẨN_ĐOÁN | `['E71.8']` | `[]` |
| 11.json | tụ máu ngoài màng cứng phải | CHẨN_ĐOÁN | `['A36.0']` | `[]` |
| 11.json | bàn chân bẹt | CHẨN_ĐOÁN | `['Q66.5']` | `['Q72.7']` |
| 11.json | không đau | CHẨN_ĐOÁN | `['R51']` | `[]` |
| 12.json | Bệnh phổi kẽ | CHẨN_ĐOÁN | `['A52.72']` | `[]` |
| 12.json | Suy giảm miễn dịch | CHẨN_ĐOÁN | `['E88.1']` | `['D81']` |
| 12.json | đau đớn | CHẨN_ĐOÁN | `['R51']` | `[]` |
| 12.json | tịt ống tai ngoài | CHẨN_ĐOÁN | `['Q11']` | `[]` |

---

## 💡 Đề xuất hành động khắc phục ngay lập tức

Để nâng điểm số lên mức tối đa, chúng ta cần:
1. **Ép buộc ghi đè:** Sửa đổi logic trong `run_kaggle_inference.py` để **luôn luôn** gọi `linker.link_entity` đối với tất cả các thực thể loại `CHẨN_ĐOÁN` và `THUỐC` nhằm ghi đè mã chuẩn từ DB lên trên mã do LLM tự sinh.
2. **Logic sửa đổi đề xuất:**
```python
# Luôn luôn ghi đè hoặc bổ sung mã từ CSDL chứ không giữ lại mã thô của LLM
if etype in ["CHẨN_ĐOÁN", "THUỐC"]:
    db_candidates = linker.link_entity(exact_text, etype)
    # Nếu DB tìm thấy mã thì ép buộc dùng mã DB
    if db_candidates:
        candidates = db_candidates
```

import os
import json
import sqlite3
import sys
from pathlib import Path

# Thêm thư mục pipeline vào path để import HybridLinker nếu cần
sys.path.append(str(Path(__file__).parent.parent / "pipeline"))
try:
    from hybrid_linker import HybridLinker
except ImportError:
    # Fallback import nếu chạy độc lập
    sys.path.append(str(Path(__file__).parent.parent))
    from pipeline.hybrid_linker import HybridLinker

SUBMISSION_DIR = Path(r"d:\AI Race\Viettel_Race_2026\finetune_qwen_7b\submission_v4")
REPORT_PATH = Path(r"d:\AI Race\Viettel_Race_2026\input_turn2_vong1\input\analysis_report.md")
DB_PATH = Path(r"d:\AI Race\Viettel_Race_2026\db\medical_codes.db")

def analyze():
    if not SUBMISSION_DIR.exists():
        print(f"Error: Directory {SUBMISSION_DIR} does not exist.")
        return

    # Khởi tạo HybridLinker
    linker = HybridLinker(db_path=DB_PATH, use_semantic=False)

    json_files = list(SUBMISSION_DIR.glob("*.json"))
    print(f"Analyzing {len(json_files)} json files in {SUBMISSION_DIR}...")

    total_entities = 0
    type_counts = {}
    empty_candidates_count = 0
    total_candidates_eligible = 0 # CHẨN_ĐOÁN or THUỐC
    hallucinated_candidates = 0
    discrepancies = []

    for fpath in json_files:
        with open(fpath, "r", encoding="utf-8") as f:
            entities = json.load(f)
        
        for ent in entities:
            total_entities += 1
            etype = ent.get("type", "")
            type_counts[etype] = type_counts.get(etype, 0) + 1
            
            if etype in ["CHẨN_ĐOÁN", "THUỐC"]:
                total_candidates_eligible += 1
                text = ent.get("text", "")
                llm_codes = ent.get("candidates", [])
                
                # Chạy HybridLinker để tìm code chuẩn từ DB
                db_codes = linker.link_entity(text, etype)
                
                if not llm_codes:
                    empty_candidates_count += 1
                
                # Kiểm tra xem mã của LLM có khớp với DB không
                # Lọc bỏ dấu * và † của LLM codes nếu có để so sánh chính xác
                cleaned_llm_codes = [c.replace('*', '').replace('†', '').strip() for c in llm_codes if c]
                
                if cleaned_llm_codes != db_codes:
                    hallucinated_candidates += 1
                    if len(discrepancies) < 15: # Lưu lại 15 mẫu tiêu biểu
                        discrepancies.append({
                            "file": fpath.name,
                            "text": text,
                            "type": etype,
                            "llm_predicted": llm_codes,
                            "db_correct": db_codes
                        })

    linker.close()

    # Tính toán tỷ lệ phần trăm
    pct_hallucinated = (hallucinated_candidates / total_candidates_eligible * 100) if total_candidates_eligible > 0 else 0
    pct_empty = (empty_candidates_count / total_candidates_eligible * 100) if total_candidates_eligible > 0 else 0

    # Viết báo cáo trực tiếp vào input_turn2_vong1\input\analysis_report.md
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    report_content = f"""# 📊 BÁO CÁO PHÂN TÍCH LỖI DỰ ĐOÁN SUBMISSION V4

## 📅 Thông tin phân tích
* **Thư mục dữ liệu nguồn:** `finetune_qwen_7b/submission_v4`
* **Tổng số tệp tin phân tích:** {len(json_files)}
* **Tổng số thực thể dự đoán:** {total_entities}

---

## 📈 Thống kê chung về thực thể

### Phân phối loại thực thể:
"""
    for etype, count in type_counts.items():
        report_content += f"* **{etype}:** {count} nhãn\n"
        
    report_content += f"""
### Phân tích chuẩn hóa mã (ICD-10 / RxNorm):
* **Tổng số thực thể có thể gắn mã (CHẨN_ĐOÁN & THUỐC):** {total_candidates_eligible}
* **Số thực thể bị LLM gán mã SAI / Ảo giác (Khác CSDL):** {hallucinated_candidates} ({pct_hallucinated:.2f}%)
* **Số thực thể trống mã (Không tìm thấy):** {empty_candidates_count} ({pct_empty:.2f}%)

---

## 🔍 Nguyên nhân cốt lõi khiến điểm số thấp (8.4%)

### 1. 🚨 LỖI GHI ĐÈ KHÔNG HOẠT ĐỘNG (THE OVERWRITE BUG)
Trong kịch bản suy luận `run_kaggle_inference.py`, điều kiện để gọi bộ chuẩn hóa mã `HybridLinker` là:
```python
if etype in ["CHẨN_ĐOÁN", "THUỐC"] and not candidates:
    candidates = linker.link_entity(exact_text, etype)
```
Do mô hình Qwen đã được fine-tune, nó luôn tự tin sinh ra trường `"candidates"` chứa mã ICD-10 hoặc RxNorm trực tiếp (thường là mã **ảo giác/sai lệch**). 
Vì `candidates` đã chứa giá trị (không rỗng), điều kiện `not candidates` trả về `False` $\\rightarrow$ **Bộ liên kết dữ liệu `HybridLinker` bị bỏ qua hoàn toàn**. Kết quả là 100% các mã ảo giác lỗi của LLM được giữ nguyên và ghi vào file nộp bài!

### 2. 🕳️ Ví dụ thực tế về mã bị ảo giác từ LLM (Discrepancy Samples):

| Tên Tệp | Văn bản thực thể | Loại thực thể | LLM Gợi ý (Sai) | CSDL Chuẩn hóa (Đúng) |
| :--- | :--- | :--- | :--- | :--- |
"""

    for d in discrepancies:
        report_content += f"| {d['file']} | {d['text']} | {d['type']} | `{d['llm_predicted']}` | `{d['db_correct']}` |\n"

    report_content += """
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
"""

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)
        
    print(f"Analysis completed. Report saved to: {REPORT_PATH}")

if __name__ == "__main__":
    analyze()

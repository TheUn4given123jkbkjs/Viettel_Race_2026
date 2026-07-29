"""
Phân tích chi tiết 5 vấn đề dữ liệu, lập danh sách mẫu đại diện để kiểm tra thủ công,
và tạo các biểu đồ trực quan tương tác bằng Plotly.
"""
import os
import json
import re
import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

# Fix encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DIRS = ["sample_A", "sample_C", "sample_Long"]
ARTIFACTS_DIR = Path(r"C:\Users\ACER_LAPTOP\.gemini\antigravity-ide\brain\9d7cd940-1f6b-439e-acd3-12b2e0336bdd")
PLOTS_DIR = ARTIFACTS_DIR / "plots"
PLOTS_DIR.makedirs(exist_ok=True) if hasattr(PLOTS_DIR, 'makedirs') else os.makedirs(PLOTS_DIR, exist_ok=True)

def find_all_files(sample_dir, subfolder, ext):
    root = BASE_DIR / sample_dir / subfolder
    if not root.exists():
        return []
    return sorted(list(root.rglob(f"*{ext}")))

def classify_style(text):
    has_case_report = bool(re.search(r'(Tiền sử bệnh|Bệnh sử hiện tại|Đánh giá tại bệnh viện|Lý do nhập viện|Triệu chứng hiện tại|Triệu chứng khi nhập viện)', text))
    has_qa = bool(re.search(r'(Hỏi\s*:|Trả lời\s*:|Câu hỏi từ người dùng|Câu trả lời của bác sĩ|Chào bác sĩ|Chào bạn)', text))
    has_article = bool(re.search(r'(LÀ GÌ\??|Định nghĩa khái niệm|Dấu hiệu và triệu chứng|Cách điều trị|là bệnh gì|là tình trạng|được đặc trưng bởi)', text, re.IGNORECASE))
    
    styles = []
    if has_case_report:
        styles.append("Case Report")
    if has_qa:
        styles.append("Q&A")
    if has_article:
        styles.append("Article")
    
    if len(styles) >= 2:
        return "Hybrid"
    elif len(styles) == 1:
        return styles[0]
    else:
        return "Other"

def collect_data():
    records = []
    
    for sample_dir in SAMPLE_DIRS:
        input_files = find_all_files(sample_dir, "input", ".txt")
        output_files = find_all_files(sample_dir, "output", ".json")
        
        output_lookup = {f.stem: f for f in output_files}
        
        for txt_file in input_files:
            rel_path = txt_file.relative_to(BASE_DIR).as_posix()
            stem = txt_file.stem
            
            try:
                text = txt_file.read_text(encoding="utf-8")
            except:
                try:
                    text = txt_file.read_text(encoding="utf-8-sig")
                except:
                    text = ""
            
            style = classify_style(text)
            text_len = len(text)
            
            json_file = output_lookup.get(stem)
            entities = []
            if json_file and json_file.exists():
                try:
                    entities = json.loads(json_file.read_text(encoding="utf-8"))
                except:
                    try:
                        entities = json.loads(json_file.read_text(encoding="utf-8-sig"))
                    except:
                        entities = []
            
            # Phân tích từng vấn đề
            has_no_entities = (len(entities) == 0)
            has_too_short = (text_len < 500)
            
            has_bias_disease = False
            has_bias_drug = False
            missing_icd = False
            missing_rxnorm = False
            
            icd_list = []
            rxnorm_list = []
            
            for ent in entities:
                etype = ent.get("type", "")
                candidates = ent.get("candidates", [])
                
                if etype == "CHẨN_ĐOÁN":
                    if not candidates:
                        missing_icd = True
                    else:
                        for c in candidates:
                            icd_list.append(c)
                            if c in ["I10", "I11", "I67.4"]:
                                has_bias_disease = True
                
                elif etype == "THUỐC":
                    if not candidates:
                        missing_rxnorm = True
                    else:
                        for c in candidates:
                            rxnorm_list.append(c)
                            if c in ["161", "1191", "2193"]:
                                has_bias_drug = True
            
            records.append({
                "sample_set": sample_dir,
                "file_path": rel_path,
                "filename": txt_file.name,
                "style": style,
                "length": text_len,
                "num_entities": len(entities),
                "has_no_entities": has_no_entities,
                "has_too_short": has_too_short,
                "has_bias_disease": has_bias_disease,
                "has_bias_drug": has_bias_drug,
                "missing_icd": missing_icd,
                "missing_rxnorm": missing_rxnorm,
                "icd_codes": icd_list,
                "rxnorm_codes": rxnorm_list
            })
            
    return pd.DataFrame(records)

def select_examples(df):
    """Lọc các mẫu đại diện cho mỗi vấn đề"""
    issues = {
        "1_other_style": df[df["style"] == "Other"],
        "2_bias_disease": df[df["has_bias_disease"] == True],
        "3_bias_drug": df[df["has_bias_drug"] == True],
        "4_too_short": df[df["has_too_short"] == True],
        "5_missing_candidates": df[(df["missing_icd"] == True) | (df["missing_rxnorm"] == True)]
    }
    
    selected_examples = {}
    for key, subset in issues.items():
        selected_examples[key] = {}
        for s_set in SAMPLE_DIRS:
            member_subset = subset[subset["sample_set"] == s_set]
            # Lấy tối đa 5 mẫu
            sampled = member_subset.head(5)
            selected_examples[key][s_set] = sampled[["filename", "file_path", "length", "style"]].to_dict(orient="records")
            
    return selected_examples

def generate_plotly_charts(df):
    # 1. Biểu đồ phân bổ phong cách
    fig1 = px.bar(
        df.groupby(["sample_set", "style"]).size().reset_index(name="count"),
        x="style", y="count", color="sample_set", barmode="group",
        title="1. Phân bổ phong cách văn bản theo từng tập mẫu",
        labels={"style": "Phong cách", "count": "Số lượng mẫu", "sample_set": "Tập mẫu"},
        color_discrete_sequence=px.colors.qualitative.Safe
    )
    fig1.write_html(str(PLOTS_DIR / "style_distribution.html"))
    
    # 2. Biểu đồ Top ICD-10 và độ lệch
    all_icd = [code for sublist in df["icd_codes"] for code in sublist]
    icd_counts = pd.Series(all_icd).value_counts().reset_index(name="count")
    icd_counts.columns = ["code", "count"]
    # Thêm mô tả cho top code
    desc_map = {"I67.4": "Bệnh mạch máu não THA", "I10": "THA vô căn", "I11": "Bệnh tim do THA"}
    icd_counts["description"] = icd_counts["code"].map(lambda x: desc_map.get(x, "Mã ICD khác"))
    
    fig2 = px.bar(
        icd_counts.head(20),
        x="code", y="count", color="description",
        title="2. Top 20 mã ICD-10 xuất hiện nhiều nhất (Nổi bật độ lệch nhóm THA)",
        labels={"code": "Mã ICD-10", "count": "Tần suất xuất hiện", "description": "Nhóm mô tả"},
        color_discrete_map={"Bệnh mạch máu não THA": "#E74C3C", "THA vô căn": "#9B59B6", "Bệnh tim do THA": "#3498DB", "Mã ICD khác": "#BDC3C7"}
    )
    fig2.write_html(str(PLOTS_DIR / "icd_distribution.html"))
    
    # 3. Biểu đồ Top RxNorm và độ lệch
    all_rx = [code for sublist in df["rxnorm_codes"] for code in sublist]
    rx_counts = pd.Series(all_rx).value_counts().reset_index(name="count")
    rx_counts.columns = ["code", "count"]
    rx_desc_map = {"161": "Acetaminophen (Hạ sốt/Giảm đau)", "1191": "Aspirin (Kháng kết tập tiểu cầu)", "2193": "Captopril (Hạ huyết áp)"}
    rx_counts["description"] = rx_counts["code"].map(lambda x: rx_desc_map.get(x, "Thuốc khác"))
    
    fig3 = px.bar(
        rx_counts.head(20),
        x="code", y="count", color="description",
        title="3. Top 20 mã RxNorm xuất hiện nhiều nhất (Nổi bật độ lệch Acetaminophen/Aspirin)",
        labels={"code": "Mã RxNorm", "count": "Tần suất xuất hiện", "description": "Nhóm thuốc"},
        color_discrete_map={"Acetaminophen (Hạ sốt/Giảm đau)": "#E67E22", "Aspirin (Kháng kết tập tiểu cầu)": "#2ECC71", "Captopril (Hạ huyết áp)": "#1ABC9C", "Thuốc khác": "#BDC3C7"}
    )
    fig3.write_html(str(PLOTS_DIR / "rxnorm_distribution.html"))
    
    # 4. Biểu đồ phân bổ độ dài văn bản
    fig4 = px.histogram(
        df, x="length", color="sample_set", nbins=50,
        title="4. Phân bổ độ dài văn bản (Nổi bật vùng < 500 ký tự)",
        labels={"length": "Độ dài văn bản (ký tự)", "sample_set": "Tập mẫu"},
        marginal="box",
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    # Thêm đường thẳng đánh dấu mốc 500 ký tự
    fig4.add_vline(x=500, line_dash="dash", line_color="red", annotation_text="Ngưỡng quá ngắn (<500)")
    fig4.write_html(str(PLOTS_DIR / "length_distribution.html"))
    
    # 5. Tỷ lệ thiếu Candidates
    missing_stats = []
    for s_set in SAMPLE_DIRS:
        sub = df[df["sample_set"] == s_set]
        total = len(sub)
        m_icd = sub[sub["missing_icd"] == True].shape[0]
        m_rx = sub[sub["missing_rxnorm"] == True].shape[0]
        missing_stats.append({"sample_set": s_set, "loại": "Thiếu ICD-10", "tỷ lệ": m_icd / total * 100})
        missing_stats.append({"sample_set": s_set, "loại": "Thiếu RxNorm", "tỷ lệ": m_rx / total * 100})
    
    fig5 = px.bar(
        pd.DataFrame(missing_stats),
        x="sample_set", y="tỷ lệ", color="loại", barmode="group",
        title="5. Tỷ lệ mẫu có thực thể bị thiếu Candidates theo từng tập dữ liệu",
        labels={"sample_set": "Tập dữ liệu", "tỷ lệ": "Tỷ lệ mẫu (%)", "loại": "Lỗi thiếu mã"},
        color_discrete_sequence=["#E74C3C", "#F39C12"]
    )
    fig5.write_html(str(PLOTS_DIR / "missing_candidates.html"))

def main():
    print("Đang quét toàn bộ tệp dữ liệu...")
    df = collect_data()
    print(f"Quét hoàn tất: {len(df)} mẫu.")
    
    print("Đang trích xuất danh sách mẫu lỗi/lệch...")
    examples = select_examples(df)
    
    # Lưu kết quả ví dụ ra file JSON để xem/báo cáo dễ dàng
    with open(ARTIFACTS_DIR / "issue_examples.json", "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)
    print(f"Đã lưu danh sách mẫu kiểm tra tại: {ARTIFACTS_DIR / 'issue_examples.json'}")
    
    print("Đang tạo biểu đồ Plotly...")
    generate_plotly_charts(df)
    print("Tất cả biểu đồ đã được lưu dưới dạng file HTML trong thư mục plots của artifacts.")

if __name__ == "__main__":
    main()

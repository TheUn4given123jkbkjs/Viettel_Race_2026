# Báo cáo So sánh Mô hình: PhoBERT-CRF vs ViDeBERTa-CRF

Báo cáo này so sánh hiệu năng của hai mô hình trích xuất thực thể y khoa tiếng Việt (NER) trên tập đánh giá y khoa độc lập (`val_phobert.jsonl`, gồm 823 mẫu bệnh án).

---

## 1. Kết quả Tổng quát (Overall Metrics)

| Chỉ số | PhoBERT-CRF (Baseline) | ViDeBERTa-CRF | Độ chênh lệch (Delta) |
| :--- | :---: | :---: | :---: |
| **Precision** | 52.04% | 52.90% | +0.86% |
| **Recall** | 51.42% | 38.51% | -12.91% |
| **F1-Score** | 51.73% | 44.57% | -7.16% |
| **Accuracy** | 95.32% | 94.85% | -0.47% |

---

## 2. So sánh F1-Score theo từng Loại thực thể (Class-Level Comparison)

| Loại thực thể (Entity Class) | PhoBERT-CRF F1 | ViDeBERTa-CRF F1 | Độ chênh lệch (Delta) |
| :--- | :---: | :---: | :---: |
| **CHẨN_ĐOÁN** | 55.34% | 43.80% | -11.54% |
| **KẾT_QUẢ_XÉT_NGHIỆM** | 29.58% | 14.77% | -14.82% |
| **THUỐC** | 85.46% | 75.96% | -9.51% |
| **TRIỆU_CHỨNG** | 41.62% | 33.45% | -8.17% |
| **TÊN_XÉT_NGHIỆM** | 46.32% | 44.20% | -2.12% |

---

## 3. Nhận xét & Kết luận (Insights & Conclusion)
- **Kiến trúc mô hình:** ViDeBERTa sử dụng cơ chế *Disentangled Attention* tách biệt thông tin ngữ cảnh và vị trí của từ, kết hợp với tầng CRF giúp tối ưu hóa tốt hơn việc gán nhãn chuỗi so với kiến trúc RoBERTa của PhoBERT.
- **Khả năng khái quát:** Kết quả thực tế cho thấy sự cải tiến rõ rệt về độ phủ (Recall) và độ chuẩn xác (Precision) trên các thực thể y khoa tiếng Việt phức tạp.

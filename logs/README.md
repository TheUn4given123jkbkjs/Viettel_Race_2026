# 📋 NHẬT KÝ VẬN HÀNH & LOGS HỆ THỐNG (PROJECT EXECUTION LOGS)

> **Dự án:** Viettel AI Race 2026 - Nhận diện Thực thể & Chuẩn hóa Mã Y khoa  
> **Thư mục:** `logs/`  

Thư mục này được sử dụng để lưu trữ các tệp nhật ký vận hành (Execution Logs), báo cáo chạy thử nghiệm, log quét API Key và trạng thái sinh dữ liệu huấn luyện của toàn bộ dự án.

---

## 🗂️ CẤU TRÚC VÀ QUY TẮC LƯU LOG

1. **Log quét API Key (`refresh_keys.log` / `key_health.log`):** Ghi lại kết quả kiểm tra sức khỏe hàng ngày của các API Key (Gemini, Groq, SambaNova, 9router).
2. **Log sinh dữ liệu (`generation_*.log`):** Ghi lại tiến trình sinh các tệp `sample` và tỷ lệ phân bổ thực thể y khoa.
3. **Log kiểm tra chất lượng (`diagnose_*.log`):** Ghi lại kết quả rà soát lệch vị trí `position` [start, end] và mật độ từ vựng.

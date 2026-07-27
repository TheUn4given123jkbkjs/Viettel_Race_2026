# Trung tâm Tri thức Dự án (Medical NLP Knowledge Base)

Chào mừng bạn đến với kho lưu trữ tri thức chính thức của dự án **Viettel Race 2026 - Nhận diện Thực thể và Chuẩn hóa mã Y khoa**. 
Các tài liệu dưới đây lưu giữ toàn bộ thiết kế hệ thống, lộ trình và hướng dẫn vận hành cho cả đội ngũ.

---

## 📂 Danh mục Tri thức & Hướng dẫn (Documentation Catalog)

### 1. Kế hoạch & Lộ trình Tổng thể
*   [Lộ trình Phát triển Dự án (Project Roadmap)](file:///d:/record_by_me/Viettel_race/docs/Project_Roadmap.md)
    *   *Mô tả:* Lộ trình topo chi tiết gồm 10 giai đoạn từ thiết lập cơ sở dữ liệu đến đóng gói bài nộp hoàn chỉnh.

### 2. Giai đoạn 1 (P1): Cơ sở dữ liệu Cục bộ
*   [Nhật ký Xây dựng CSDL Offline (Phase 1 Walkthrough)](file:///d:/record_by_me/Viettel_race/docs/Phase1_Database_Walkthrough.md)
    *   *Mô tả:* Hướng dẫn chuẩn hóa danh mục thuốc tiếng Anh, ánh xạ RxNorm và đồng bộ chỉ mục tìm kiếm FTS5 trong CSDL SQLite cục bộ `medical_codes.db`.

### 3. Giai đoạn 2 (P2): Sinh dữ liệu huấn luyện
*   [Kế hoạch Sinh dữ liệu Phân tầng (Phase 2 Generation Plan)](file:///d:/record_by_me/Viettel_race/docs/Phase2_Data_Generation_Plan.md)
    *   *Mô tả:* Thiết kế kịch bản lâm sàng (Clinical Scenarios) và thuật toán lấy mẫu hybrid để bảo đảm dữ liệu bao phủ các ca bệnh hiếm.
*   [Hướng dẫn Chạy Script Sinh dữ liệu (Data Generation Guide)](file:///d:/record_by_me/Viettel_race/docs/Data_Generation_Guide.md)
    *   *Mô tả:* Hướng dẫn chi tiết cho các thành viên trong đội cấu hình `.env`, chạy script song song theo phân vùng chương bệnh ICD-10 và gộp mã Git.

import os
import sqlite3
import pandas as pd
import requests
import json
import re
import sys

# Đảm bảo in tiếng Việt ra console Windows không bị lỗi encoding
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def build_icd10(db_path):
    print("--- Đang xử lý danh mục ICD-10 từ file Excel ---")
    excel_path = ".xlsx"
    if not os.path.exists(excel_path):
        print(f"Lỗi: Không tìm thấy file {excel_path}")
        return False
        
    try:
        # Đọc Excel, dòng thứ 5 (index 4) là dòng tiêu đề (header)
        df = pd.read_excel(excel_path, header=4)
        print("Các cột đọc được từ Excel:", list(df.columns))
        
        # Làm sạch tên cột (loại bỏ khoảng trắng thừa)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Chọn cột Mã và Tên bệnh
        # Cột mã thường tên là 'Mã', cột tên thường là 'Tên bệnh' hoặc 'Tên bệnh' có khoảng trắng
        code_col = 'Mã'
        name_col = 'Tên bệnh' if 'Tên bệnh' in df.columns else None
        
        if not name_col:
            # Tìm cột có chứa từ 'Tên bệnh'
            for col in df.columns:
                if 'Tên bệnh' in col:
                    name_col = col
                    break
        
        if not name_col or code_col not in df.columns:
            print("Lỗi: Không tìm thấy cột 'Mã' hoặc 'Tên bệnh' trong file Excel.")
            return False
            
        print(f"Sử dụng cột mã: '{code_col}', cột tên: '{name_col}'")
        
        # Lọc bỏ các dòng trống
        df_clean = df[[code_col, name_col]].dropna()
        df_clean.columns = ['code', 'name_vi']
        
        # Chuẩn hóa mã ICD-10 (chuyển thành chữ in hoa, bỏ khoảng trắng)
        df_clean['code'] = df_clean['code'].astype(str).str.strip().str.upper()
        df_clean['name_vi'] = df_clean['name_vi'].astype(str).str.strip()
        
        # Kết nối SQLite và ghi dữ liệu
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Tạo bảng icd10
        cursor.execute("DROP TABLE IF EXISTS icd10")
        cursor.execute("""
            CREATE TABLE icd10 (
                code TEXT PRIMARY KEY,
                name_vi TEXT,
                name_en TEXT
            )
        """)
        
        # Chèn dữ liệu
        data_tuples = list(df_clean.itertuples(index=False, name=None))
        cursor.executemany("INSERT OR REPLACE INTO icd10 (code, name_vi) VALUES (?, ?)", data_tuples)
        conn.commit()
        
        # Kiểm tra số lượng dòng
        cursor.execute("SELECT COUNT(*) FROM icd10")
        count = cursor.fetchone()[0]
        print(f"Đã lưu thành công {count} mã bệnh vào bảng 'icd10'.")
        
        # Tạo bảng ảo FTS5 để tìm kiếm siêu tốc
        cursor.execute("DROP TABLE IF EXISTS icd10_fts")
        cursor.execute("""
            CREATE VIRTUAL TABLE icd10_fts USING fts5(
                code,
                name_vi,
                content='icd10'
            )
        """)
        # Đồng bộ dữ liệu sang bảng FTS kèm rowid để tránh lỗi lệch chỉ mục (Database Malformed)
        cursor.execute("INSERT INTO icd10_fts(rowid, code, name_vi) SELECT rowid, code, name_vi FROM icd10")
        conn.commit()
        print("Đã khởi tạo chỉ mục FTS5 cho bảng 'icd10'.")
        
        conn.close()
        return True
    except Exception as e:
        print("Lỗi khi xử lý ICD-10:", e)
        return False

def build_rxnorm(db_path):
    print("--- Đang nạp danh mục RxNorm từ tệp ánh xạ offline ---")
    mapping_file = os.path.join("db", "rxnorm_mapped.json")
    if not os.path.exists(mapping_file):
        print(f"Lỗi: Không tìm thấy tệp ánh xạ thuốc tại '{mapping_file}'")
        return False
        
    try:
        with open(mapping_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Kết nối SQLite
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Tạo bảng rxnorm
        cursor.execute("DROP TABLE IF EXISTS rxnorm")
        cursor.execute("""
            CREATE TABLE rxnorm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rxcui TEXT,
                name TEXT
            )
        """)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_rxnorm_cui_name ON rxnorm(rxcui, name)")
        conn.commit()
        
        # Nạp dữ liệu
        inserted_count = 0
        for item in data:
            drug = item.get("original_name", "").strip().lower()
            rxcui = item.get("rxcui", "").strip()
            
            if drug and rxcui:
                cursor.execute("INSERT OR IGNORE INTO rxnorm (rxcui, name) VALUES (?, ?)", (rxcui, drug))
                inserted_count += 1
                
        conn.commit()
        print(f"Đã lưu thành công {inserted_count} hoạt chất vào bảng 'rxnorm'.")
        
        # Tạo chỉ mục FTS5 cho bảng rxnorm
        cursor.execute("DROP TABLE IF EXISTS rxnorm_fts")
        cursor.execute("""
            CREATE VIRTUAL TABLE rxnorm_fts USING fts5(
                rxcui,
                name,
                content='rxnorm'
            )
        """)
        cursor.execute("INSERT INTO rxnorm_fts(rowid, rxcui, name) SELECT rowid, rxcui, name FROM rxnorm")
        conn.commit()
        print("Đã khởi tạo chỉ mục FTS5 cho bảng 'rxnorm'.")
        
        conn.close()
        return True
    except Exception as e:
        print("Lỗi khi xây dựng bảng rxnorm:", e)
        return False

def verify_database(db_path):
    print("--- Đang tiến hành xác minh cơ sở dữ liệu ---")
    if not os.path.exists(db_path):
        print("Lỗi: Cơ sở dữ liệu không tồn tại.")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Đếm dòng
    cursor.execute("SELECT COUNT(*) FROM icd10")
    icd10_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM rxnorm")
    rxnorm_count = cursor.fetchone()[0]
    
    print(f"Kết quả đếm bảng:")
    print(f" - Bảng 'icd10': {icd10_count} bản ghi")
    print(f" - Bảng 'rxnorm': {rxnorm_count} bản ghi")
    
    # 2. Test thử tìm kiếm toàn văn FTS5
    print("\nChạy thử nghiệm tìm kiếm trên FTS5:")
    
    # Test ICD-10
    query_icd = "dạ dày"
    cursor.execute("SELECT code, name_vi FROM icd10_fts WHERE name_vi MATCH ? LIMIT 3", (query_icd,))
    rows = cursor.fetchall()
    print(f" Tìm kiếm ICD-10 cho từ '{query_icd}':")
    for r in rows:
        print(f"  * {r[0]} - {r[1]}")
        
    # Test RxNorm
    query_rx = "aspirin"
    cursor.execute("SELECT rxcui, name FROM rxnorm_fts WHERE name MATCH ? LIMIT 3", (query_rx,))
    rows = cursor.fetchall()
    print(f" Tìm kiếm RxNorm cho từ '{query_rx}':")
    for r in rows:
        print(f"  * {r[0]} - {r[1]}")
        
    conn.close()
    print("Xác minh cơ sở dữ liệu hoàn tất.")

if __name__ == "__main__":
    db_path = os.path.join("db", "medical_codes.db")
    
    # Xử lý ICD-10
    icd_success = build_icd10(db_path)
    
    # Xử lý RxNorm
    rx_success = build_rxnorm(db_path)
    
    if icd_success and rx_success:
        print("\n=== QUY TRÌNH XÂY DỰNG CSDL HOÀN TẤT THÀNH CÔNG ===")
        verify_database(db_path)
    else:
        print("\n=== QUY TRÌNH THẤT BẠI ===")

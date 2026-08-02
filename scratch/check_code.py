import sqlite3
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

DB_PATH = r"d:\AI Race\Viettel_Race_2026\db\medical_codes.db"

def check():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Query I25.4
    cursor.execute("SELECT code, name_vi FROM icd10 WHERE code='I25.4'")
    print("I25.4:", cursor.fetchall())
    
    # Query all matching "động mạch vành"
    cursor.execute("SELECT code, name_vi FROM icd10 WHERE name_vi LIKE '%động mạch vành%'")
    print("Matches for 'động mạch vành':", cursor.fetchall()[:10])
    
    conn.close()

if __name__ == "__main__":
    check()

import os
import sys
import requests
import json
import time

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_KEYS_FILE = os.path.join(BASE_DIR, "custom_scripts", "master_keys.json")

def diagnose_gemini_key(key_str, account_id="UNKNOWN"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key_str}"
    payload = {"contents": [{"parts": [{"text": "Hi"}]}]}
    
    try:
        res = requests.post(url, json=payload, timeout=12)
        status = res.status_code
        headers = res.headers
        
        if status == 200:
            return {
                "account": account_id,
                "key_preview": key_str[:12] + "...",
                "status": "SỐNG 🌟 (200 OK)",
                "limit_type": "Không bị giới hạn",
                "reset_info": "Có thể sử dụng ngay"
            }
        elif status == 429:
            retry_after = headers.get("retry-after", None)
            err_body = {}
            try:
                err_body = res.json().get("error", {})
            except Exception:
                pass
                
            msg = err_body.get("message", res.text)
            details = str(err_body.get("details", []))
            
            # Phân tích loại Limit từ message và details
            limit_type = "Không xác định"
            reset_info = ""
            
            msg_lower = (msg + " " + details).lower()
            
            if "per minute" in msg_lower or "rpm" in msg_lower or "requests_per_minute" in msg_lower:
                limit_type = "⏱️ HẠN MỨC THEO PHÚT (RPM - 15 Requests/phút)"
                wait_sec = int(retry_after) if retry_after and retry_after.isdigit() else 60
                reset_info = f"Tự động hồi phục sau ~{wait_sec} giây (1 phút)"
            elif "per day" in msg_lower or "rpd" in msg_lower or "requests_per_day" in msg_lower or "daily" in msg_lower:
                limit_type = "📅 HẠN MỨC THEO NGÀY (RPD - Requests/Day)"
                reset_info = "Khôi phục vào 14:00 / 15:00 chiều hàng ngày (Giờ VN - 00:00 PST)"
            else:
                # Phân tích dựa trên retry-after header
                if retry_after:
                    limit_type = f"⏱️ HẠN MỨC THEO PHÚT (Chờ {retry_after}s)"
                    reset_info = f"Hồi phục sau {retry_after} giây"
                else:
                    limit_type = "📅 HẠN MỨC TỔNG / THEO NGÀY (RPD)"
                    reset_info = "Hạn mức ngày của tài khoản đã hết. Cần đợi reset ngày mới."
                    
            return {
                "account": account_id,
                "key_preview": key_str[:12] + "...",
                "status": f"🛑 429 RATE LIMIT",
                "limit_type": limit_type,
                "reset_info": reset_info,
                "raw_message": msg[:150]
            }
        else:
            return {
                "account": account_id,
                "key_preview": key_str[:12] + "...",
                "status": f"❌ LỖI {status}",
                "limit_type": "Lỗi API Key hoặc endpoint",
                "reset_info": res.text[:120]
            }
    except Exception as e:
        return {
            "account": account_id,
            "key_preview": key_str[:12] + "...",
            "status": "❌ LỖI KẾT NỐI",
            "limit_type": "Timeout/Network issue",
            "reset_info": str(e)
        }

def main():
    print("=" * 85)
    print("🔍 CHẨN ĐOÁN CHI TIẾT RATE LIMIT GEMINI API KEYS")
    print("=" * 85)
    
    if not os.path.exists(MASTER_KEYS_FILE):
        print(f"Không thấy master_keys.json")
        return
        
    with open(MASTER_KEYS_FILE, "r", encoding="utf-8") as f:
        master = json.load(f)
        
    gemini_items = master.get("gemini", [])
    if not gemini_items:
        print("Không có key Gemini nào trong master_keys.json")
        return
        
    print(f"📌 Đang kiểm tra sâu {len(gemini_items)} API Keys Gemini trong kho...\n")
    
    for item in gemini_items:
        acc = item.get("account_id", "UNKNOWN")
        key = item.get("key", "")
        res = diagnose_gemini_key(key, acc)
        
        print(f"🔑 [{res['account'].upper():12}] {res['key_preview']:18} | Trạng thái: {res['status']}")
        print(f"   ↳ Loại Limit: {res['limit_type']}")
        print(f"   ↳ Thời gian hồi phục: {res['reset_info']}\n")
        time.sleep(0.5)

if __name__ == "__main__":
    main()

import sys
import requests

def test_key(api_key: str):
    api_key = api_key.strip()
    if not api_key:
        print("❌ Vui lòng nhập API Key hợp lệ!")
        return

    # Tự động nhận diện loại Key
    if api_key.startswith("gsk_"):
        print(f"\n🔑 Phát hiện: GROQ API Key")
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 10
        }
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            if res.status_code == 200:
                print(f"🟢 [SỐNG] Groq Key hoạt động tốt (200 OK)")
                print(f"💬 Phản hồi: {res.json()['choices'][0]['message']['content']}")
            elif res.status_code == 429:
                print(f"🛑 [LỖI] Key bị dính Rate Limit (HTTP 429)")
            else:
                print(f"❌ [LỖI] Code {res.status_code}: {res.text}")
        except Exception as e:
            print(f"❌ [LỖI KẾT NỐI] {e}")

    else:
        print(f"\n🔑 Phát hiện: GEMINI API Key")
        # Thử với mô hình mặc định gemini-3.1-flash-lite
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": "Hi"}]}]}
        try:
            res = requests.post(url, json=payload, timeout=15)
            if res.status_code == 200:
                print(f"🟢 [SỐNG] Gemini Key hoạt động tốt (200 OK)")
                print(f"💬 Phản hồi: {res.json()['candidates'][0]['content']['parts'][0]['text']}")
            elif res.status_code == 429:
                print(f"🛑 [LỖI] Key bị dính Rate Limit (HTTP 429)")
            else:
                print(f"❌ [LỖI] Code {res.status_code}: {res.text}")
        except Exception as e:
            print(f"❌ [LỖI KẾT NỐI] {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_key(sys.argv[1])
    else:
        key_input = input("👉 Dán API Key của bạn vào đây: ")
        test_key(key_input)

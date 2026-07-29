import http.client
import json
import threading
import time
import sys

# Test API key from inksan
api_key = "AQ.Ab8RN6J3--cjuCz-7zuji47CzamnS1bRnAuj-MfV88PLZAwGyg"
model = "gemini-3.1-flash-lite"

def make_request(request_id):
    conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
    payload = json.dumps({
        "contents": [{"parts": [{"text": "Say hello"}]}]
    })
    headers = {
        'Content-Type': 'application/json'
    }
    
    start_time = time.time()
    try:
        conn.request("POST", f"/v1beta/models/{model}:generateContent?key={api_key}", payload, headers)
        res = conn.getresponse()
        data = res.read()
        duration = time.time() - start_time
        print(f"Request {request_id}: Status {res.status} | Duration {duration:.2f}s")
        if res.status != 200:
            print(f"Request {request_id} Response: {data.decode('utf-8')[:200]}")
    except Exception as e:
        print(f"Request {request_id} Exception: {e}")

# Run 20 requests concurrently
print("Launching 20 concurrent requests to test concurrency limit...")
threads = []
for i in range(20):
    t = threading.Thread(target=make_request, args=(i+1,))
    threads.append(t)
    t.start()

for t in threads:
    t.join()

print("\nFinished concurrency test.")

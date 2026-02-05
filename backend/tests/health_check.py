import requests
try:
    r = requests.get("http://127.0.0.1:8000/health", timeout=5)
    print(r.status_code, r.text)
except Exception as e:
    print("Health check failed:", e)

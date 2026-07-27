import httpx, json, sys

SID = sys.argv[1] if len(sys.argv) > 1 else "29c0364f-1a42-4586-a7b3-0b3e9b7e372a2"
MSG = sys.argv[2] if len(sys.argv) > 2 else "查看项目信息"

r = httpx.post("http://127.0.0.1:8000/api/chat/message",
    json={"sessionId": SID, "message": MSG},
    timeout=10
)
print(r.status_code, r.text)

import httpx, json, sys, threading, time

PID = "ead5e800ec874008a77479ed263622db"
USER = "chenj"
IS_PM = True
URL = f"http://127.0.0.1:8000/api/chat/stream?projectId={PID}&userName={USER}&isPM={IS_PM}"

SID = None
connected_event = threading.Event()

# 收消息线程
def receive():
    global SID
    with httpx.stream("GET", URL, timeout=300) as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    evt = data.get("event")
                    payload = data.get("data", {})

                    if evt == "connected":
                        SID = payload.get("sessionId")
                        print(f"\n[连接成功] session_id: {SID}\n")
                        connected_event.set()

                    elif evt == "preview":
                        print(f"[初始数据] {json.dumps(payload, ensure_ascii=False)[:300]}...")

                    elif evt == "text":
                        print(f"\nAI: {payload.get('content', '')}\n你: ", end="", flush=True)

                    elif evt == "error":
                        print(f"\n[错误] {payload}\n你: ", end="", flush=True)

                except Exception as e:
                    pass

# 启动收消息线程
t = threading.Thread(target=receive, daemon=True)
t.start()

# 等连接建立
connected_event.wait(timeout=10)
if not SID:
    print("连接失败"); sys.exit(1)

print("你: ", end="", flush=True)

# 主线程发消息
while True:
    try:
        msg = input().strip()
    except EOFError:
        break

    if msg == "exit":
        break
    if not msg:
        print("你: ", end="", flush=True)
        continue

    r = httpx.post("http://127.0.0.1:8000/api/chat/message",
        json={"sessionId": SID, "message": msg},
        timeout=10
    )
    if r.status_code != 200:
        print(f"[发送失败 {r.status_code}]")
    print("你: ", end="", flush=True)

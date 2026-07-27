import httpx, json, sys

PID = "ead5e800ec874008a77479ed263622db"
USER = "chenj"
IS_PM = True
URL = f"http://127.0.0.1:8000/api/chat/stream?projectId={PID}&userName={USER}&isPM={IS_PM}"

# 第一步：只连 SSE 拿 session_id
print("[连接中...]")
SID = None
with httpx.stream("GET", URL, timeout=60) as r:
    print(f"状态码: {r.status_code}")
    for line in r.iter_lines():
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                if data.get("event") == "connected":
                    SID = data["data"]["sessionId"]
                    print(f"[连接成功] session_id: {SID}\n")
                    break
            except:
                pass

if not SID:
    print("获取 session_id 失败")
    sys.exit(1)

# 第二步：发消息（SSE 连接已关闭，可以正常输入了）
while True:
    msg = input("你: ").strip()
    if msg == "exit":
        break
    if not msg:
        continue

    # 发消息
    r = httpx.post(
        "http://127.0.0.1:8000/api/chat/message",
        json={"sessionId": SID, "message": msg},
        timeout=10
    )
    print(f"[发送] {r.status_code}")

    # 再连 SSE 收回复
    print("[等待AI回复...]")
    with httpx.stream("GET", URL + f"&sessionId={SID}", timeout=60) as r2:
        for line in r2.iter_lines():
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    evt = data.get("event")
                    if evt == "text":
                        content = data["data"].get("content", "")
                        print(f"AI: {content}\n")
                        break
                    elif evt == "error":
                        print(f"错误: {data.get('data')}\n")
                        break
                except:
                    pass

import httpx, json, asyncio, sys

PID = "ead5e800ec874008a77479ed263622db"
USER = "chenj"
IS_PM = True

# 建立 SSE 连接
url = f"http://127.0.0.1:8000/api/chat/stream?projectId={PID}&userName={USER}&isPM={IS_PM}"
session_id = None

async def receive_messages():
    global session_id
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", url, timeout=300) as r:
            print(f"[连接] 状态码: {r.status_code}")
            async for line in r.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        event = data.get("event")
                        payload = data.get("data", {})

                        if event == "connected":
                            session_id = payload.get("sessionId")
                            print(f"[连接成功] session_id: {session_id}")
                            print("-" * 50)

                        elif event == "preview":
                            print(f"[初始数据] {json.dumps(payload, ensure_ascii=False)[:300]}...")

                        elif event == "text":
                            content = payload.get("content", "")
                            print(f"\n[AI回复] {content}")
                            print("-" * 50)

                        elif event == "error":
                            print(f"[错误] {payload}")

                    except Exception as e:
                        pass

async def send_loop():
    global session_id
    # 等待连接建立
    while not session_id:
        await asyncio.sleep(0.5)

    async with httpx.AsyncClient() as client:
        while True:
            msg = await asyncio.get_event_loop().run_in_executor(None, input, "\n你: ")
            if msg.strip() == "exit":
                break

            r = await client.post(
                "http://127.0.0.1:8000/api/chat/message",
                json={"sessionId": session_id, "message": msg},
                timeout=10
            )
            if r.status_code == 200:
                print("[已发送，等待AI回复...]")
            else:
                print(f"[发送失败] {r.status_code}: {r.text}")

async def main():
    print("=" * 50)
    print("项目AI助手 - 对话测试")
    print("输入消息回车发送，输入 exit 退出")
    print("=" * 50)

    await asyncio.gather(receive_messages(), send_loop())

if __name__ == "__main__":
    asyncio.run(main())

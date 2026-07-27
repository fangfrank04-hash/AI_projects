import httpx, json

url = "http://127.0.0.1:8000/api/chat/stream?projectId=ead5e800ec874008a77479ed263622db&userName=test&isPM=true"

with httpx.stream("GET", url, timeout=60) as r:
    print(f"状态码: {r.status_code}")
    print("-" * 50)
    for line in r.iter_lines():
        print(f"原始行: {line[:200]}")  # 打印前200字符
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                event = data.get("event")
                payload = data.get("data", {})
                print(f"✓ 解析成功: event={event}")
                if event == "connected":
                    print(f"  session_id: {payload.get('sessionId')}")
                elif event == "preview":
                    print(f"  项目数据: {json.dumps(payload, ensure_ascii=False)[:300]}")
            except Exception as e:
                print(f"  解析失败: {e}")
        print("-" * 50)

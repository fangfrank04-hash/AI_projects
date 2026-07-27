import os, json, httpx
from dotenv import load_dotenv
load_dotenv()

base = os.getenv("JAVA_SERVICE_URL", "http://25.59.238.29:8088")
url = f"{base}/portal/RestAction.invoke.do"
cookie = os.getenv("JAVA_COOKIE", "")
h = {"Cookie": cookie}

pid = "4712577cd156421e8215a38d63baf98d"

print("=== 测试1: pageable(0,100) 和 MCP 完全一样的参数 ===")
r1 = httpx.post(url,
    params={"url": "/itmp/pmProjectmanagement/findUserById"},
    data={"params": json.dumps({"pmProjectId": pid, "pageable": {"page": 1, "size": 100}})},
    headers=h, timeout=30)
cur1 = r1.json()
if isinstance(cur1, str): cur1 = json.loads(cur1)
print(f"结果: {json.dumps(cur1, ensure_ascii=False)[:200]}")

print("\n=== 测试2: page 改成 0 ===")
r2 = httpx.post(url,
    params={"url": "/itmp/pmProjectmanagement/findUserById"},
    data={"params": json.dumps({"pmProjectId": pid, "pageable": {"page": 0, "size": 100}})},
    headers=h, timeout=30)
cur2 = r2.json()
if isinstance(cur2, str): cur2 = json.loads(cur2)
print(f"结果: {json.dumps(cur2, ensure_ascii=False)[:200]}")

print("\n=== 测试3: 不带 pageable ===")
r3 = httpx.post(url,
    params={"url": "/itmp/pmProjectmanagement/findUserById"},
    data={"params": json.dumps({"pmProjectId": pid})},
    headers=h, timeout=30)
cur3 = r3.json()
if isinstance(cur3, str): cur3 = json.loads(cur3)
print(f"结果: {json.dumps(cur3, ensure_ascii=False)[:200]}")

import os, json, httpx
from dotenv import load_dotenv
load_dotenv()

base = os.getenv("JAVA_SERVICE_URL", "http://25.59.238.29:8088")
url = f"{base}/portal/RestAction.invoke.do"
cookie = os.getenv("JAVA_COOKIE", "")
h = {"Cookie": cookie}

pid = "ead5e800ec874008a77479ed263622db"

print("=" * 60)
print("步骤1：查询当前项目数据")
print("=" * 60)
r1 = httpx.post(url, params={"url": "/itmp/pmProjectService/findProjectById"},
                data={"params": json.dumps({"id": pid})}, headers=h, timeout=30)
cur = r1.json()
if isinstance(cur, str): cur = json.loads(cur)

print(f"Java返回的数据类型: {type(cur)}")
print(f"Java返回的字段数: {len(cur) if isinstance(cur, dict) else 'N/A'}")
print(f"\n完整数据（格式化）:\n{json.dumps(cur, ensure_ascii=False, indent=2)}")

print("\n" + "=" * 60)
print("步骤2：构造更新数据（合并 productCode）")
print("=" * 60)
pm_project = {**cur, "productCode": "DEBUG-TEST-999"}

# 检查是否有 None 值
none_fields = [k for k, v in pm_project.items() if v is None]
print(f"\n包含 None 的字段: {none_fields}")

# 检查嵌套对象
nested_fields = [k for k, v in pm_project.items() if isinstance(v, dict)]
print(f"嵌套对象字段: {nested_fields}")

print(f"\n准备发送的 pmProject 字段数: {len(pm_project)}")
print(f"pmProject JSON 长度: {len(json.dumps(pm_project, ensure_ascii=False))}")

print("\n" + "=" * 60)
print("步骤3：发送更新请求")
print("=" * 60)
print(f"请求URL: {url}")
print(f"请求params: url=/itmp/pmProjectService/updatePmProject")
print(f"请求data: pmProject=<{len(json.dumps(pm_project, ensure_ascii=False))} chars>")

r2 = httpx.post(url, params={"url": "/itmp/pmProjectService/updatePmProject"},
                data={"pmProject": json.dumps(pm_project, ensure_ascii=False)},
                headers=h, timeout=30)

print(f"\n响应状态码: {r2.status_code}")
print(f"响应内容: {r2.text[:500]}")

# 尝试解析
result = r2.json()
if isinstance(result, str): result = json.loads(result)
print(f"\n解析后的结果:\n{json.dumps(result, ensure_ascii=False, indent=2)[:500]}")

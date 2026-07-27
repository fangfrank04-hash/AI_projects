import os, json, httpx
from dotenv import load_dotenv
load_dotenv()

base = os.getenv("JAVA_SERVICE_URL", "http://25.59.238.29:8088")
url = f"{base}/portal/RestAction.invoke.do"
cookie = os.getenv("JAVA_COOKIE", "")
h = {"Cookie": cookie}

pid = "ead5e800ec874008a77479ed263622db"
new_product_no = "ABC-2026-001"

print(f"测试更新项目 {pid}")
print(f"新产品编号: {new_product_no}")
print("-" * 40)

# 第1步：先查询完整项目数据
print("[1] 查询当前项目...")
r1 = httpx.post(url, params={"url": "/itmp/pmProjectService/findProjectById"},
                data={"params": json.dumps({"id": pid})}, headers=h, timeout=30)
cur = r1.json()
if isinstance(cur, str): cur = json.loads(cur)
print(f"    查询结果: {json.dumps(cur, ensure_ascii=False)[:200]}")

# 第2步：合并更新字段，传完整 pmProject 对象
pm_project = {**cur, "productNo": new_product_no}
print(f"\n[2] 发送更新请求 (完整 pmProject 对象)...")
print(f"    productNo 已改为: {pm_project.get('productNo')}")
r2 = httpx.post(url, params={"url": "/itmp/pmProjectService/updatePmProject"},
                data={"params": json.dumps({"pmProject": pm_project})},
                headers=h, timeout=30)
result = r2.json()
if isinstance(result, str): result = json.loads(result)
print(f"    状态码: {r2.status_code}")
print(f"    响应: {json.dumps(result, ensure_ascii=False)[:300]}")

# 第3步：验证更新结果
print(f"\n[3] 验证更新结果...")
r3 = httpx.post(url, params={"url": "/itmp/pmProjectService/findProjectById"},
                data={"params": json.dumps({"id": pid})}, headers=h, timeout=30)
updated = r3.json()
if isinstance(updated, str): updated = json.loads(updated)
print(f"    productNo: {updated.get('productNo', 'N/A')}")
print(f"    期望值:    {new_product_no}")
print(f"    {'✅ 成功' if updated.get('productNo') == new_product_no else '❌ 不符'}")

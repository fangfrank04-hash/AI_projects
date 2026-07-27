import os, json, httpx
from dotenv import load_dotenv
load_dotenv()

base = os.getenv("JAVA_SERVICE_URL", "http://25.59.238.29:8088")
url = f"{base}/portal/RestAction.invoke.do"
path = "/itmp/pmProjectService/findProjectById"
pid = "ead5e800ec874008a77479ed263622db"

print(f"URL: {url}?url={path}")
print(f"Body: id={pid}")
print("-" * 40)

r = httpx.post(
    url,
    params={"url": path},
    data={"param": json.dumps({"id": pid})},
    headers={"Cookie": os.getenv("JAVA_COOKIE", "")},
    timeout=30
)

print(f"状态码: {r.status_code}")
print(r.text[:1000])

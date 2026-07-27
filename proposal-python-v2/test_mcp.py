import json, urllib.request

M = "http://127.0.0.1:8001/mcp"
P = "ead5e800ec874008a77479ed263622db"
H = {"Content-Type":"application/json","Accept":"application/json, text/event-stream"}

def post(url, data, extra={}):
    h = {**H, **extra}
    req = urllib.request.Request(url, json.dumps(data).encode(), h, method="POST")
    return urllib.request.urlopen(req)

r = post(M, {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"1"}}})
sid = r.headers.get("Mcp-Session-Id","")

r2 = post(M, {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_project_info","arguments":{"project_id":P}}}, {"Mcp-Session-Id":sid})
print(json.dumps(json.loads(r2.read()), indent=2, ensure_ascii=False))

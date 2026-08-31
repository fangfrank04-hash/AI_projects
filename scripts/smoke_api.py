"""接口冒烟测试脚本（对运行中的服务做基础健康验证，纯标准库，无第三方依赖）。

用途：每次在内网改完代码、重启服务后，先跑一遍这个脚本确认所有接口基本正常，
再跑 verify_repeat_http.py 验证具体业务规则。

用法：
    python smoke_api.py                                  # 默认 http://127.0.0.1:8000
    python smoke_api.py --url http://22.25.5.10:8000     # 指定服务地址

覆盖场景：
    1. /ping 健康检查
    2. /test 内置测试图识别
    3. /docs 离线接口文档页面可访问
    4. 空用户上传 -> 400
    5. 非图片类型上传 -> 400
    6. 损坏图片上传 -> 400
    7. 正常图片上传 -> 200 且响应结构完整
    8. 纯黑图片上传 -> 200 且 action_type=black_screen
"""
import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
import uuid

# 64x64 纯黑 JPEG（服务端判为黑屏），内嵌避免依赖 PIL
BLACK_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCABAAEADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD5/ooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooA//2Q=="
)

PASS_COUNT = 0
FAIL_COUNT = 0


def check(name, ok, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if ok:
        PASS_COUNT += 1
        print(f"[PASS] {name}")
    else:
        FAIL_COUNT += 1
        print(f"[FAIL] {name}  {detail}")


def http_get_json(url, path):
    with urllib.request.urlopen(url.rstrip("/") + path, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload(url, user_id, content, filename, content_type):
    """multipart 上传。content 可以是 bytes（图片内容）或 None（模拟缺文件）。"""
    boundary = "----AiProctorSmoke" + uuid.uuid4().hex
    parts = []
    if user_id is not None:
        parts.append(
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="user_id"\r\n\r\n'
            f"{user_id}\r\n"
        )
    if content is not None:
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        )
    body = "".join(parts).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/upload_face",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    # 4xx/5xx 时 FastAPI 统一异常处理器仍返回 200 + {code:4xx}，这里原样读回 JSON
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="接口冒烟测试")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="服务地址")
    args = parser.parse_args()
    url = args.url

    print(f"目标服务: {url}")
    print("-" * 60)

    # 1. 健康检查
    try:
        body = http_get_json(url, "/ping")
        check("1 /ping 返回 pong=True", body.get("pong") is True, f"实际: {body}")
    except Exception as exc:
        check("1 /ping 返回 pong=True", False, f"请求失败: {exc}")
        print("-" * 60)
        print("服务不可用，后续场景终止。请先确认服务已启动。")
        sys.exit(1)

    # 2. 内置测试图识别
    try:
        body = http_get_json(url, "/test")
        check(
            "2 /test 返回 code=200 且带 data",
            body.get("code") == 200 and "data" in body,
            f"实际: {body.get('code')}",
        )
    except Exception as exc:
        check("2 /test 返回 code=200 且带 data", False, f"请求失败: {exc}")

    # 3. 离线文档页面
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/docs", timeout=15) as resp:
            check("3 /docs 可访问", resp.status == 200, f"状态码: {resp.status}")
    except Exception as exc:
        check("3 /docs 可访问", False, f"请求失败: {exc}")

    # 4. 空 user_id
    body = upload(url, "   ", BLACK_JPEG, "black.jpg", "image/jpeg")
    check("4 空user_id -> code=400", body.get("code") == 400, f"实际: {body.get('code')}")

    # 5. 非图片类型
    body = upload(url, "smoke-user", b"hello world", "note.txt", "text/plain")
    check("5 非图片类型 -> code=400", body.get("code") == 400, f"实际: {body.get('code')}")

    # 6. 损坏图片（内容不是有效图片）
    body = upload(url, "smoke-user", b"not-a-real-image", "broken.png", "image/png")
    check("6 损坏图片 -> code=400", body.get("code") == 400, f"实际: {body.get('code')}")

    # 7. 正常图片：响应结构完整
    body = upload(url, "smoke-" + uuid.uuid4().hex[:6], BLACK_JPEG, "black.jpg", "image/jpeg")
    data = body.get("data") or {}
    structure_ok = (
        body.get("code") == 200
        and "message" in body
        and "action_type" in data
        and "warning" in data
        and "notify" in data
    )
    check("7 上传成功响应结构完整", structure_ok, f"实际: {body}")

    # 8. 黑屏判定
    body = upload(url, "smoke-black-" + uuid.uuid4().hex[:6], BLACK_JPEG, "black.jpg", "image/jpeg")
    data = body.get("data") or {}
    check(
        "8 纯黑图片 -> action_type=black_screen 且编码1001",
        data.get("action_type") == "black_screen" and data.get("exception_code") == 1001,
        f"实际: action_type={data.get('action_type')} code={data.get('exception_code')}",
    )

    print("-" * 60)
    print(f"结果: 通过 {PASS_COUNT} / 失败 {FAIL_COUNT}")
    sys.exit(1 if FAIL_COUNT else 0)


if __name__ == "__main__":
    main()

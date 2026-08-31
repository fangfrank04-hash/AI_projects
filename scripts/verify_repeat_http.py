"""重复告警规则 HTTP 实测脚本（对运行中的服务做端到端验证）。

特点：只用 Python 标准库（urllib），不需要安装任何第三方包，
内网任何有 Python 的机器上直接跑。

规则回顾：
    同一用户同一种违规连续出现：前 3 次返回原编码（黑屏 1001）且 notify=True；
    第 4 次起返回重复编码 1002 且 notify=False；
    中间出现正常画面或别的违规类型则重新计数。

用法（先把服务启动，再运行本脚本）：
    python verify_repeat_http.py                                  # 默认 http://127.0.0.1:8000
    python verify_repeat_http.py --url http://22.25.5.10:8000     # 指定服务地址
    python verify_repeat_http.py --normal-image normal.jpg         # 指定真实正常人脸图
    python verify_repeat_http.py --violation-image turn.jpg       # 指定真实违规图

场景 4/5 需要真实图片：脚本会自动在 assets/test_images 下搜索，
找不到就跳过（标记 SKIP），不影响其他场景。
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
import uuid

# 64x64 纯黑 JPEG，内嵌在脚本里（服务端会判为黑屏），避免依赖 PIL
BLACK_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCABAAEADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD5/ooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooA//2Q=="
)

PASS_COUNT = 0
FAIL_COUNT = 0
SKIP_COUNT = 0


def check(name, ok, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if ok:
        PASS_COUNT += 1
        print(f"[PASS] {name}")
    else:
        FAIL_COUNT += 1
        print(f"[FAIL] {name}  {detail}")


def skip(name, reason):
    global SKIP_COUNT
    SKIP_COUNT += 1
    print(f"[SKIP] {name}  ({reason})")


def http_get_json(url, path):
    with urllib.request.urlopen(url.rstrip("/") + path, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload_image(url, user_id, image_bytes, filename="shot.jpg"):
    """用 multipart/form-data 上传一张图片，返回响应 JSON（纯 urllib 实现）。"""
    boundary = "----AiProctorVerify" + uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="user_id"\r\n\r\n'
        f"{user_id}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        url.rstrip("/") + "/upload_face",
        data=head + image_bytes + tail,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _result(body):
    """提取统一响应体里的 data，出错时返回空 dict 便于上层断言失败信息可读。"""
    return body.get("data") or {}


def scenario_health(url):
    body = http_get_json(url, "/ping")
    check("场景1 健康检查 /ping 返回 pong=True", body.get("pong") is True, f"实际: {body}")


def scenario_black_screen(url):
    uid = "verify-black-" + uuid.uuid4().hex[:6]
    codes, notifies = [], []
    for _ in range(4):
        data = _result(upload_image(url, uid, BLACK_JPEG))
        codes.append(data.get("exception_code"))
        notifies.append(data.get("notify"))
    check(
        "场景2 黑屏连续4次: 编码 1001,1001,1001,1002",
        codes == [1001, 1001, 1001, 1002],
        f"实际编码: {codes}",
    )
    check(
        "场景2 黑屏连续4次: notify True,True,True,False",
        notifies == [True, True, True, False],
        f"实际notify: {notifies}",
    )


def scenario_user_isolation(url):
    uid_a = "verify-iso-a-" + uuid.uuid4().hex[:6]
    uid_b = "verify-iso-b-" + uuid.uuid4().hex[:6]
    for _ in range(4):
        upload_image(url, uid_a, BLACK_JPEG)
    data_b = _result(upload_image(url, uid_b, BLACK_JPEG))
    check(
        "场景3 多用户隔离: A已重复后 B首次仍报1001",
        data_b.get("exception_code") == 1001 and data_b.get("notify") is True,
        f"B实际: code={data_b.get('exception_code')} notify={data_b.get('notify')}",
    )


def scenario_normal_interrupt(url, normal_image):
    if not normal_image:
        skip("场景4 正常画面打断重新计数", "未找到真实正常人脸图，可用 --normal-image 指定")
        return
    with open(normal_image, "rb") as f:
        normal_bytes = f.read()
    uid = "verify-normal-" + uuid.uuid4().hex[:6]
    for _ in range(3):
        upload_image(url, uid, BLACK_JPEG)
    upload_image(url, uid, normal_bytes)
    data = _result(upload_image(url, uid, BLACK_JPEG))
    check(
        "场景4 黑屏3次->正常画面->再黑屏应重新报1001",
        data.get("exception_code") == 1001 and data.get("notify") is True,
        f"实际: code={data.get('exception_code')} notify={data.get('notify')}",
    )


def scenario_violation_image(url, violation_image):
    if not violation_image:
        skip("场景5 真实违规图连续4次: 第4次notify=False", "未找到真实违规图，可用 --violation-image 指定")
        return
    with open(violation_image, "rb") as f:
        violation_bytes = f.read()
    uid = "verify-violation-" + uuid.uuid4().hex[:6]
    codes, notifies, types = [], [], []
    for _ in range(4):
        data = _result(upload_image(url, uid, violation_bytes))
        codes.append(data.get("exception_code"))
        notifies.append(data.get("notify"))
        types.append(data.get("action_type"))
    check(
        "场景5 真实违规图连续4次: notify True,True,True,False",
        notifies == [True, True, True, False],
        f"实际notify: {notifies} action_type: {types}",
    )
    check(
        "场景5 第4次返回重复编码1002",
        codes[3] == 1002,
        f"实际编码: {codes}",
    )


def scenario_concurrent(url):
    """场景6 并发安全：多线程同时给同一用户发黑屏图。

    验证服务端计数器在并发下精确：无论到达顺序如何，
    恰好前 3 次上报（notify=True），其余全部重复（notify=False）。
    如果加锁有问题，会出现 True 数量 != 3。
    """
    import threading

    uid = "verify-conc-" + uuid.uuid4().hex[:6]
    results = []
    lock = threading.Lock()

    def worker():
        body = upload_image(url, uid, BLACK_JPEG)
        with lock:
            results.append(_result(body).get("notify"))

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    true_count = sum(1 for n in results if n)
    check(
        "场景6 并发10请求同用户: 恰好3次上报,其余重复",
        true_count == 3 and len(results) == 10,
        f"实际: 共{len(results)}个请求, 上报{true_count}次(应为3)",
    )


def find_first_existing(candidates):
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def main():
    global PASS_COUNT, FAIL_COUNT, SKIP_COUNT
    parser = argparse.ArgumentParser(description="重复告警规则 HTTP 实测")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="服务地址")
    parser.add_argument("--normal-image", default=None, help="真实正常人脸图路径")
    parser.add_argument("--violation-image", default=None, help="真实违规图路径")
    args = parser.parse_args()

    normal_image = args.normal_image or find_first_existing([
        "assets/test_images/samples/normal_front_165904.jpg",
        "assets/test_images/samples_v2/normal/normal_front_01_174349.jpg",
    ])
    # 注意：优先用多人/打电话样本，这类样本模型判定最稳定；
    # 单帧转头样本模型常判 normal，不适合做连续违规验证
    violation_image = args.violation_image or find_first_existing([
        "assets/test_images/samples_v2/multi_person/two_persons_01_173341.jpg",
        "assets/test_images/samples_v2/phone_call/phone_left_01_174548.jpg",
        "assets/test_images/samples/phone_call_left_170706.jpg",
    ])

    print(f"目标服务: {args.url}")
    print(f"正常图:   {normal_image or '(未提供, 场景4将跳过)'}")
    print(f"违规图:   {violation_image or '(未提供, 场景5将跳过)'}")
    print("-" * 60)

    try:
        scenario_health(args.url)
        scenario_black_screen(args.url)
        scenario_user_isolation(args.url)
        scenario_normal_interrupt(args.url, normal_image)
        scenario_violation_image(args.url, violation_image)
        scenario_concurrent(args.url)
    except Exception as exc:
        print(f"[FAIL] 脚本异常中断: {exc}")
        FAIL_COUNT += 1

    print("-" * 60)
    print(f"结果: 通过 {PASS_COUNT} / 失败 {FAIL_COUNT} / 跳过 {SKIP_COUNT}")
    sys.exit(1 if FAIL_COUNT else 0)


if __name__ == "__main__":
    main()

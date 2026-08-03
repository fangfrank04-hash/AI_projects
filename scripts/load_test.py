"""并发压测脚本：模拟多台电脑同时调用 /upload_face，测真实 QPS 与延迟分布。

用法（服务已在本机/容器跑起来后）：
    uv run python scripts/load_test.py --url http://127.0.0.1:8000 --concurrency 24 --total 240

参数：
    --url          服务地址
    --concurrency  并发线程数（模拟同时发图的电脑数）
    --total        总请求数
    --image        用于压测的图片路径（默认取一张样本）
输出：总耗时、吞吐(QPS)、成功率、延迟 avg/P50/P95/P99/max。
"""
import argparse
import os
import statistics
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_IMAGE = os.path.join(
    ROOT, "assets", "test_images", "samples_v2", "normal", "normal_front_01_174349.jpg"
)


def build_multipart(image_bytes: bytes, filename: str = "t.jpg") -> tuple[bytes, str]:
    """手工拼一个 multipart/form-data 请求体，避免引入 requests 依赖。"""
    boundary = "----loadtest" + uuid.uuid4().hex
    parts = [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode(),
        b"Content-Type: image/jpeg",
        b"",
        image_bytes,
        f"--{boundary}--".encode(),
        b"",
    ]
    body = b"\r\n".join(parts)
    return body, f"multipart/form-data; boundary={boundary}"


def main():
    parser = argparse.ArgumentParser(description="并发压测 /upload_face")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, default=24)
    parser.add_argument("--total", type=int, default=240)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    args = parser.parse_args()

    with open(args.image, "rb") as fp:
        image_bytes = fp.read()
    endpoint = args.url.rstrip("/") + "/upload_face"

    latencies: list[float] = []
    errors = 0
    lock = threading.Lock()

    def one_request(_i: int):
        nonlocal errors
        body, content_type = build_multipart(image_bytes)
        req = urllib.request.Request(endpoint, data=body, method="POST")
        req.add_header("Content-Type", content_type)
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp.read()
                ok = resp.status == 200
        except (urllib.error.URLError, TimeoutError, OSError):
            ok = False
        elapsed = (time.perf_counter() - start) * 1000
        with lock:
            if ok:
                latencies.append(elapsed)
            else:
                errors += 1

    print(f"目标: {endpoint}")
    print(f"并发: {args.concurrency}  总请求: {args.total}  图片: {os.path.basename(args.image)}")
    print("压测中...")

    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [executor.submit(one_request, i) for i in range(args.total)]
        for _ in as_completed(futures):
            pass
    wall = time.perf_counter() - wall_start

    ok_count = len(latencies)
    print("\n" + "=" * 50)
    print(f"总耗时:     {wall:.2f} s")
    print(f"成功/总数:  {ok_count}/{args.total}  (失败 {errors})")
    print(f"吞吐 QPS:   {ok_count / wall:.2f} 张/秒")
    if latencies:
        latencies.sort()

        def pct(p):
            return latencies[min(len(latencies) - 1, int(len(latencies) * p))]

        print(f"延迟 avg:   {statistics.mean(latencies):.0f} ms")
        print(f"延迟 P50:   {pct(0.50):.0f} ms")
        print(f"延迟 P95:   {pct(0.95):.0f} ms")
        print(f"延迟 P99:   {pct(0.99):.0f} ms")
        print(f"延迟 max:   {max(latencies):.0f} ms")
    print("=" * 50)


if __name__ == "__main__":
    main()

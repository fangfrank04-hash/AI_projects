"""一键测试入口：按顺序跑完全部验证，内网改完代码后只需要记住这一条命令。

流程：
    1. verify_repeat_logic.py  逻辑验证（不需要启动服务）
    2. 探测服务是否在运行
       - 在运行  -> 跑 smoke_api.py（接口冒烟） + verify_repeat_http.py（重复规则+并发）
       - 没在跑  -> 跳过 HTTP 测试并提示（不算失败）
    3. 汇总所有结果

用法（在 code 目录下，即和 app/ 同级的目录执行）：
    python scripts/run_all_tests.py                                # 默认 http://127.0.0.1:8000
    python scripts/run_all_tests.py --url http://22.25.5.10:8000   # 指定服务地址
    python scripts/run_all_tests.py --logic-only                   # 只跑逻辑验证（服务没起时）

压测（可选，不在一键流程里）：
    python scripts/load_test.py --url http://127.0.0.1:8000 --concurrency 8 --total 80

依赖：纯 Python 标准库，无需安装任何第三方包。
"""
import argparse
import os
import subprocess
import sys
import urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run_step(title, cmd):
    """跑一个子脚本，实时打印输出，返回是否成功。"""
    print()
    print("=" * 60)
    print(f"▶ {title}")
    print("=" * 60)
    result = subprocess.run(cmd, cwd=os.path.dirname(SCRIPT_DIR))
    return result.returncode == 0


def service_alive(url):
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/ping", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="一键测试入口")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="服务地址")
    parser.add_argument("--logic-only", action="store_true", help="只跑逻辑验证，跳过 HTTP 测试")
    args = parser.parse_args()

    steps = []

    # 1. 逻辑验证（不需要服务）
    steps.append((
        "步骤1 逻辑验证（重复告警规则，无需启动服务）",
        [sys.executable, os.path.join(SCRIPT_DIR, "verify_repeat_logic.py")],
    ))

    if not args.logic_only:
        if service_alive(args.url):
            steps.append((
                "步骤2 接口冒烟测试（健康检查/参数校验/上传/黑屏）",
                [sys.executable, os.path.join(SCRIPT_DIR, "smoke_api.py"), "--url", args.url],
            ))
            steps.append((
                "步骤3 重复告警规则实测（含并发安全验证）",
                [sys.executable, os.path.join(SCRIPT_DIR, "verify_repeat_http.py"), "--url", args.url],
            ))
        else:
            print()
            print(f"[提示] 服务 {args.url} 未运行，跳过 HTTP 测试（不算失败）。")
            print("[提示] 启动服务后重新运行本脚本可做完整验证。")

    # 依次执行并汇总
    results = []
    for title, cmd in steps:
        ok = run_step(title, cmd)
        results.append((title, ok))

    # 汇总
    print()
    print("=" * 60)
    print("总结果")
    print("=" * 60)
    all_ok = True
    for title, ok in results:
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {title}")
        all_ok = all_ok and ok
    print()
    print("全部通过 ✓" if all_ok else "存在失败项 ✗（看上方 FAIL 明细）")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()

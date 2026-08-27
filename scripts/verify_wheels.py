"""对比 wheels_linux/ 里的 wheel 与 uv.lock 记录的哈希是否一致。

用法：uv run scripts/verify_wheels.py [wheels目录，默认 deploy_split/wheels_linux]
退出码 0 = 全部匹配；1 = 有不匹配（会打印明细）。
"""
import hashlib
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WHEELS_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "deploy_split" / "wheels_linux"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    # uv.lock 中 wheels 数组项形如 { url = ".../xxx.whl", hash = "sha256:..." }
    lock_by_name: dict[str, str] = {}  # wheel文件名 -> sha256
    for pkg in lock["package"]:
        for whl in pkg.get("wheels", []):
            url = whl.get("url", "")
            hash_str = whl.get("hash", "")
            name = url.rsplit("/", 1)[-1] if url else ""
            if name and hash_str.startswith("sha256:"):
                lock_by_name[name] = hash_str.removeprefix("sha256:")

    local_files = sorted(WHEELS_DIR.glob("*.whl"))
    print(f"wheels 目录: {WHEELS_DIR}（{len(local_files)} 个文件）")
    print(f"uv.lock 记录的 wheel 总数: {len(lock_by_name)}（含全部平台）")

    matched, not_in_lock, hash_mismatch = [], [], []
    for f in local_files:
        digest = sha256_of(f)
        if f.name not in lock_by_name:
            not_in_lock.append(f.name)
        elif lock_by_name[f.name] != digest:
            hash_mismatch.append(f.name)
        else:
            matched.append(f.name)

    print(f"\n哈希与 uv.lock 完全一致: {len(matched)}")
    if not_in_lock:
        print(f"\n[警告] 文件名在 uv.lock 中找不到（可能是多标签同文件）: {len(not_in_lock)}")
        for n in not_in_lock:
            print(f"  - {n}")
    if hash_mismatch:
        print(f"\n[错误] 哈希不一致: {len(hash_mismatch)}")
        for n in hash_mismatch:
            print(f"  - {n}")
        return 1

    print("\n结论：所有能在 uv.lock 对上文件名的 wheel，sha256 全部一致。")
    print("（镜像构建 = uv sync --frozen 按同一份 uv.lock 下载安装，版本与哈希同源）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

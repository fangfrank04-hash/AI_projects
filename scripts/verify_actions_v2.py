"""
验证脚本 v2：测试 6 大类动作检测并生成交付报告。

运行方式（项目根目录）：
    .venv\\Scripts\\python.exe scripts\\verify_actions_v2.py

输出：
    reports/detection_report.md
    reports/detection_results.csv
"""

import argparse
import contextlib
import csv
import io
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.image_proctor import ImageProctor  # noqa: E402
from scripts.test_answer_manifest import AnswerRow, load_answer_manifest  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent
ANSWERS_PATH = ROOT_DIR / "assets" / "test_images" / "test_answers.csv"
REPORTS_DIR = ROOT_DIR / "reports"

EXPECTED_MARKERS = {
    "正常考试": ("正常",),
    "视线偏移": ("视线偏移",),
    "离开座位": ("离开座位",),
    "多人": ("多人",),
    "打电话": ("电话",),
    "伸胳膊": ("伸展",),
}

CSV_FIELDS = [
    "source_set",
    "split",
    "scenario",
    "image_path",
    "filename",
    "expected_category",
    "note",
    "actual",
    "passed",
    "elapsed_ms",
]


def collect_images(answers_path=ANSWERS_PATH, root_dir=ROOT_DIR):
    """读取标准答案表，只返回明确计入主测试的照片。"""
    rows = load_answer_manifest(Path(answers_path), Path(root_dir))
    return [row for row in rows if row.include_in_main]


def is_passed(expected_category, actual):
    """严格按业务大类判断，不接受其他类别作为兼容结果。"""
    return any(marker in actual for marker in EXPECTED_MARKERS[expected_category])


def run_single(proctor, answer: AnswerRow, root_dir=ROOT_DIR):
    """执行单张图片检测，返回结构化结果。"""
    filepath = Path(root_dir) / answer.image_path
    start = time.time()
    try:
        image = Image.open(filepath).convert("RGB")
        # ImageProctor 内部有调试 print，这里收束到报告，不污染终端。
        with contextlib.redirect_stdout(io.StringIO()):
            texts = proctor.get_image_face_angle_by_img(image)
        actual = texts[0][0] if texts else ""
    except Exception as exc:
        actual = "异常: " + str(exc)

    elapsed_ms = round((time.time() - start) * 1000, 2)
    return {
        "source_set": answer.source_set,
        "split": answer.split,
        "scenario": answer.scenario,
        "image_path": answer.image_path,
        "filename": filepath.name,
        "expected_category": answer.expected_category,
        "note": answer.note,
        "actual": actual,
        "passed": is_passed(answer.expected_category, actual),
        "elapsed_ms": elapsed_ms,
    }


def _rate(passed, count):
    return round(passed / count * 100, 2) if count else 0.0


def _latency_stats(values):
    if not values:
        return {"avg_elapsed_ms": 0.0, "max_elapsed_ms": 0.0, "p95_elapsed_ms": 0.0}

    sorted_values = sorted(values)
    p95_index = max(0, int(len(sorted_values) * 0.95 + 0.999999) - 1)
    return {
        "avg_elapsed_ms": round(sum(values) / len(values), 2),
        "max_elapsed_ms": round(max(values), 2),
        "p95_elapsed_ms": round(sorted_values[p95_index], 2),
    }


def build_summary(rows):
    """汇总总体和分类检测率、耗时统计。"""
    by_category = {}
    for row in rows:
        category = row["expected_category"]
        bucket = by_category.setdefault(
            category,
            {"count": 0, "passed": 0, "failed": 0, "latencies": []},
        )
        bucket["count"] += 1
        bucket["passed"] += 1 if row["passed"] else 0
        bucket["failed"] += 0 if row["passed"] else 1
        bucket["latencies"].append(float(row["elapsed_ms"]))

    for bucket in by_category.values():
        bucket["pass_rate"] = _rate(bucket["passed"], bucket["count"])
        bucket.update(_latency_stats(bucket.pop("latencies")))

    total_count = len(rows)
    total_passed = sum(1 for row in rows if row["passed"])
    total = {
        "count": total_count,
        "passed": total_passed,
        "failed": total_count - total_passed,
        "pass_rate": _rate(total_passed, total_count),
    }
    total.update(_latency_stats([float(row["elapsed_ms"]) for row in rows]))

    normal_rows = [row for row in rows if row["expected_category"] == "正常考试"]
    normal_false_positives = sum(1 for row in normal_rows if not row["passed"])

    return {
        "total": total,
        "by_category": by_category,
        "normal_false_positives": {
            "count": normal_false_positives,
            "total": len(normal_rows),
            "rate": _rate(normal_false_positives, len(normal_rows)),
        },
    }


def write_reports(rows, summary, output_dir=REPORTS_DIR):
    """写入 Markdown 汇总报告和 CSV 明细。"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / "detection_report.md"
    csv_path = output_dir / "detection_results.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})

    failed_rows = [row for row in rows if not row["passed"]]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# AI 监考检测率报告",
        "",
        f"- 生成时间：{generated_at}",
        f"- 标准答案表：`{ANSWERS_PATH.relative_to(ROOT_DIR).as_posix()}`",
        f"- 样本总数：{summary['total']['count']} 张",
        "- 正常考试误报：{count}/{total}（{rate:.2f}%）".format(
            **summary["normal_false_positives"]
        ),
        f"- 总体通过率：{summary['total']['pass_rate']:.2f}%",
        f"- 平均耗时：{summary['total']['avg_elapsed_ms']:.2f} ms",
        f"- P95 耗时：{summary['total']['p95_elapsed_ms']:.2f} ms",
        f"- 最大耗时：{summary['total']['max_elapsed_ms']:.2f} ms",
        "",
        "## 分类结果",
        "",
        "| 大类 | 样本数 | 通过 | 失败 | 通过率 | 平均耗时 | P95耗时 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for category in sorted(summary["by_category"]):
        item = summary["by_category"][category]
        lines.append(
            "| {category} | {count} | {passed} | {failed} | {pass_rate:.2f}% | "
            "{avg:.2f} ms | {p95:.2f} ms |".format(
                category=category,
                count=item["count"],
                passed=item["passed"],
                failed=item["failed"],
                pass_rate=item["pass_rate"],
                avg=item["avg_elapsed_ms"],
                p95=item["p95_elapsed_ms"],
            )
        )

    lines.extend(
        [
            "",
            "## 失败样本清单",
            "",
        ]
    )

    if failed_rows:
        lines.extend(
            [
                "| 文件 | 预期大类 | 预期描述 | 实际结果 | 耗时 |",
                "|---|---|---|---|---:|",
            ]
        )
        for row in failed_rows:
            lines.append(
                "| {filename} | {expected_category} | {note} | {actual} | "
                "{elapsed_ms:.2f} ms |".format(
                    filename=row["filename"],
                    expected_category=row["expected_category"],
                    note=row.get("note") or row["expected_category"],
                    actual=row["actual"].replace("|", "/"),
                    elapsed_ms=float(row["elapsed_ms"]),
                )
            )
    else:
        lines.append("本次验证没有失败样本。")

    lines.extend(
        [
            "",
            "## 下一步建议",
            "",
            "1. 优先查看失败样本清单，按大类定位误判/漏判模式。",
            "2. 每次调整阈值或规则后重新运行本脚本，比较 CSV 明细和分类通过率。",
            "3. tune/eval 来自同批连续拍摄，只能说明同场景稳定性，不能代表陌生考场泛化能力。",
            "4. 当前报告只代表本地样本集表现，真实考场上线前仍需补充更多光线、角度、遮挡和多人半入镜样本。",
        ]
    )

    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"markdown": markdown_path, "csv": csv_path}


def run_verification(
    answers_path=ANSWERS_PATH, output_dir=REPORTS_DIR, limit=None, root_dir=ROOT_DIR
):
    images = collect_images(answers_path, root_dir)
    if limit is not None:
        images = images[:limit]

    if not images:
        raise FileNotFoundError(f"标准答案表中没有主测试照片：{answers_path}")

    print("=" * 80)
    print("ImageProctor 6 大类验证 v2")
    print(f"标准答案表：{answers_path}")
    print(f"样本数量：{len(images)} 张")
    print("=" * 80)

    proctor = ImageProctor()
    rows = []
    for index, answer in enumerate(images, start=1):
        row = run_single(proctor, answer, root_dir)
        rows.append(row)
        mark = "PASS" if row["passed"] else "FAIL"
        if not row["passed"]:
            print(
                f"[{mark}] {index}/{len(images)} {row['filename']} "
                f"预期={row['expected_category']} 实际={row['actual']} "
                f"耗时={row['elapsed_ms']:.0f}ms"
            )
        elif index % 20 == 0 or index == len(images):
            print(f"[进度] {index}/{len(images)}")

    summary = build_summary(rows)
    paths = write_reports(rows, summary, output_dir)
    return rows, summary, paths


def parse_args():
    parser = argparse.ArgumentParser(description="验证 6 大类监考检测并生成报告")
    parser.add_argument(
        "--answers",
        default=str(ANSWERS_PATH),
        help="标准答案 CSV 路径",
    )
    parser.add_argument("--output-dir", default=str(REPORTS_DIR), help="报告输出目录")
    parser.add_argument("--limit", type=int, default=None, help="仅验证前 N 张，用于快速冒烟")
    return parser.parse_args()


def main():
    args = parse_args()
    rows, summary, paths = run_verification(args.answers, args.output_dir, args.limit)

    print("\n" + "=" * 80)
    print("验证汇总")
    print("=" * 80)
    print(f"{'大类':<10} {'通过':>6} {'失败':>6} {'通过率':>8} {'平均耗时':>10}")
    print("-" * 52)
    for category in sorted(summary["by_category"]):
        item = summary["by_category"][category]
        print(
            f"{category:<10} {item['passed']:>6} {item['failed']:>6} "
            f"{item['pass_rate']:>7.2f}% {item['avg_elapsed_ms']:>9.0f}ms"
        )
    print("-" * 52)
    total = summary["total"]
    print(
        f"{'总计':<10} {total['passed']:>6} {total['failed']:>6} "
        f"{total['pass_rate']:>7.2f}% {total['avg_elapsed_ms']:>9.0f}ms"
    )
    print(f"\nMarkdown 报告：{paths['markdown']}")
    print(f"CSV 明细：{paths['csv']}")
    print(f"验证图片数：{len(rows)}")


if __name__ == "__main__":
    main()

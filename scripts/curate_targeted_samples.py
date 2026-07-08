"""
Curate newly captured targeted samples without deleting the raw photos.

Run from project root:
    .venv\\Scripts\\python.exe scripts\\curate_targeted_samples.py

Output:
    assets/test_images/targeted_samples_clean/
    reports/targeted_samples_curated_report.md
"""

from __future__ import annotations

import argparse
import csv
import shutil
from collections import Counter, defaultdict
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_DIR = ROOT_DIR / "assets" / "test_images" / "targeted_samples"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "assets" / "test_images" / "targeted_samples_clean"
DEFAULT_REPORT_PATH = ROOT_DIR / "reports" / "targeted_samples_curated_report.md"
MANIFEST_NAME = "samples_manifest.csv"

MANUAL_REJECTS = {
    ("stretch_left_horizontal", "2"),
    ("stretch_left_horizontal", "3"),
    ("stretch_both_mixed", "1"),
    ("normal_side_guard", "2"),
    ("normal_side_guard", "3"),
    ("normal_side_guard", "4"),
}


def read_manifest(source_dir: Path) -> list[dict[str, str]]:
    manifest_path = source_dir / MANIFEST_NAME
    with manifest_path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def classify_row(row: dict[str, str]) -> str:
    if (row["code"], row["shot_index"]) in MANUAL_REJECTS:
        return "manual_reject"
    return "keep"


def select_latest_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["code"], row["shot_index"])
        current = selected.get(key)
        if current is None or row["created_at"] > current["created_at"]:
            selected[key] = row
    return list(selected.values())


def clean_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def copy_curated_images(rows: list[dict[str, str]], output_dir: Path) -> list[dict[str, str]]:
    curated_rows = []
    for row in rows:
        source_path = ROOT_DIR / row["relative_path"]
        target_dir = output_dir / row["category_dir"]
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / row["filename"]
        shutil.copy2(source_path, target_path)

        curated = dict(row)
        curated["raw_relative_path"] = row["relative_path"]
        curated["relative_path"] = target_path.relative_to(ROOT_DIR).as_posix()
        curated["curation_status"] = "kept"
        curated_rows.append(curated)
    return curated_rows


def write_manifest(output_dir: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    manifest_path = output_dir / MANIFEST_NAME
    fields = list(rows[0].keys())
    with manifest_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summarize_rejections(rows: list[dict[str, str]], latest_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    latest_keys = {(row["code"], row["shot_index"], row["filename"]) for row in latest_rows}
    latest_by_key = {(row["code"], row["shot_index"]) for row in latest_rows}
    rejected = []
    for row in rows:
        status = classify_row(row)
        if status == "manual_reject":
            rejected.append({**row, "reason": "manual_reject"})
            continue
        key = (row["code"], row["shot_index"])
        file_key = (row["code"], row["shot_index"], row["filename"])
        if key in latest_by_key and file_key not in latest_keys:
            rejected.append({**row, "reason": "older_duplicate"})
    return rejected


def write_report(report_path: Path, raw_rows: list[dict[str, str]], kept_rows: list[dict[str, str]], rejected_rows: list[dict[str, str]], output_dir: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    kept_by_category = Counter(row["category_dir"] for row in kept_rows)
    rejected_by_reason = Counter(row["reason"] for row in rejected_rows)
    kept_by_code = Counter(row["code"] for row in kept_rows)

    lines = [
        "# Targeted Samples Curation Report",
        "",
        f"- Raw manifest rows: {len(raw_rows)}",
        f"- Kept rows: {len(kept_rows)}",
        f"- Rejected rows: {len(rejected_rows)}",
        f"- Clean output: `{output_dir.relative_to(ROOT_DIR).as_posix()}`",
        "",
        "## Kept By Category",
        "",
        "| Category | Count |",
        "|---|---:|",
    ]
    for category, count in sorted(kept_by_category.items()):
        lines.append(f"| {category} | {count} |")

    lines.extend([
        "",
        "## Kept By Code",
        "",
        "| Code | Count |",
        "|---|---:|",
    ])
    for code, count in sorted(kept_by_code.items()):
        lines.append(f"| {code} | {count} |")

    lines.extend([
        "",
        "## Rejected By Reason",
        "",
        "| Reason | Count |",
        "|---|---:|",
    ])
    for reason, count in sorted(rejected_by_reason.items()):
        lines.append(f"| {reason} | {count} |")

    lines.extend([
        "",
        "## Rejected Samples",
        "",
        "| Code | Shot | Filename | Reason |",
        "|---|---:|---|---|",
    ])
    for row in rejected_rows:
        lines.append(f"| {row['code']} | {row['shot_index']} | {row['filename']} | {row['reason']} |")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def curate_samples(source_dir: Path, output_dir: Path, report_path: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    raw_rows = read_manifest(source_dir)
    kept_candidates = [row for row in raw_rows if classify_row(row) == "keep"]
    latest_kept = select_latest_rows(kept_candidates)
    rejected_rows = summarize_rejections(raw_rows, latest_kept)

    clean_output_dir(output_dir)
    curated_rows = copy_curated_images(latest_kept, output_dir)
    write_manifest(output_dir, curated_rows)
    write_report(report_path, raw_rows, curated_rows, rejected_rows, output_dir)
    return curated_rows, rejected_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a cleaned targeted sample set.")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE_DIR), help="Raw targeted sample directory.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR), help="Clean sample output directory.")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Markdown report path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    kept, rejected = curate_samples(Path(args.source).resolve(), Path(args.output).resolve(), Path(args.report).resolve())
    print(f"Kept: {len(kept)}")
    print(f"Rejected: {len(rejected)}")
    print(f"Clean directory: {Path(args.output).resolve()}")
    print(f"Report: {Path(args.report).resolve()}")


if __name__ == "__main__":
    main()

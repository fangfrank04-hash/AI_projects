"""Build the reviewed 305-image answer manifest."""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLES_V2_DIR = ROOT_DIR / "assets" / "test_images" / "samples_v2"
TARGETED_DIR = ROOT_DIR / "assets" / "test_images" / "targeted_samples"
TARGETED_MANIFEST = TARGETED_DIR / "samples_manifest.csv"
OUTPUT_PATH = ROOT_DIR / "assets" / "test_images" / "test_answers.csv"

CSV_FIELDS = (
    "image_path",
    "source_set",
    "scenario",
    "expected_category",
    "split",
    "include_in_main",
    "note",
)

EXPECTED_COUNTS = {
    "正常考试": 37,
    "视线偏移": 68,
    "离开座位": 15,
    "多人": 70,
    "打电话": 35,
    "伸胳膊": 80,
}

SAMPLES_V2_RULES = {
    "normal_front": "正常考试",
    "normal_side": "正常考试",
    "normal_writing": "视线偏移",
    "face_hidden_in_frame": "视线偏移",
    "head_turn_large": "视线偏移",
    "phone_look_down": "视线偏移",
    "turn_body_left_90": "视线偏移",
    "turn_body_right_90": "视线偏移",
    "turn_head": "视线偏移",
    "person_gone": "离开座位",
    "stand_up": "离开座位",
    "two_persons_talking": "多人",
    "two_persons": "多人",
    "person_entering": "多人",
    "phone_left": "打电话",
    "phone_right": "打电话",
    "stretch_left": "伸胳膊",
    "stretch_right": "伸胳膊",
    "stretch_both": "伸胳膊",
}

TARGETED_CATEGORY_MAP = {
    "正常考试": "正常考试",
    "多人": "多人",
    "打电话": "打电话",
    "伸胳膊": "伸胳膊",
}

SEATED_TURN_FILENAMES = {
    "normal_side_guard_002_20260708_154603.jpg",
    "normal_side_guard_003_20260708_154605.jpg",
    "normal_side_guard_004_20260708_154611.jpg",
}


def _match_samples_v2_rule(filename: str) -> tuple[str, str]:
    for prefix in sorted(SAMPLES_V2_RULES, key=len, reverse=True):
        if filename.startswith(prefix + "_"):
            return prefix, SAMPLES_V2_RULES[prefix]
    raise ValueError(f"samples_v2 照片没有答案规则：{filename}")


def _sequence_number(filename: str, scenario: str) -> int:
    match = re.match(rf"^{re.escape(scenario)}_(\d+)_", filename)
    if not match:
        raise ValueError(f"无法读取照片序号：{filename}")
    return int(match.group(1))


def _samples_v2_note(scenario: str) -> str:
    if scenario == "normal_writing":
        return "低头写字"
    if scenario == "phone_look_down":
        return "低头看手机"
    if scenario.startswith("turn_body"):
        return "坐着转身"
    if scenario == "turn_head":
        return "坐着转头"
    return ""


def build_samples_v2_rows(root_dir: Path = ROOT_DIR) -> list[dict[str, str]]:
    samples_dir = root_dir / "assets" / "test_images" / "samples_v2"
    rows = []
    for image_path in sorted(samples_dir.glob("*/*")):
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        scenario, category = _match_samples_v2_rule(image_path.name)
        sequence = _sequence_number(image_path.name, scenario)
        rows.append(
            {
                "image_path": image_path.relative_to(root_dir).as_posix(),
                "source_set": "samples_v2",
                "scenario": scenario,
                "expected_category": category,
                "split": "tune" if sequence <= 7 else "eval",
                "include_in_main": "1",
                "note": _samples_v2_note(scenario),
            }
        )
    return rows


def build_targeted_rows(root_dir: Path = ROOT_DIR) -> list[dict[str, str]]:
    manifest_path = (
        root_dir / "assets" / "test_images" / "targeted_samples" / "samples_manifest.csv"
    )
    rows = []
    with manifest_path.open(encoding="utf-8-sig", newline="") as file:
        for source in csv.DictReader(file):
            filename = source["filename"]
            category = TARGETED_CATEGORY_MAP.get(source["category"])
            if category is None:
                raise ValueError(
                    f"targeted_samples 未知类别：{source['category']} ({filename})"
                )
            note = ""
            if filename in SEATED_TURN_FILENAMES:
                category = "视线偏移"
                note = "坐着转身"

            image_path = root_dir / source["relative_path"]
            if not image_path.is_file():
                raise FileNotFoundError(f"targeted_samples 照片不存在：{image_path}")
            rows.append(
                {
                    "image_path": image_path.relative_to(root_dir).as_posix(),
                    "source_set": "targeted_samples",
                    "scenario": source["code"],
                    "expected_category": category,
                    "split": source["split"],
                    "include_in_main": "1",
                    "note": note,
                }
            )
    return rows


def build_answer_rows(root_dir: Path = ROOT_DIR) -> list[dict[str, str]]:
    rows = build_samples_v2_rows(root_dir) + build_targeted_rows(root_dir)
    rows.sort(key=lambda row: row["image_path"])

    paths = [row["image_path"] for row in rows]
    if len(paths) != len(set(paths)):
        raise ValueError("标准答案表出现重复照片路径")
    if len(rows) != 305:
        raise ValueError(f"标准答案数量应为 305，实际为 {len(rows)}")

    counts = Counter(row["expected_category"] for row in rows)
    if dict(counts) != EXPECTED_COUNTS:
        raise ValueError(f"标准答案分类数量错误：{dict(counts)}")
    return rows


def write_answer_manifest(
    output_path: Path = OUTPUT_PATH, root_dir: Path = ROOT_DIR
) -> list[dict[str, str]]:
    rows = build_answer_rows(root_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> None:
    rows = write_answer_manifest()
    counts = Counter(row["expected_category"] for row in rows)
    print(f"Wrote {len(rows)} answers to {OUTPUT_PATH.relative_to(ROOT_DIR)}")
    print(" ".join(f"{category}={counts[category]}" for category in EXPECTED_COUNTS))


if __name__ == "__main__":
    main()

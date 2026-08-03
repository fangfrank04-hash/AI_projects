"""Load and validate the image-proctor test answer manifest."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

ALLOWED_CATEGORIES = {
    "正常考试",
    "视线偏移",
    "离开座位",
    "多人",
    "打电话",
    "伸胳膊",
}

REQUIRED_FIELDS = (
    "image_path",
    "source_set",
    "scenario",
    "expected_category",
    "split",
    "include_in_main",
    "note",
)


@dataclass(frozen=True)
class AnswerRow:
    image_path: str
    source_set: str
    scenario: str
    expected_category: str
    split: str
    include_in_main: bool
    note: str


def _validate_relative_path(raw_path: str, row_number: int) -> Path:
    image_path = Path(raw_path)
    if image_path.is_absolute():
        raise ValueError(f"第 {row_number} 行：照片路径必须是项目内相对路径")
    if ".." in image_path.parts:
        raise ValueError(f"第 {row_number} 行：照片路径不能包含 '..'")
    if not raw_path.strip():
        raise ValueError(f"第 {row_number} 行：照片路径不能为空")
    return image_path


def load_answer_manifest(csv_path: Path, root_dir: Path) -> list[AnswerRow]:
    """Read the manifest and reject incomplete, unsafe, or duplicate rows."""
    csv_path = Path(csv_path)
    root_dir = Path(root_dir)
    rows: list[AnswerRow] = []
    seen_paths: set[str] = set()

    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing_fields = [
            field for field in REQUIRED_FIELDS if field not in (reader.fieldnames or [])
        ]
        if missing_fields:
            raise ValueError(f"答案表缺少字段：{', '.join(missing_fields)}")

        for row_number, raw in enumerate(reader, start=2):
            relative_path = _validate_relative_path(raw["image_path"], row_number)
            normalized_path = relative_path.as_posix()
            if normalized_path in seen_paths:
                raise ValueError(f"第 {row_number} 行：重复照片路径 {normalized_path}")
            seen_paths.add(normalized_path)

            category = raw["expected_category"].strip()
            if category not in ALLOWED_CATEGORIES:
                raise ValueError(f"第 {row_number} 行：非法答案类别 {category!r}")

            include_value = raw["include_in_main"].strip()
            if include_value not in {"0", "1"}:
                raise ValueError(
                    f"第 {row_number} 行：include_in_main 只能是 0 或 1"
                )

            if not (root_dir / relative_path).is_file():
                raise ValueError(f"第 {row_number} 行：照片不存在 {normalized_path}")

            rows.append(
                AnswerRow(
                    image_path=normalized_path,
                    source_set=raw["source_set"].strip(),
                    scenario=raw["scenario"].strip(),
                    expected_category=category,
                    split=raw["split"].strip(),
                    include_in_main=include_value == "1",
                    note=raw["note"].strip(),
                )
            )

    return rows

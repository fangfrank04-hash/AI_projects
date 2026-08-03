import csv
import tempfile
import unittest
from pathlib import Path

from scripts.test_answer_manifest import load_answer_manifest

FIELDS = [
    "image_path",
    "source_set",
    "scenario",
    "expected_category",
    "split",
    "include_in_main",
    "note",
]


class AnswerManifestTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.csv_path = self.root / "test_answers.csv"

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_image(self, relative_path="assets/test_images/sample.jpg"):
        image_path = self.root / relative_path
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"jpeg")
        return relative_path

    def valid_row(self, **overrides):
        row = {
            "image_path": "assets/test_images/sample.jpg",
            "source_set": "samples_v2",
            "scenario": "normal_front",
            "expected_category": "正常考试",
            "split": "eval",
            "include_in_main": "1",
            "note": "",
        }
        row.update(overrides)
        return row

    def write_csv(self, rows, fields=FIELDS):
        with self.csv_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    def test_loads_one_valid_answer_row(self):
        self.make_image()
        self.write_csv([self.valid_row()])

        rows = load_answer_manifest(self.csv_path, self.root)

        self.assertEqual(1, len(rows))
        self.assertEqual("正常考试", rows[0].expected_category)
        self.assertTrue(rows[0].include_in_main)

    def test_rejects_duplicate_image_paths(self):
        self.make_image()
        self.write_csv([self.valid_row(), self.valid_row()])

        with self.assertRaisesRegex(ValueError, "第 3 行.*重复照片路径"):
            load_answer_manifest(self.csv_path, self.root)

    def test_rejects_unsupported_category(self):
        self.make_image()
        self.write_csv([self.valid_row(expected_category="转身")])

        with self.assertRaisesRegex(ValueError, "第 2 行.*非法答案类别"):
            load_answer_manifest(self.csv_path, self.root)

    def test_rejects_missing_image(self):
        self.write_csv([self.valid_row()])

        with self.assertRaisesRegex(ValueError, "第 2 行.*照片不存在"):
            load_answer_manifest(self.csv_path, self.root)

    def test_rejects_absolute_image_path(self):
        self.write_csv([self.valid_row(image_path="D:/outside.jpg")])

        with self.assertRaisesRegex(ValueError, "第 2 行.*必须是项目内相对路径"):
            load_answer_manifest(self.csv_path, self.root)

    def test_rejects_parent_directory_path(self):
        self.write_csv([self.valid_row(image_path="../outside.jpg")])

        with self.assertRaisesRegex(ValueError, "第 2 行.*不能包含"):
            load_answer_manifest(self.csv_path, self.root)

    def test_rejects_invalid_include_flag(self):
        self.make_image()
        self.write_csv([self.valid_row(include_in_main="yes")])

        with self.assertRaisesRegex(ValueError, "第 2 行.*include_in_main"):
            load_answer_manifest(self.csv_path, self.root)

    def test_rejects_missing_required_column(self):
        fields = [field for field in FIELDS if field != "note"]
        self.write_csv([self.valid_row()], fields=fields)

        with self.assertRaisesRegex(ValueError, "缺少字段.*note"):
            load_answer_manifest(self.csv_path, self.root)


if __name__ == "__main__":
    unittest.main()

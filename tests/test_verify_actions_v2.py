import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from scripts import verify_actions_v2 as report
from scripts.answer_manifest import AnswerRow


class FakeProctor:
    def __init__(self, action_type, action_label):
        self.result = SimpleNamespace(
            action_type=action_type,
            action_label=action_label,
        )

    def analyze(self, _image):
        return self.result


class VerifyActionsReportTest(unittest.TestCase):
    def test_collect_images_uses_only_included_manifest_rows(self):
        fields = [
            "image_path",
            "source_set",
            "scenario",
            "expected_category",
            "split",
            "include_in_main",
            "note",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_dir = root / "assets" / "test_images"
            image_dir.mkdir(parents=True)
            for name in ("included.jpg", "excluded.jpg"):
                Image.new("RGB", (4, 4)).save(image_dir / name)
            answers_path = root / "answers.csv"
            with answers_path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=fields)
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "image_path": "assets/test_images/included.jpg",
                            "source_set": "samples_v2",
                            "scenario": "normal_front",
                            "expected_category": "正常考试",
                            "split": "eval",
                            "include_in_main": "1",
                            "note": "",
                        },
                        {
                            "image_path": "assets/test_images/excluded.jpg",
                            "source_set": "samples_v2",
                            "scenario": "normal_front",
                            "expected_category": "正常考试",
                            "split": "eval",
                            "include_in_main": "0",
                            "note": "not scored",
                        },
                    ]
                )

            answers = report.collect_images(answers_path, root)

            self.assertEqual(1, len(answers))
            self.assertEqual("assets/test_images/included.jpg", answers[0].image_path)

    def test_gaze_away_does_not_accept_normal_or_leave_seat(self):
        self.assertFalse(report.is_passed("视线偏移", "正常考试"))
        self.assertFalse(report.is_passed("视线偏移", "离开座位"))
        self.assertTrue(report.is_passed("视线偏移", "视线偏移"))

    def test_run_single_scores_against_answer_category(self):
        answer = AnswerRow(
            image_path="sample.jpg",
            source_set="samples_v2",
            scenario="normal_writing",
            expected_category="视线偏移",
            split="eval",
            include_in_main=True,
            note="低头写字",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (4, 4)).save(root / "sample.jpg")

            row = report.run_single(
                FakeProctor("normal", "正常考试中"), answer, root
            )

        self.assertEqual("视线偏移", row["expected_category"])
        self.assertEqual("正常考试", row["actual_category"])
        self.assertFalse(row["passed"])

    def test_turn_head_action_type_maps_to_gaze_away(self):
        answer = AnswerRow(
            image_path="sample.jpg",
            source_set="samples_v2",
            scenario="normal_writing",
            expected_category="视线偏移",
            split="eval",
            include_in_main=True,
            note="低头写字",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (4, 4)).save(root / "sample.jpg")

            row = report.run_single(
                FakeProctor("turn_head", "视线偏移(考生转头)"), answer, root
            )

        self.assertEqual("视线偏移", row["actual_category"])
        self.assertTrue(row["passed"])

    def test_turn_body_action_type_remains_leave_seat(self):
        answer = AnswerRow(
            image_path="sample.jpg",
            source_set="samples_v2",
            scenario="turn_body_left_90",
            expected_category="视线偏移",
            split="eval",
            include_in_main=True,
            note="坐着转身",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.new("RGB", (4, 4)).save(root / "sample.jpg")

            row = report.run_single(
                FakeProctor("turn_body", "离开座位(考生转身)"), answer, root
            )

        self.assertEqual("离开座位", row["actual_category"])
        self.assertFalse(row["passed"])

    def test_build_summary_counts_pass_fail_and_latency(self):
        rows = [
            {
                "expected_category": "正常考试",
                "passed": True,
                "elapsed_ms": 100.0,
            },
            {
                "expected_category": "正常考试",
                "passed": False,
                "elapsed_ms": 300.0,
            },
            {
                "expected_category": "多人",
                "passed": True,
                "elapsed_ms": 200.0,
            },
        ]

        summary = report.build_summary(rows)

        self.assertEqual(summary["total"]["count"], 3)
        self.assertEqual(summary["total"]["passed"], 2)
        self.assertEqual(summary["total"]["failed"], 1)
        self.assertEqual(summary["total"]["pass_rate"], 66.67)
        self.assertEqual(summary["total"]["avg_elapsed_ms"], 200.0)
        self.assertEqual(summary["by_category"]["正常考试"]["failed"], 1)
        self.assertEqual(summary["by_category"]["多人"]["pass_rate"], 100.0)
        self.assertEqual(
            summary["normal_false_positives"],
            {"count": 1, "total": 2, "rate": 50.0},
        )

    def test_write_reports_creates_markdown_and_csv(self):
        rows = [
            {
                "category_dir": "normal",
                "filename": "normal_front_01.jpg",
                "expected_category": "正常考试",
                "expected_desc": "正常考试",
                "expected_keyword": "正常",
                "actual": "正常考试中 ...",
                "passed": True,
                "elapsed_ms": 123.45,
            },
            {
                "category_dir": "multi_person",
                "filename": "person_entering_01.jpg",
                "expected_category": "多人",
                "expected_desc": "多人",
                "expected_keyword": "多人",
                "actual": "正常考试中 ...",
                "passed": False,
                "elapsed_ms": 456.78,
            },
        ]
        summary = report.build_summary(rows)

        with tempfile.TemporaryDirectory() as tmp:
            paths = report.write_reports(rows, summary, tmp)

            self.assertTrue(paths["markdown"].exists())
            self.assertTrue(paths["csv"].exists())
            markdown = paths["markdown"].read_text(encoding="utf-8")
            self.assertIn("AI 监考检测率报告", markdown)
            self.assertIn("person_entering_01.jpg", markdown)
            self.assertIn("平均耗时", markdown)
            self.assertIn("正常考试误报：0/1（0.00%）", markdown)
            self.assertIn("assets/test_images/test_answers.csv", markdown)
            self.assertIn("不能代表陌生考场泛化能力", markdown)

            with paths["csv"].open(encoding="utf-8-sig", newline="") as f:
                csv_rows = list(csv.DictReader(f))
            self.assertEqual(csv_rows[1]["filename"], "person_entering_01.jpg")
            self.assertEqual(csv_rows[1]["passed"], "False")


if __name__ == "__main__":
    unittest.main()

import csv
import tempfile
import unittest

from scripts import verify_actions_v2 as report


class VerifyActionsReportTest(unittest.TestCase):
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

            with paths["csv"].open(encoding="utf-8-sig", newline="") as f:
                csv_rows = list(csv.DictReader(f))
            self.assertEqual(csv_rows[1]["filename"], "person_entering_01.jpg")
            self.assertEqual(csv_rows[1]["passed"], "False")


if __name__ == "__main__":
    unittest.main()

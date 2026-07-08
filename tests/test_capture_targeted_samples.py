import unittest
from pathlib import Path

from scripts import capture_targeted_samples as capture


class CaptureTargetedSamplesTest(unittest.TestCase):
    def test_default_plan_has_expected_total_count(self):
        plan = capture.build_capture_plan("focused")

        self.assertEqual(120, sum(item["count"] for item in plan))

    def test_every_capture_item_has_guidance_fields(self):
        plan = capture.build_capture_plan("focused")

        for item in plan:
            self.assertTrue(item["category"])
            self.assertTrue(item["code"])
            self.assertTrue(item["goal"])
            self.assertGreaterEqual(len(item["pose_steps"]), 3)
            self.assertGreaterEqual(len(item["quality_checks"]), 2)
            self.assertGreaterEqual(len(item["avoid"]), 2)

    def test_manifest_row_contains_capture_metadata(self):
        item = capture.build_capture_plan("focused")[0]

        row = capture.build_manifest_row(
            item=item,
            filename="sample.jpg",
            saved_path=Path("assets/test_images/targeted_samples/normal/sample.jpg"),
            shot_index=1,
            split="tune",
            camera_index=0,
        )

        self.assertEqual("sample.jpg", row["filename"])
        self.assertEqual(item["category"], row["category"])
        self.assertEqual(item["code"], row["code"])
        self.assertEqual("tune", row["split"])
        self.assertEqual("0", row["camera_index"])


if __name__ == "__main__":
    unittest.main()

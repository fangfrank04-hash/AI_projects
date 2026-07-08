import unittest

from scripts import curate_targeted_samples as curate


class CurateTargetedSamplesTest(unittest.TestCase):
    def test_rejects_known_mislabeled_samples(self):
        row = {
            "code": "normal_side_guard",
            "shot_index": "2",
            "filename": "normal_side_guard_002_20260708_154603.jpg",
        }

        self.assertEqual("manual_reject", curate.classify_row(row))

    def test_keeps_latest_duplicate_shot(self):
        rows = [
            {
                "code": "normal_front_guard",
                "shot_index": "1",
                "filename": "normal_front_guard_001_20260708_154417.jpg",
                "created_at": "2026-07-08T15:44:17",
            },
            {
                "code": "normal_front_guard",
                "shot_index": "1",
                "filename": "normal_front_guard_001_20260708_154502.jpg",
                "created_at": "2026-07-08T15:45:02",
            },
        ]

        selected = curate.select_latest_rows(rows)

        self.assertEqual(1, len(selected))
        self.assertEqual("normal_front_guard_001_20260708_154502.jpg", selected[0]["filename"])

    def test_keeps_known_hard_but_valid_stretch_sample(self):
        row = {
            "code": "stretch_right_horizontal",
            "shot_index": "10",
            "filename": "stretch_right_horizontal_010_20260708_153952.jpg",
        }

        self.assertEqual("keep", curate.classify_row(row))


if __name__ == "__main__":
    unittest.main()

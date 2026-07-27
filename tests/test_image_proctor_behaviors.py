import contextlib
import io
import unittest
from pathlib import Path

from PIL import Image

from app.ml.image_proctor import ImageProctor
from app.schemas.proctor import ActionType

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT_DIR / "assets" / "test_images" / "samples_v2"


def analyze_sample(relative_path):
    proctor = ImageProctor()
    image_path = SAMPLES_DIR / relative_path
    with Image.open(image_path).convert("RGB") as image:
        with contextlib.redirect_stdout(io.StringIO()):
            result = proctor.analyze(image)
    return result


class ImageProctorBehaviorTest(unittest.TestCase):
    def test_detects_partial_multi_person_entry(self):
        result = analyze_sample(Path("multi_person") / "person_entering_01_173414.jpg")

        self.assertEqual(result.action_type, ActionType.MULTI_PERSON)

    def test_normal_exam_is_not_multi_person(self):
        result = analyze_sample(Path("normal") / "normal_front_01_174349.jpg")

        self.assertNotEqual(result.action_type, ActionType.MULTI_PERSON)

    def test_detects_horizontal_right_arm_stretch(self):
        result = analyze_sample(Path("stretch_arm") / "stretch_right_10_174635.jpg")

        self.assertEqual(result.action_type, ActionType.STRETCH_ARM)

    def test_side_normal_exam_is_not_stretch_arm(self):
        result = analyze_sample(Path("normal") / "normal_side_08_174419.jpg")

        self.assertNotEqual(result.action_type, ActionType.STRETCH_ARM)


if __name__ == "__main__":
    unittest.main()

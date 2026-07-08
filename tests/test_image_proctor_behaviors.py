import contextlib
import io
import unittest
from pathlib import Path

from PIL import Image

from app.ml.image_proctor import ImageProctor


ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = ROOT_DIR / "assets" / "test_images" / "samples_v2"


def analyze_sample(relative_path):
    proctor = ImageProctor()
    image_path = SAMPLES_DIR / relative_path
    with Image.open(image_path).convert("RGB") as image:
        with contextlib.redirect_stdout(io.StringIO()):
            result = proctor.GetImageFaceAngleByImg(image)
    return result[0][0] if result else ""


class ImageProctorBehaviorTest(unittest.TestCase):
    def test_detects_partial_multi_person_entry(self):
        actual = analyze_sample(Path("multi_person") / "person_entering_01_173414.jpg")

        self.assertIn("多人", actual)

    def test_normal_exam_is_not_multi_person(self):
        actual = analyze_sample(Path("normal") / "normal_front_01_174349.jpg")

        self.assertNotIn("多人", actual)


if __name__ == "__main__":
    unittest.main()

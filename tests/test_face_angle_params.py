import contextlib
import io
import unittest
from pathlib import Path

from PIL import Image

from app.ml.image_proctor import (
    DEFAULT_MAX_DOWN_ANGLE,
    DEFAULT_MAX_LEFT_ANGLE,
    DEFAULT_MAX_RIGHT_ANGLE,
    DEFAULT_MAX_UP_ANGLE,
    FaceAngleThresholds,
    ImageProctor,
)
from app.services.proctor_service import _build_face_angles

ROOT_DIR = Path(__file__).resolve().parent.parent
SAMPLE_IMAGE = (
    ROOT_DIR / "assets" / "test_images" / "samples_v2" / "normal" / "normal_front_01_174349.jpg"
)


def _analyze(proctor, face_angles=None):
    with Image.open(SAMPLE_IMAGE).convert("RGB") as image:
        with contextlib.redirect_stdout(io.StringIO()):
            proctor.analyze(image, face_angles=face_angles)


class FaceAngleDefaultsTest(unittest.TestCase):
    def test_dataclass_defaults_match_constants(self):
        thresholds = FaceAngleThresholds()
        self.assertEqual(thresholds.max_left_angle, DEFAULT_MAX_LEFT_ANGLE)
        self.assertEqual(thresholds.max_right_angle, DEFAULT_MAX_RIGHT_ANGLE)
        self.assertEqual(thresholds.max_up_angle, DEFAULT_MAX_UP_ANGLE)
        self.assertEqual(thresholds.max_down_angle, DEFAULT_MAX_DOWN_ANGLE)


class BuildFaceAnglesTest(unittest.TestCase):
    def test_returns_none_when_nothing_passed(self):
        # Java 不传任何参数：service 返回 None，交给 ml 层用默认值。
        self.assertIsNone(_build_face_angles())

    def test_partial_override_keeps_defaults_for_rest(self):
        # 只传一个参数：其余字段自动用默认值。
        result = _build_face_angles(max_left_angle=15)
        self.assertIsNotNone(result)
        self.assertEqual(result.max_left_angle, 15)
        self.assertEqual(result.max_right_angle, DEFAULT_MAX_RIGHT_ANGLE)
        self.assertEqual(result.max_up_angle, DEFAULT_MAX_UP_ANGLE)
        self.assertEqual(result.max_down_angle, DEFAULT_MAX_DOWN_ANGLE)


class NoPollutionTest(unittest.TestCase):
    def test_custom_thresholds_do_not_leak_to_next_request(self):
        proctor = ImageProctor()
        try:
            custom = FaceAngleThresholds(
                max_left_angle=20, max_right_angle=-20, max_up_angle=20, max_down_angle=-20
            )
            _analyze(proctor, custom)
            self.assertEqual(proctor.max_left_angle, 20)
            self.assertEqual(proctor.max_down_angle, -20)

            # 下一次请求不传参数，阈值必须回到默认，不能残留上次的自定义值。
            _analyze(proctor, None)
            self.assertEqual(proctor.max_left_angle, DEFAULT_MAX_LEFT_ANGLE)
            self.assertEqual(proctor.max_down_angle, DEFAULT_MAX_DOWN_ANGLE)
        finally:
            proctor.close()


if __name__ == "__main__":
    unittest.main()

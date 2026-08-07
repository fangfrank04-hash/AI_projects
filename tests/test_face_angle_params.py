import contextlib
import io
import unittest
from pathlib import Path

from PIL import Image

from app.core.config import Settings
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


class FaceDirectionBoundaryTest(unittest.TestCase):
    def test_classifies_each_direction_and_keeps_exact_boundaries_normal(self):
        proctor = ImageProctor(
            config=Settings(
                _env_file=None,
                max_left_angle=6,
                max_right_angle=-6,
                max_up_angle=6,
                max_down_angle=-0.5,
            )
        )
        try:
            self.assertEqual(1, proctor._classify_face_direction(0, -6.01))
            self.assertEqual(3, proctor._classify_face_direction(0, 6.01))
            self.assertEqual(2, proctor._classify_face_direction(-0.51, 0))
            self.assertEqual(4, proctor._classify_face_direction(6.01, 0))

            for pitch, yaw in ((0, -6), (0, 6), (-0.5, 0), (6, 0)):
                with self.subTest(pitch=pitch, yaw=yaw):
                    self.assertEqual(0, proctor._classify_face_direction(pitch, yaw))
        finally:
            proctor.close()

    def test_horizontal_direction_keeps_priority_over_vertical_direction(self):
        proctor = ImageProctor(config=Settings(_env_file=None))
        try:
            self.assertEqual(1, proctor._classify_face_direction(-100, -100))
            self.assertEqual(3, proctor._classify_face_direction(100, 100))
        finally:
            proctor.close()


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

    def test_injected_face_defaults_are_restored_after_request_override(self):
        config = Settings(
            _env_file=None,
            max_left_angle=12,
            max_right_angle=-11,
            max_up_angle=10,
            max_down_angle=-9,
        )
        proctor = ImageProctor(config=config)
        try:
            proctor._apply_face_angles(
                FaceAngleThresholds(
                    max_left_angle=20,
                    max_right_angle=-20,
                    max_up_angle=20,
                    max_down_angle=-20,
                )
            )
            proctor._apply_face_angles(None)

            self.assertEqual(12, proctor.max_left_angle)
            self.assertEqual(-11, proctor.max_right_angle)
            self.assertEqual(10, proctor.max_up_angle)
            self.assertEqual(-9, proctor.max_down_angle)
        finally:
            proctor.close()


if __name__ == "__main__":
    unittest.main()

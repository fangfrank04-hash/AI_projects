import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.proctor import ActionType


class SettingsLoadingTest(unittest.TestCase):
    def test_environment_overrides_dotenv(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "APP_NAME=from-file\nPORT=9100\nPHONE_ARM_ANGLE=27\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"PORT": "9200"}, clear=True):
                config = Settings(_env_file=env_path)

        self.assertEqual("from-file", config.app_name)
        self.assertEqual(9200, config.port)
        self.assertEqual(27, config.phone_arm_angle)

    def test_current_runtime_defaults_are_the_single_source_of_truth(self):
        with patch.dict(os.environ, {}, clear=True):
            config = Settings(_env_file=None)

        self.assertEqual(0.55, config.phone_wrist_ear_dist)
        self.assertEqual(30, config.phone_arm_angle)
        self.assertEqual(140, config.stretch_arm_angle)
        self.assertEqual(155, config.horizontal_stretch_arm_angle)
        self.assertEqual(0.4, config.horizontal_stretch_visibility)
        self.assertEqual(1.05, config.horizontal_stretch_arm_length)
        self.assertEqual(1.6, config.horizontal_stretch_wrist_ear_dist)
        self.assertEqual(0.25, config.elbow_stretch_visibility)
        self.assertEqual(0.5, config.elbow_stretch_max_dy)
        self.assertEqual(0.7, config.elbow_stretch_min_reach)
        self.assertEqual(0.25, config.turn_body_shoulder_dist)
        self.assertEqual(0.05, config.seated_turn_max_hip_visibility)
        self.assertEqual(0.5, config.visibility_threshold)

    def test_seated_turn_has_a_machine_readable_action_type(self):
        self.assertEqual("seated_turn", ActionType.SEATED_TURN.value)


class SettingsValidationTest(unittest.TestCase):
    def test_invalid_values_fail_at_startup(self):
        invalid_values = (
            {"port": 0},
            {"port": 65536},
            {"log_level": "verbose"},
            {"multi_person_pose_confidence": 1.1},
            {"visibility_threshold": -0.1},
            {"seated_turn_max_hip_visibility": -0.01},
            {"seated_turn_max_hip_visibility": 1.01},
            {"proctor_pool_size": 0},
            {"multi_person_max_poses": 0},
        )

        with patch.dict(os.environ, {}, clear=True):
            for values in invalid_values:
                with self.subTest(values=values):
                    with self.assertRaises(ValidationError):
                        Settings(_env_file=None, **values)

    def test_log_level_is_normalized(self):
        with patch.dict(os.environ, {}, clear=True):
            config = Settings(_env_file=None, log_level="warning")

        self.assertEqual("WARNING", config.log_level)


if __name__ == "__main__":
    unittest.main()

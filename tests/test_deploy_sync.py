import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


class SplitDeploymentSyncTest(unittest.TestCase):
    def test_runtime_configuration_sources_match(self):
        pairs = (
            (
                ROOT_DIR / "app" / "core" / "config.py",
                ROOT_DIR / "deploy_split" / "code" / "app" / "core" / "config.py",
            ),
            (
                ROOT_DIR / "app" / "ml" / "image_proctor.py",
                ROOT_DIR / "deploy_split" / "code" / "app" / "ml" / "image_proctor.py",
            ),
            (
                ROOT_DIR / "app" / "schemas" / "proctor.py",
                ROOT_DIR / "deploy_split" / "code" / "app" / "schemas" / "proctor.py",
            ),
            (
                ROOT_DIR / "app" / "api" / "v1" / "proctor.py",
                ROOT_DIR / "deploy_split" / "code" / "app" / "api" / "v1" / "proctor.py",
            ),
            (
                ROOT_DIR / ".env.example",
                ROOT_DIR / "deploy_split" / ".env.example",
            ),
        )

        for primary, deployment in pairs:
            with self.subTest(file=primary.name):
                self.assertEqual(primary.read_bytes(), deployment.read_bytes())


if __name__ == "__main__":
    unittest.main()

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("docker"), "Docker CLI is required")
class ComposeEnvironmentTest(unittest.TestCase):
    def test_optional_dotenv_reaches_both_container_deployments(self):
        compose_files = (
            ROOT_DIR / "docker-compose.yml",
            ROOT_DIR / "deploy_split" / "docker-compose.yml",
        )

        for source in compose_files:
            with self.subTest(compose=source.relative_to(ROOT_DIR)):
                with tempfile.TemporaryDirectory() as tmp:
                    temp_dir = Path(tmp)
                    compose_path = temp_dir / "docker-compose.yml"
                    compose_path.write_bytes(source.read_bytes())
                    (temp_dir / ".env").write_text(
                        "SEATED_TURN_MAX_HIP_VISIBILITY=0.03\nLOG_LEVEL=DEBUG\n",
                        encoding="utf-8",
                    )

                    completed = subprocess.run(
                        [
                            "docker",
                            "compose",
                            "-f",
                            str(compose_path),
                            "config",
                            "--format",
                            "json",
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    config = json.loads(completed.stdout)
                    environment = config["services"]["aiproctor"]["environment"]

                    self.assertEqual(
                        "0.03", environment["SEATED_TURN_MAX_HIP_VISIBILITY"]
                    )
                    self.assertEqual("INFO", environment["LOG_LEVEL"])


if __name__ == "__main__":
    unittest.main()

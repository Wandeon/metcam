import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestDeploySafeScriptContracts(unittest.TestCase):
    def test_deploy_safe_script_exists_and_is_bash(self) -> None:
        script = ROOT / "deploy" / "deploy-safe.sh"
        self.assertTrue(script.exists())
        header = script.read_text(encoding="utf-8").splitlines()[0]
        self.assertIn("bash", header)

    def test_deploy_safe_script_preserves_config_key_path(self) -> None:
        script = (ROOT / "deploy" / "deploy-safe.sh").read_text(encoding="utf-8")
        self.assertIn("CONFIG_REL_PATH=\"config/camera_config.json\"", script)
        self.assertIn("restore_config", script)
        self.assertIn("backup_config", script)

    def test_deploy_safe_script_runs_health_and_recording_smoke(self) -> None:
        script = (ROOT / "deploy" / "deploy-safe.sh").read_text(encoding="utf-8")
        self.assertIn("/health", script)
        self.assertIn("/recording?force=true", script)
        self.assertIn("run_recording_smoke", script)


if __name__ == "__main__":
    unittest.main()

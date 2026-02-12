import argparse
import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


def load_matrix_module():
    module_name = f"recording_matrix_{time.time_ns()}"
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "run_recording_regression_matrix.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if not spec or not spec.loader:
        raise RuntimeError("Could not load run_recording_regression_matrix.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRecordingRegressionMatrix(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_matrix_module()

    def _build_args(self, config_path: Path, output_dir: Path, presets: str = "fast") -> argparse.Namespace:
        return argparse.Namespace(
            api_base_url="http://localhost:8000/api/v1",
            config_path=str(config_path),
            output_dir=str(output_dir),
            restart_cmd="",
            presets=presets,
            duration_seconds=0.5,
            sample_interval_seconds=0.1,
            min_fps=24.0,
            max_cpu_p95=95.0,
        )

    def test_parse_avg_frame_rate(self) -> None:
        self.assertEqual(self.module.parse_avg_frame_rate("30/1"), 30.0)
        self.assertEqual(self.module.parse_avg_frame_rate("30000/1001"), 30000 / 1001)
        self.assertIsNone(self.module.parse_avg_frame_rate("0/0"))
        self.assertIsNone(self.module.parse_avg_frame_rate("N/A"))
        self.assertIsNone(self.module.parse_avg_frame_rate("abc"))

    def test_percentile_interpolation(self) -> None:
        values = [10.0, 20.0, 30.0, 40.0]
        self.assertEqual(self.module.percentile(values, 0), 10.0)
        self.assertEqual(self.module.percentile(values, 100), 40.0)
        self.assertEqual(self.module.percentile(values, 50), 25.0)
        self.assertIsNone(self.module.percentile([], 95))

    def test_runner_rejects_unsupported_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "camera_config.json"
            config_path.write_text(json.dumps({"recording_quality": "fast"}) + "\n", encoding="utf-8")
            args = self._build_args(config_path=config_path, output_dir=root / "out", presets="fast,ultra")
            runner = self.module.MatrixRunner(args)
            with self.assertRaises(ValueError):
                runner.run()

    def test_runner_exit_code_on_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "camera_config.json"
            config_path.write_text(json.dumps({"recording_quality": "fast"}) + "\n", encoding="utf-8")
            output_dir = root / "out"
            args = self._build_args(config_path=config_path, output_dir=output_dir, presets="fast")
            runner = self.module.MatrixRunner(args)

            with (
                mock.patch.object(runner, "_wait_for_health", return_value=None),
                mock.patch.object(runner, "_stop_any_active_recording", return_value=None),
                mock.patch.object(runner, "_restart_service", return_value=None),
                mock.patch.object(
                    runner,
                    "_run_one_preset",
                    return_value={"preset": "fast", "match_id": "m1", "pass": False, "failures": ["stop_failed"]},
                ),
            ):
                exit_code = runner.run()

            self.assertEqual(exit_code, 1)
            reports = list(output_dir.glob("recording-matrix-*.json"))
            self.assertEqual(len(reports), 1)

    def test_runner_exit_code_when_all_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "camera_config.json"
            config_path.write_text(json.dumps({"recording_quality": "fast"}) + "\n", encoding="utf-8")
            output_dir = root / "out"
            args = self._build_args(config_path=config_path, output_dir=output_dir, presets="fast")
            runner = self.module.MatrixRunner(args)

            with (
                mock.patch.object(runner, "_wait_for_health", return_value=None),
                mock.patch.object(runner, "_stop_any_active_recording", return_value=None),
                mock.patch.object(runner, "_restart_service", return_value=None),
                mock.patch.object(
                    runner,
                    "_run_one_preset",
                    return_value={"preset": "fast", "match_id": "m1", "pass": True, "failures": []},
                ),
            ):
                exit_code = runner.run()

            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()

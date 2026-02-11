import importlib.util
import json
import os
import sys
import tempfile
import time
import types
import unittest
from datetime import datetime
from pathlib import Path


class FakePipelineState:
    def __init__(self, value: str) -> None:
        self.value = value


class FakePipelineStatus:
    def __init__(self, state: str = "running", start_time: datetime | None = None) -> None:
        self.state = FakePipelineState(state)
        self.start_time = start_time or datetime.utcnow()


class FakeGStreamerManager:
    def __init__(self) -> None:
        self.create_results: dict[str, bool] = {}
        self.start_results: dict[str, bool] = {}
        self.stop_results: dict[str, bool] = {}
        self.statuses: dict[str, FakePipelineStatus] = {}
        self.create_calls: list[str] = []
        self.start_calls: list[str] = []
        self.stop_calls: list[str] = []
        self.remove_calls: list[str] = []

    def create_pipeline(self, name, pipeline_description, on_eos, on_error, metadata):
        self.create_calls.append(name)
        ok = self.create_results.get(name, True)
        if ok:
            self.statuses[name] = FakePipelineStatus(state="created")
        return ok

    def start_pipeline(self, name):
        self.start_calls.append(name)
        ok = self.start_results.get(name, True)
        if ok and name in self.statuses:
            self.statuses[name] = FakePipelineStatus(state="running")
        return ok

    def stop_pipeline(self, name, wait_for_eos=True, timeout=5.0):
        self.stop_calls.append(name)
        ok = self.stop_results.get(name, True)
        if ok:
            self.statuses.pop(name, None)
        return ok

    def remove_pipeline(self, name):
        self.remove_calls.append(name)
        self.statuses.pop(name, None)
        return True

    def get_pipeline_status(self, name):
        return self.statuses.get(name)


def load_recording_service_module():
    # Stub dependencies that require Jetson runtime libraries.
    gm_stub = types.ModuleType("gstreamer_manager")
    gm_stub.GStreamerManager = FakeGStreamerManager
    sys.modules["gstreamer_manager"] = gm_stub

    pb_stub = types.ModuleType("pipeline_builders")
    pb_stub.build_recording_pipeline = lambda camera_id, output_pattern, config_path=None, quality_preset="high": (
        f"pipeline-cam{camera_id}-{quality_preset}-{output_pattern}"
    )
    pb_stub.load_camera_config = lambda config_path=None: {"recording_quality": "high"}
    sys.modules["pipeline_builders"] = pb_stub

    module_name = f"recording_service_test_{time.time_ns()}"
    module_path = Path(__file__).resolve().parents[1] / "src/video-pipeline/recording_service.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if not spec or not spec.loader:
        raise RuntimeError("Could not load recording_service module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class TestRecordingService(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_recording_service_module()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.service = self.module.RecordingService(base_recordings_dir=self.temp_dir.name)
        self.service.gst_manager = FakeGStreamerManager()
        self.service.state_file = Path(self.temp_dir.name) / "recording_state.json"
        self.service._clear_state()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_start_recording_partial_camera_success(self) -> None:
        self.service.gst_manager.create_results["recording_cam1"] = False

        result = self.service.start_recording("match_partial", process_after_recording=False)

        self.assertTrue(result["success"])
        self.assertEqual(result["match_id"], "match_partial")
        self.assertEqual(result["cameras_started"], [0])
        self.assertEqual(result["cameras_failed"], [1])
        self.assertEqual(self.service.current_match_id, "match_partial")

    def test_start_recording_all_failures(self) -> None:
        self.service.gst_manager.start_results["recording_cam0"] = False
        self.service.gst_manager.start_results["recording_cam1"] = False

        result = self.service.start_recording("match_fail", process_after_recording=False)

        self.assertFalse(result["success"])
        self.assertIn("Failed to start any cameras", result["message"])
        self.assertEqual(self.service.current_match_id, None)

    def test_stop_recording_protection_and_force(self) -> None:
        start = self.service.start_recording("match_protected", process_after_recording=False)
        self.assertTrue(start["success"])

        protected_stop = self.service.stop_recording(force=False)
        self.assertFalse(protected_stop["success"])
        self.assertTrue(protected_stop.get("protected"))

        force_stop = self.service.stop_recording(force=True)
        self.assertTrue(force_stop["success"])
        self.assertEqual(self.service.current_match_id, None)

    def test_stop_recording_triggers_post_processing_when_enabled(self) -> None:
        calls: list[str] = []
        post_stub = types.ModuleType("post_processing_service")

        class _PostService:
            def process_recording_async(self, match_id):
                calls.append(match_id)

        post_stub.get_post_processing_service = lambda: _PostService()
        sys.modules["post_processing_service"] = post_stub

        start = self.service.start_recording("match_post", process_after_recording=True)
        self.assertTrue(start["success"])
        # Simulate elapsed time so non-force stop passes protection.
        self.service.recording_start_time = time.time() - 20

        stop = self.service.stop_recording(force=False)
        self.assertTrue(stop["success"])
        self.assertEqual(calls, ["match_post"])

    def test_get_status_contains_duration_and_protected_flag(self) -> None:
        start = self.service.start_recording("match_status", process_after_recording=False)
        self.assertTrue(start["success"])

        status = self.service.get_status()
        self.assertTrue(status["recording"])
        self.assertEqual(status["match_id"], "match_status")
        self.assertIn("duration", status)
        self.assertIn("protected", status)
        self.assertTrue(status["protected"])

    def test_save_and_load_state_restores_active_recording(self) -> None:
        self.service.current_match_id = "match_state"
        self.service.recording_start_time = time.time() - 30
        self.service.process_after_recording = True
        self.service._save_state()

        second = self.module.RecordingService(base_recordings_dir=self.temp_dir.name)
        second.gst_manager = FakeGStreamerManager()
        second.state_file = self.service.state_file
        second.gst_manager.statuses["recording_cam0"] = FakePipelineStatus(state="running")
        second.gst_manager.statuses["recording_cam1"] = FakePipelineStatus(state="running")
        second._load_state()

        self.assertEqual(second.current_match_id, "match_state")
        self.assertTrue(second.process_after_recording)

        saved = json.loads(self.service.state_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["match_id"], "match_state")
        self.assertTrue(saved["process_after_recording"])

    def test_check_recording_health_no_active_recording(self) -> None:
        health = self.service.check_recording_health()
        self.assertTrue(health["healthy"])
        self.assertIn("No active recording", health["message"])

    def test_check_recording_health_detects_missing_segments_after_grace_period(self) -> None:
        match_id = "match_missing_segments"
        segments_dir = Path(self.temp_dir.name) / match_id / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)

        self.service.current_match_id = match_id
        self.service.recording_start_time = time.time() - 20

        health = self.service.check_recording_health()
        self.assertFalse(health["healthy"])
        self.assertIn("No segments after 10 seconds", health["message"])

    def test_check_recording_health_detects_zero_byte_segments(self) -> None:
        match_id = "match_zero_byte"
        segments_dir = Path(self.temp_dir.name) / match_id / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)

        cam0 = segments_dir / "cam0_test_00.mp4"
        cam1 = segments_dir / "cam1_test_00.mp4"
        cam0.write_bytes(b"")
        cam1.write_bytes(b"x" * (1024 * 1024 + 1))

        stale = time.time() - 20
        os.utime(cam0, (stale, stale))
        os.utime(cam1, (stale, stale))

        self.service.current_match_id = match_id
        self.service.recording_start_time = time.time() - 40

        health = self.service.check_recording_health()
        self.assertFalse(health["healthy"])
        self.assertIn("cam0: Zero-byte file", health["message"])
        self.assertIn("issues", health)

    def test_check_recording_health_is_healthy_with_fresh_segments(self) -> None:
        match_id = "match_healthy"
        segments_dir = Path(self.temp_dir.name) / match_id / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)
        (segments_dir / "cam0_test_00.mp4").write_bytes(b"x" * 512)
        (segments_dir / "cam1_test_00.mp4").write_bytes(b"x" * 512)

        self.service.current_match_id = match_id
        self.service.recording_start_time = time.time() - 5

        health = self.service.check_recording_health()
        self.assertTrue(health["healthy"])
        self.assertIn("healthy", health["message"].lower())


if __name__ == "__main__":
    unittest.main()

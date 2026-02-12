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
from unittest import mock


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
        self.stop_timeout_flags: dict[str, bool] = {}
        self.stop_timeouts: dict[str, list[float]] = {}
        self.statuses: dict[str, FakePipelineStatus] = {}
        self.create_calls: list[str] = []
        self.start_calls: list[str] = []
        self.stop_calls: list[str] = []
        self.remove_calls: list[str] = []
        self.on_error_callbacks: dict[str, object] = {}
        self.on_eos_callbacks: dict[str, object] = {}
        self.metadata: dict[str, dict] = {}

    def create_pipeline(self, name, pipeline_description, on_eos, on_error, metadata):
        self.create_calls.append(name)
        ok = self.create_results.get(name, True)
        if ok:
            self.statuses[name] = FakePipelineStatus(state="created")
            self.on_error_callbacks[name] = on_error
            self.on_eos_callbacks[name] = on_eos
            self.metadata[name] = metadata
        return ok

    def start_pipeline(self, name):
        self.start_calls.append(name)
        ok = self.start_results.get(name, True)
        if ok and name in self.statuses:
            self.statuses[name] = FakePipelineStatus(state="running")
        return ok

    def stop_pipeline(self, name, wait_for_eos=True, timeout=5.0):
        details = self.stop_pipeline_with_details(name, wait_for_eos=wait_for_eos, timeout=timeout)
        return details["success"]

    def stop_pipeline_with_details(self, name, wait_for_eos=True, timeout=5.0):
        self.stop_calls.append(name)
        self.stop_timeouts.setdefault(name, []).append(timeout)
        ok = self.stop_results.get(name, True)
        timed_out = bool(wait_for_eos and self.stop_timeout_flags.get(name, False))
        if ok:
            self.statuses.pop(name, None)
        return {
            "success": ok,
            "eos_received": bool(ok and wait_for_eos and not timed_out),
            "timed_out": timed_out,
            "error": None if ok else "stop failed",
        }

    def remove_pipeline(self, name):
        self.remove_calls.append(name)
        self.statuses.pop(name, None)
        self.on_error_callbacks.pop(name, None)
        self.on_eos_callbacks.pop(name, None)
        self.metadata.pop(name, None)
        return True

    def get_pipeline_status(self, name):
        return self.statuses.get(name)

    def emit_error(self, name, error="boom", debug="debug"):
        callback = self.on_error_callbacks.get(name)
        if callback is None:
            raise AssertionError(f"No error callback registered for {name}")
        callback(name, error, debug, self.metadata.get(name, {}))


def wait_for(condition, timeout=1.0, interval=0.01):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return condition()


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
        self.service.overload_guard_enabled = False
        self.service.state_file = Path(self.temp_dir.name) / "recording_state.json"
        self.service._clear_state()

    def tearDown(self) -> None:
        try:
            self.service._stop_overload_guard()  # type: ignore[attr-defined]
        except Exception:
            pass
        self.temp_dir.cleanup()

    def _mark_recording_pipelines_running(self) -> None:
        for cam_id in self.service.camera_ids:
            self.service.gst_manager.statuses[f"recording_cam{cam_id}"] = FakePipelineStatus(state="running")

    def test_start_recording_partial_camera_rolls_back_when_strict_mode_enabled(self) -> None:
        self.service.gst_manager.create_results["recording_cam1"] = False

        result = self.service.start_recording("match_partial", process_after_recording=False)

        self.assertFalse(result["success"])
        self.assertIn("Failed to start all required cameras", result["message"])
        self.assertEqual(result["cameras_started"], [])
        self.assertEqual(result["cameras_failed"], [1])
        self.assertEqual(self.service.current_match_id, None)
        self.assertTrue(result["require_all_cameras"])
        self.assertIn("recording_cam0", self.service.gst_manager.remove_calls)

    def test_start_recording_partial_camera_success_when_strict_mode_disabled(self) -> None:
        self.service.require_all_cameras = False
        self.service.gst_manager.create_results["recording_cam1"] = False

        result = self.service.start_recording("match_partial", process_after_recording=False)

        self.assertTrue(result["success"])
        self.assertEqual(result["match_id"], "match_partial")
        self.assertEqual(result["cameras_started"], [0])
        self.assertEqual(result["cameras_failed"], [1])
        self.assertEqual(self.service.current_match_id, "match_partial")
        self.assertFalse(result["require_all_cameras"])

    def test_pipeline_error_auto_recovers_camera(self) -> None:
        self.service.max_recovery_attempts = 1
        self.service.recovery_backoff_seconds = 0.0
        start = self.service.start_recording("match_recover", process_after_recording=False)
        self.assertTrue(start["success"])

        self.service.gst_manager.emit_error("recording_cam0", error="encoder-fault", debug="simulated")

        self.assertTrue(
            wait_for(lambda: self.service.gst_manager.start_calls.count("recording_cam0") >= 2),
            "Camera recovery did not restart cam0 pipeline",
        )

        status = self.service.get_status()
        self.assertFalse(status["degraded"])
        self.assertIsNone(status["camera_recovery"]["camera_0"]["last_error"])
        self.assertEqual(status["camera_recovery"]["camera_0"]["attempts"], 1)

    def test_pipeline_error_marks_degraded_after_recovery_exhausted(self) -> None:
        self.service.max_recovery_attempts = 1
        self.service.recovery_backoff_seconds = 0.0
        start = self.service.start_recording("match_degraded", process_after_recording=False)
        self.assertTrue(start["success"])

        # Force recovery create failure after initial successful startup.
        self.service.gst_manager.create_results["recording_cam0"] = False
        self.service.gst_manager.emit_error("recording_cam0", error="fatal-camera-error", debug="simulated")

        self.assertTrue(
            wait_for(lambda: self.service.get_status()["degraded"]),
            "Recording never reached degraded state after failed recovery",
        )

        status = self.service.get_status()
        self.assertTrue(status["degraded"])
        self.assertIn("camera_0", status["degraded_cameras"])
        self.assertTrue(status["camera_recovery"]["camera_0"]["failed_permanently"])

    def test_start_recording_all_failures(self) -> None:
        self.service.gst_manager.start_results["recording_cam0"] = False
        self.service.gst_manager.start_results["recording_cam1"] = False

        result = self.service.start_recording("match_fail", process_after_recording=False)

        self.assertFalse(result["success"])
        self.assertIn("Failed to start all required cameras", result["message"])
        self.assertEqual(self.service.current_match_id, None)

    def test_load_recording_policy_reads_integrity_probe_timeout(self) -> None:
        self.module.load_camera_config = lambda config_path=None: {  # type: ignore[assignment]
            "recording_quality": "high",
            "recording_integrity_probe_timeout_seconds": 11.25,
        }

        self.service._load_recording_policy()

        self.assertEqual(self.service.integrity_probe_timeout_seconds, 11.25)

    def test_load_recording_policy_reads_overload_guard_thresholds(self) -> None:
        self.module.load_camera_config = lambda config_path=None: {  # type: ignore[assignment]
            "recording_quality": "high",
            "recording_overload_guard_enabled": True,
            "recording_overload_cpu_percent_threshold": 88.5,
            "recording_overload_poll_interval_seconds": 4.0,
            "recording_overload_unhealthy_streak_threshold": 5,
        }

        self.service._load_recording_policy()

        self.assertTrue(self.service.overload_guard_enabled)
        self.assertEqual(self.service.overload_guard_cpu_percent_threshold, 88.5)
        self.assertEqual(self.service.overload_guard_poll_interval_seconds, 4.0)
        self.assertEqual(self.service.overload_guard_unhealthy_streak_threshold, 5)

    def test_probe_segment_integrity_uses_metadata_probe_and_configured_timeout(self) -> None:
        segment = Path(self.temp_dir.name) / "probe_target.mp4"
        segment.write_bytes(b"probe-bytes")
        self.service.integrity_probe_timeout_seconds = 7.5

        probe_stdout = json.dumps(
            {
                "streams": [{"codec_name": "h264", "avg_frame_rate": "30/1"}],
                "format": {"duration": "12.3", "size": "999", "bit_rate": "1000"},
            }
        )
        completed = types.SimpleNamespace(returncode=0, stdout=probe_stdout, stderr="")

        with mock.patch.object(self.module.shutil, "which", return_value="/usr/bin/ffprobe"), mock.patch.object(
            self.module.subprocess, "run", return_value=completed
        ) as run_mock:
            result = self.service._probe_segment_integrity(segment, time.time())

        called_cmd = run_mock.call_args.args[0]
        self.assertNotIn("-count_frames", called_cmd)
        self.assertEqual(run_mock.call_args.kwargs["timeout"], 7.5)
        self.assertTrue(result["checked"])
        self.assertTrue(result["ok"])
        self.assertNotIn("nb_read_frames", result)

    def test_overload_guard_triggers_after_sustained_unhealthy_samples(self) -> None:
        self.service.overload_guard_unhealthy_streak_threshold = 2
        self.service.overload_guard_cpu_percent_threshold = 90.0

        first = self.service._ingest_overload_sample(
            95.0,
            {"healthy": False, "issues": ["cam0: Segment not growing"], "message": "cam0 unhealthy"},
            now=time.time(),
        )
        self.assertFalse(first["active"])
        self.assertEqual(first["unhealthy_streak"], 1)

        second = self.service._ingest_overload_sample(
            94.0,
            {"healthy": False, "issues": ["cam0: Segment not growing"], "message": "cam0 unhealthy"},
            now=time.time() + 1.0,
        )
        self.assertTrue(second["active"])
        self.assertEqual(second["unhealthy_streak"], 2)
        self.assertIn("overload_guard", self.service.degraded_cameras)

    def test_overload_guard_clears_after_healthy_sample(self) -> None:
        self.service.overload_guard_unhealthy_streak_threshold = 1
        self.service.overload_guard_cpu_percent_threshold = 90.0

        triggered = self.service._ingest_overload_sample(
            95.0,
            {"healthy": False, "issues": ["cam1: Pipeline state error"], "message": "cam1 unhealthy"},
            now=time.time(),
        )
        self.assertTrue(triggered["active"])
        self.assertIn("overload_guard", self.service.degraded_cameras)

        cleared = self.service._ingest_overload_sample(
            35.0,
            {"healthy": True, "message": "Recording healthy"},
            now=time.time() + 1.0,
        )
        self.assertFalse(cleared["active"])
        self.assertEqual(cleared["unhealthy_streak"], 0)
        self.assertNotIn("overload_guard", self.service.degraded_cameras)

    def test_status_includes_overload_guard_state(self) -> None:
        idle_status = self.service.get_status()
        self.assertIn("overload_guard", idle_status)
        self.assertIn("active", idle_status["overload_guard"])

    def test_stop_recording_protection_and_force(self) -> None:
        start = self.service.start_recording("match_protected", process_after_recording=False)
        self.assertTrue(start["success"])

        protected_stop = self.service.stop_recording(force=False)
        self.assertFalse(protected_stop["success"])
        self.assertTrue(protected_stop.get("protected"))

        force_stop = self.service.stop_recording(force=True)
        self.assertTrue(force_stop["success"])
        self.assertEqual(self.service.current_match_id, None)

    def test_stop_recording_returns_graceful_stop_metadata(self) -> None:
        start = self.service.start_recording("match_stop_metadata", process_after_recording=False)
        self.assertTrue(start["success"])
        self.service.recording_start_time = time.time() - 20

        stop = self.service.stop_recording(force=False)
        self.assertTrue(stop["success"])
        self.assertTrue(stop["transport_success"])
        self.assertTrue(stop["graceful_stop"])
        self.assertIn("camera_0", stop["camera_stop_results"])
        self.assertIn("camera_1", stop["camera_stop_results"])
        self.assertTrue(stop["camera_stop_results"]["camera_0"]["eos_received"])
        self.assertTrue(stop["camera_stop_results"]["camera_0"]["finalized"])
        self.assertFalse(stop["camera_stop_results"]["camera_0"]["timed_out"])
        self.assertIn("integrity", stop)
        self.assertIn("cameras", stop["integrity"])

    def test_stop_recording_timeout_reports_non_graceful_and_respects_timeout_setting(self) -> None:
        self.service.stop_eos_timeout_seconds = 9.5
        start = self.service.start_recording("match_stop_timeout", process_after_recording=False)
        self.assertTrue(start["success"])
        self.service.recording_start_time = time.time() - 20
        self.service.gst_manager.stop_timeout_flags["recording_cam1"] = True

        stop = self.service.stop_recording(force=False)
        self.assertFalse(stop["success"])
        self.assertTrue(stop["transport_success"])
        self.assertFalse(stop["graceful_stop"])
        self.assertFalse(stop["camera_stop_results"]["camera_1"]["finalized"])
        self.assertTrue(stop["camera_stop_results"]["camera_1"]["timed_out"])
        self.assertIn("finalization was incomplete", stop["message"])
        self.assertEqual(self.service.gst_manager.stop_timeouts["recording_cam0"][-1], 9.5)
        self.assertEqual(self.service.gst_manager.stop_timeouts["recording_cam1"][-1], 9.5)

    def test_stop_recording_integrity_gate_marks_failure_on_probe_error(self) -> None:
        match_id = "match_integrity_fail"
        start = self.service.start_recording(match_id, process_after_recording=False)
        self.assertTrue(start["success"])
        self.service.recording_start_time = time.time() - 20

        segments_dir = Path(self.temp_dir.name) / match_id / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)
        (segments_dir / "cam0_20260212_000000_00.mp4").write_bytes(b"cam0")
        (segments_dir / "cam1_20260212_000000_00.mp4").write_bytes(b"cam1")

        def probe(path: Path, now: float) -> dict:
            if "cam0_" in path.name:
                return {"checked": True, "ok": False, "error": "moov atom not found", "cached": False}
            return {"checked": True, "ok": True, "error": None, "cached": False}

        self.service._probe_segment_integrity = probe  # type: ignore[method-assign]

        stop = self.service.stop_recording(force=False)
        self.assertFalse(stop["success"])
        self.assertTrue(stop["transport_success"])
        self.assertTrue(stop["graceful_stop"])
        self.assertIn("integrity checks failed", stop["message"])
        self.assertFalse(stop["integrity"]["all_ok"])
        self.assertFalse(stop["camera_stop_results"]["camera_0"]["integrity_ok"])
        self.assertEqual(stop["camera_stop_results"]["camera_0"]["integrity_error"], "moov atom not found")

    def test_stop_recording_integrity_gate_passes_when_all_probes_ok(self) -> None:
        match_id = "match_integrity_ok"
        start = self.service.start_recording(match_id, process_after_recording=False)
        self.assertTrue(start["success"])
        self.service.recording_start_time = time.time() - 20

        segments_dir = Path(self.temp_dir.name) / match_id / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)
        (segments_dir / "cam0_20260212_000000_00.mp4").write_bytes(b"cam0")
        (segments_dir / "cam1_20260212_000000_00.mp4").write_bytes(b"cam1")

        self.service._probe_segment_integrity = lambda path, now: {  # type: ignore[method-assign]
            "checked": True,
            "ok": True,
            "error": None,
            "cached": False,
        }

        stop = self.service.stop_recording(force=False)
        self.assertTrue(stop["success"])
        self.assertTrue(stop["integrity"]["checked"])
        self.assertTrue(stop["integrity"]["all_ok"])
        self.assertTrue(stop["camera_stop_results"]["camera_0"]["integrity_ok"])
        self.assertTrue(stop["camera_stop_results"]["camera_1"]["integrity_ok"])

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

    def test_save_state_uses_atomic_replace_and_cleans_temp_file(self) -> None:
        self.service.current_match_id = "match_atomic"
        self.service.recording_start_time = time.time() - 5
        self.service.process_after_recording = False

        self.service._save_state()

        self.assertTrue(self.service.state_file.exists())
        tmp_state_file = self.service.state_file.with_name(f"{self.service.state_file.name}.tmp")
        self.assertFalse(tmp_state_file.exists())

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
        self._mark_recording_pipelines_running()

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
        self._mark_recording_pipelines_running()

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
        self._mark_recording_pipelines_running()

        health = self.service.check_recording_health()
        self.assertTrue(health["healthy"])
        self.assertIn("healthy", health["message"].lower())

    def test_check_recording_health_detects_missing_camera_segments(self) -> None:
        match_id = "match_missing_cam1"
        segments_dir = Path(self.temp_dir.name) / match_id / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)
        (segments_dir / "cam0_test_00.mp4").write_bytes(b"x" * (1024 * 1024 + 1))

        self.service.current_match_id = match_id
        self.service.recording_start_time = time.time() - 30
        self._mark_recording_pipelines_running()

        health = self.service.check_recording_health()
        self.assertFalse(health["healthy"])
        self.assertIn("cam1: No segment files after 20 seconds", health["message"])

    def test_check_recording_health_detects_pipeline_state_error(self) -> None:
        match_id = "match_pipeline_error"
        segments_dir = Path(self.temp_dir.name) / match_id / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)
        (segments_dir / "cam0_test_00.mp4").write_bytes(b"x" * (1024 * 1024 + 1))
        (segments_dir / "cam1_test_00.mp4").write_bytes(b"x" * (1024 * 1024 + 1))

        self.service.current_match_id = match_id
        self.service.recording_start_time = time.time() - 40
        self._mark_recording_pipelines_running()
        self.service.gst_manager.statuses["recording_cam0"] = FakePipelineStatus(state="error")

        health = self.service.check_recording_health()
        self.assertFalse(health["healthy"])
        self.assertIn("cam0: Pipeline state error", health["message"])

    def test_check_recording_health_detects_non_growing_segment(self) -> None:
        match_id = "match_stalled_segment"
        segments_dir = Path(self.temp_dir.name) / match_id / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)
        cam0 = segments_dir / "cam0_test_00.mp4"
        cam1 = segments_dir / "cam1_test_00.mp4"
        cam0.write_bytes(b"x" * (1024 * 1024 + 10))
        cam1.write_bytes(b"x" * (1024 * 1024 + 10))
        stale = time.time() - 30
        os.utime(cam0, (stale, stale))
        os.utime(cam1, (stale, stale))

        self.service.current_match_id = match_id
        self.service.recording_start_time = time.time() - 60
        self._mark_recording_pipelines_running()

        first = self.service.check_recording_health()
        self.assertTrue(first["healthy"])
        self.service.health_last_segment_snapshot[0]["checked_at"] = time.time() - 25
        self.service.health_last_segment_snapshot[1]["checked_at"] = time.time() - 25

        second = self.service.check_recording_health()
        self.assertFalse(second["healthy"])
        self.assertIn("cam0: Segment not growing", second["message"])

    def test_check_recording_health_reports_probe_failure_for_stable_large_segment(self) -> None:
        match_id = "match_probe_failure"
        segments_dir = Path(self.temp_dir.name) / match_id / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)
        cam0 = segments_dir / "cam0_test_00.mp4"
        cam1 = segments_dir / "cam1_test_00.mp4"
        cam0.write_bytes(b"x" * (4 * 1024 * 1024 + 1024))
        cam1.write_bytes(b"x" * (4 * 1024 * 1024 + 1024))

        stale = time.time() - 40
        fresh = time.time() - 2
        os.utime(cam0, (stale, stale))
        os.utime(cam1, (fresh, fresh))

        self.service.current_match_id = match_id
        self.service.recording_start_time = time.time() - 80
        self._mark_recording_pipelines_running()
        self.service.health_last_segment_snapshot[0] = {
            "name": cam0.name,
            "size": cam0.stat().st_size,
            "mtime": cam0.stat().st_mtime,
            "index": 0,
            "checked_at": time.time() - 15,
        }

        self.service._probe_segment_integrity = lambda path, now: {
            "checked": True,
            "ok": False,
            "error": "simulated_probe_failure",
            "cached": False,
        }

        health = self.service.check_recording_health()
        self.assertFalse(health["healthy"])
        self.assertIn("cam0: Segment probe failed (simulated_probe_failure)", health["message"])
        self.assertIn("camera_diagnostics", health)
        self.assertTrue(health["camera_diagnostics"]["camera_0"]["integrity_probe"]["checked"])
        self.assertFalse(health["camera_diagnostics"]["camera_0"]["integrity_probe"]["ok"])


if __name__ == "__main__":
    unittest.main()

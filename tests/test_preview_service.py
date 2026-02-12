import importlib.util
import os
import shutil
import sys
import tempfile
import time
import types
import unittest
from datetime import datetime
from pathlib import Path


EVENT_LOG: list[str] = []


class _FakeState:
    def __init__(self, value: str) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _FakeState) and self.value == other.value


class _FakePipelineState:
    RUNNING = _FakeState("running")
    IDLE = _FakeState("idle")


class _FakePipelineStatus:
    def __init__(self, state: _FakeState, start_time: datetime | None = None) -> None:
        self.state = state
        self.start_time = start_time or datetime.utcnow()


class _FakeGStreamerManager:
    def __init__(self) -> None:
        self.statuses: dict[str, _FakePipelineStatus] = {}
        self.stop_calls: list[dict] = []

    def get_pipeline_status(self, name: str):
        return self.statuses.get(name)

    def create_pipeline(self, name, pipeline_description, on_eos, on_error, metadata):
        self.statuses[name] = _FakePipelineStatus(_FakePipelineState.IDLE)
        return True

    def start_pipeline(self, name):
        self.statuses[name] = _FakePipelineStatus(_FakePipelineState.RUNNING)
        return True

    def stop_pipeline(self, name, wait_for_eos=True, timeout=5.0):
        self.stop_calls.append(
            {
                "name": name,
                "wait_for_eos": wait_for_eos,
                "timeout": timeout,
            }
        )
        EVENT_LOG.append(f"stop:{name}:eos={wait_for_eos}")
        self.statuses[name] = _FakePipelineStatus(_FakePipelineState.IDLE)
        return True

    def remove_pipeline(self, name):
        self.statuses.pop(name, None)
        return True


class _FakeExposureService:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    def start(self):
        self.start_calls += 1
        EVENT_LOG.append("exposure:start")
        return True

    def stop(self):
        self.stop_calls += 1
        EVENT_LOG.append("exposure:stop")
        return True


def _load_preview_service_module():
    gm_stub = types.ModuleType("gstreamer_manager")
    gm_stub.GStreamerManager = _FakeGStreamerManager
    gm_stub.PipelineState = _FakePipelineState
    sys.modules["gstreamer_manager"] = gm_stub

    pb_stub = types.ModuleType("pipeline_builders")
    pb_stub.build_preview_pipeline = lambda camera_id, hls_location: f"pipeline-cam{camera_id}-{hls_location}"
    pb_stub.build_preview_rtsp_pipeline = lambda camera_id, config_path=None: f"( rtsp-pipeline-cam{camera_id} name=pay0 )"
    sys.modules["pipeline_builders"] = pb_stub

    exposure_stub = types.ModuleType("exposure_sync_service")
    exposure_stub._svc = _FakeExposureService()

    def _get_exposure_sync_service(_manager=None):
        return exposure_stub._svc

    exposure_stub.get_exposure_sync_service = _get_exposure_sync_service
    sys.modules["exposure_sync_service"] = exposure_stub

    module_name = f"preview_service_test_{time.time_ns()}"
    module_path = Path(__file__).resolve().parents[1] / "src/video-pipeline/preview_service.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if not spec or not spec.loader:
        raise RuntimeError("Could not load preview_service module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module, exposure_stub


class TestPreviewService(unittest.TestCase):
    def setUp(self) -> None:
        EVENT_LOG.clear()
        self.prev_transport_mode = os.environ.get("PREVIEW_TRANSPORT_MODE")
        self.prev_stun_server = os.environ.get("WEBRTC_STUN_SERVER")
        self.prev_turn_server = os.environ.get("WEBRTC_TURN_SERVER")
        self.prev_relay_url = os.environ.get("WEBRTC_RELAY_URL")
        os.environ["PREVIEW_TRANSPORT_MODE"] = "hls"
        os.environ["WEBRTC_STUN_SERVER"] = "stun://stun.l.google.com:19302"
        os.environ.pop("WEBRTC_TURN_SERVER", None)
        os.environ.pop("WEBRTC_RELAY_URL", None)
        self.module, self.exposure_stub = _load_preview_service_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.hls_dir = Path(self.tmp.name) / "hls"
        self.service = self.module.PreviewService(hls_base_dir=str(self.hls_dir))
        self.service.gst_manager = _FakeGStreamerManager()

    def tearDown(self) -> None:
        if self.prev_transport_mode is None:
            os.environ.pop("PREVIEW_TRANSPORT_MODE", None)
        else:
            os.environ["PREVIEW_TRANSPORT_MODE"] = self.prev_transport_mode
        if self.prev_stun_server is None:
            os.environ.pop("WEBRTC_STUN_SERVER", None)
        else:
            os.environ["WEBRTC_STUN_SERVER"] = self.prev_stun_server
        if self.prev_turn_server is None:
            os.environ.pop("WEBRTC_TURN_SERVER", None)
        else:
            os.environ["WEBRTC_TURN_SERVER"] = self.prev_turn_server
        if self.prev_relay_url is None:
            os.environ.pop("WEBRTC_RELAY_URL", None)
        else:
            os.environ["WEBRTC_RELAY_URL"] = self.prev_relay_url
        self.tmp.cleanup()

    def test_start_preview_recreates_hls_directory(self) -> None:
        shutil.rmtree(self.hls_dir, ignore_errors=True)
        self.assertFalse(self.hls_dir.exists())

        result = self.service.start_preview()

        self.assertTrue(result["success"])
        self.assertTrue(self.hls_dir.exists())

    def test_stop_preview_stops_exposure_before_pipeline_teardown(self) -> None:
        start = self.service.start_preview()
        self.assertTrue(start["success"])
        EVENT_LOG.clear()

        stop = self.service.stop_preview()

        self.assertTrue(stop["success"])
        stop_calls = self.service.gst_manager.stop_calls
        self.assertGreaterEqual(len(stop_calls), 2)
        self.assertTrue(all(call["wait_for_eos"] is False for call in stop_calls))
        self.assertIn("exposure:stop", EVENT_LOG)
        first_stop_index = next(i for i, entry in enumerate(EVENT_LOG) if entry.startswith("stop:"))
        exposure_stop_index = EVENT_LOG.index("exposure:stop")
        self.assertLess(exposure_stop_index, first_stop_index)

    def test_stop_single_camera_does_not_stop_exposure_service(self) -> None:
        start = self.service.start_preview()
        self.assertTrue(start["success"])
        EVENT_LOG.clear()

        stop = self.service.stop_preview(camera_id=0)

        self.assertTrue(stop["success"])
        self.assertNotIn("exposure:stop", EVENT_LOG)
        self.assertEqual(self.service.gst_manager.stop_calls[0]["name"], "preview_cam0")
        self.assertFalse(self.service.gst_manager.stop_calls[0]["wait_for_eos"])

    def test_get_ice_servers_returns_browser_compatible_stun_url(self) -> None:
        self.assertEqual(
            self.service.get_ice_servers(),
            [{"urls": ["stun:stun.l.google.com:19302"]}],
        )

    def test_get_ice_servers_parses_turn_credentials_for_browser(self) -> None:
        os.environ["WEBRTC_TURN_SERVER"] = "turn://user:pass@turn.example.com:3478?transport=udp"
        service = self.module.PreviewService(hls_base_dir=str(self.hls_dir))
        service.gst_manager = _FakeGStreamerManager()

        self.assertEqual(
            service.get_ice_servers(),
            [
                {"urls": ["stun:stun.l.google.com:19302"]},
                {
                    "urls": ["turn:turn.example.com:3478?transport=udp"],
                    "username": "user",
                    "credential": "pass",
                },
            ],
        )


    def test_relay_mode_status_includes_relay_block(self) -> None:
        os.environ["WEBRTC_RELAY_URL"] = "wss://vid.nk-otok.hr/go2rtc"
        service = self.module.PreviewService(hls_base_dir=str(self.hls_dir))
        service.gst_manager = _FakeGStreamerManager()

        status = service.get_status()

        self.assertIn("relay", status)
        self.assertTrue(status["relay"]["enabled"])
        self.assertEqual(status["relay"]["ws_url"], "wss://vid.nk-otok.hr/go2rtc")
        self.assertEqual(status["relay"]["ingest"], "rtsp")

    def test_relay_mode_resolves_webrtc_transport_to_internal_rtsp(self) -> None:
        os.environ["WEBRTC_RELAY_URL"] = "wss://vid.nk-otok.hr/go2rtc"
        service = self.module.PreviewService(hls_base_dir=str(self.hls_dir))
        service.gst_manager = _FakeGStreamerManager()

        # Relay mode: requested "webrtc" should resolve to "webrtc" (UI-facing)
        resolved = service._resolve_transport("webrtc")
        self.assertEqual(resolved, "webrtc")

    def test_relay_mode_default_transport_is_webrtc(self) -> None:
        os.environ["WEBRTC_RELAY_URL"] = "wss://vid.nk-otok.hr/go2rtc"
        service = self.module.PreviewService(hls_base_dir=str(self.hls_dir))
        service.gst_manager = _FakeGStreamerManager()

        # Default transport when relay is configured should be "webrtc"
        resolved = service._resolve_transport(None)
        self.assertEqual(resolved, "webrtc")

    def test_no_relay_mode_status_has_no_relay_block(self) -> None:
        os.environ.pop("WEBRTC_RELAY_URL", None)
        service = self.module.PreviewService(hls_base_dir=str(self.hls_dir))
        service.gst_manager = _FakeGStreamerManager()

        status = service.get_status()
        self.assertIsNone(status.get("relay"))

    def test_relay_mode_cameras_report_webrtc_transport(self) -> None:
        """UI-facing transport must stay 'webrtc', never 'rtsp'."""
        os.environ["WEBRTC_RELAY_URL"] = "wss://vid.nk-otok.hr/go2rtc"
        service = self.module.PreviewService(hls_base_dir=str(self.hls_dir))
        service.gst_manager = _FakeGStreamerManager()
        # Simulate RTSP mount active
        service.preview_active[0] = True
        service.preview_transport[0] = "webrtc"
        service.rtsp_mount_active[0] = True

        status = service.get_status()
        self.assertEqual(status["cameras"]["camera_0"]["transport"], "webrtc")
        self.assertTrue(status["cameras"]["camera_0"]["active"])


if __name__ == "__main__":
    unittest.main()

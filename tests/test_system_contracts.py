import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TestSystemContracts(unittest.TestCase):
    def test_ws_preview_command_does_not_pass_mode(self) -> None:
        source = (ROOT / "src/platform/simple_api_v3.py").read_text(encoding="utf-8")
        section_match = re.search(
            r"elif action == \"start_preview\":(?P<body>.*?)elif action == \"stop_preview\":",
            source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(section_match, "start_preview WS command block not found")
        body = section_match.group("body")
        self.assertIn("preview_service.start_preview(camera_id=camera_id, transport=transport)", body)
        self.assertIn("transport = params.get(\"transport\")", body)
        self.assertNotIn("kwargs[\"mode\"]", body)
        self.assertNotIn("start_preview(**kwargs)", body)

    def test_ws_panorama_processing_uses_panorama_service(self) -> None:
        source = (ROOT / "src/platform/simple_api_v3.py").read_text(encoding="utf-8")
        self.assertIn("pano_service.get_processing_status(match_id)", source)
        self.assertNotIn("return get_processing_status(match_id)", source)

    def test_preview_route_preserves_starlette_http_status(self) -> None:
        source = (ROOT / "src/platform/simple_api_v3.py").read_text(encoding="utf-8")
        section_match = re.search(
            r"def start_preview\(request: PreviewRequest\):(?P<body>.*?)@app.delete\(\"/api/v1/preview\"\)",
            source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(section_match, "start_preview route block not found")
        body = section_match.group("body")
        self.assertIn("isinstance(e, StarletteHTTPException)", body)
        self.assertIn("status_code=e.status_code", body)
        self.assertIn("detail=e.detail", body)
        self.assertIn("pipeline_manager.release_lock(holder)", body)

    def test_dashboard_has_transport_level_rest_fallback(self) -> None:
        source = (ROOT / "src/platform/web-dashboard/src/pages/Dashboard.tsx").read_text(encoding="utf-8")
        self.assertIn("function isWsTransportError", source)
        self.assertIn("if (isWsTransportError(err))", source)
        self.assertIn("await startRecordingViaRest()", source)
        self.assertIn("await stopRecordingViaRest()", source)

    def test_preview_has_transport_level_rest_fallback(self) -> None:
        source = (ROOT / "src/platform/web-dashboard/src/pages/Preview.tsx").read_text(encoding="utf-8")
        self.assertIn("function isWsTransportError", source)
        self.assertIn("if (isWsTransportError(err))", source)
        self.assertIn("await startPreviewViaRest()", source)
        self.assertNotIn("startCalibrationViaRest", source)
        self.assertIn("await stopPreviewViaRest()", source)

    def test_dedup_replays_cached_command_result(self) -> None:
        source = (ROOT / "src/platform/ws_manager.py").read_text(encoding="utf-8")
        self.assertIn("_recent_commands", source)
        self.assertIn("cached = self._recent_commands[cmd_id].get(\"result\")", source)
        self.assertIn("replay[\"deduplicated\"] = True", source)
        self.assertIn("\"in_progress\": True", source)

    def test_ws_preview_releases_lock_on_failed_start(self) -> None:
        source = (ROOT / "src/platform/simple_api_v3.py").read_text(encoding="utf-8")
        section_match = re.search(
            r"elif action == \"start_preview\":(?P<body>.*?)elif action == \"stop_preview\":",
            source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(section_match, "start_preview WS command block not found")
        body = section_match.group("body")
        self.assertIn("holder = f\"api-preview-{camera_id or 'all'}\"", body)
        self.assertIn("pipeline_manager.release_lock(holder)", body)

    def test_ws_stop_recording_releases_lock_after_transport_success(self) -> None:
        source = (ROOT / "src/platform/simple_api_v3.py").read_text(encoding="utf-8")
        section_match = re.search(
            r"elif action == \"stop_recording\":(?P<body>.*?)elif action == \"start_preview\":",
            source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(section_match, "stop_recording WS command block not found")
        body = section_match.group("body")
        self.assertIn("result.get(\"transport_success\")", body)
        self.assertIn("or not status_after_stop.get(\"recording\")", body)
        self.assertIn("pipeline_manager.release_lock(f\"api-recording-{match_id}\")", body)

    def test_rest_stop_recording_releases_lock_after_transport_success(self) -> None:
        source = (ROOT / "src/platform/simple_api_v3.py").read_text(encoding="utf-8")
        section_match = re.search(
            r"def stop_recording\(force: bool = False\):(?P<body>.*?)# ============================================================================",
            source,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(section_match, "stop_recording route block not found")
        body = section_match.group("body")
        self.assertIn("result.get('transport_success')", body)
        self.assertIn("or not status_after_stop.get('recording')", body)
        self.assertIn("pipeline_manager.release_lock(f\"api-recording-{match_id}\")", body)

    def test_webrtc_signaling_handlers_are_registered(self) -> None:
        source = (ROOT / "src/platform/simple_api_v3.py").read_text(encoding="utf-8")
        self.assertIn("ws_manager.register_message_handler(_msg_type, _handle_webrtc_ws_message)", source)
        self.assertIn("preview_service.set_webrtc_emitter(ws_manager.schedule_send_to_connection)", source)

    def test_system_metrics_uses_psutil_for_cpu_usage(self) -> None:
        source = (ROOT / "src/platform/simple_api_v3.py").read_text(encoding="utf-8")
        self.assertIn('psutil.cpu_percent(interval=0.1)', source)
        self.assertNotIn('subprocess.run(["top", "-bn", "1"]', source)

    def test_recording_correlation_diagnostics_endpoint_exists(self) -> None:
        source = (ROOT / "src/platform/simple_api_v3.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/api/v1/diagnostics/recording-correlations")', source)
        self.assertIn("_collect_recording_diagnostics(", source)
        self.assertIn("recording-correlations", source)

    def test_recording_correlation_scans_nvvic_and_timeout_patterns(self) -> None:
        source = (ROOT / "src/platform/simple_api_v3.py").read_text(encoding="utf-8")
        self.assertIn("failed to open NvVIC", source)
        self.assertIn("failed to allocate buffer", source)
        self.assertIn("EOS wait timed out", source)
        self.assertIn("Segment probe failed", source)

    def test_ws_proxy_config_present(self) -> None:
        caddy_source = (ROOT / "deploy/config/Caddyfile").read_text(encoding="utf-8")
        vite_source = (ROOT / "src/platform/web-dashboard/vite.config.ts").read_text(encoding="utf-8")

        ws_index = caddy_source.find("handle /ws")
        api_index = caddy_source.find("handle /api/*")
        self.assertNotEqual(ws_index, -1)
        self.assertNotEqual(api_index, -1)
        self.assertLess(ws_index, api_index, "Caddy /ws proxy must be declared before /api/*")

        self.assertIn("'/ws':", vite_source)
        self.assertIn("target: 'ws://localhost:8000'", vite_source)
        self.assertIn("ws: true", vite_source)

    def test_panorama_capture_uses_exposure_settle_warmup(self) -> None:
        source = (ROOT / "src/panorama/panorama_service.py").read_text(encoding="utf-8")
        self.assertIn("exposure_settle_frames = 60", source)
        self.assertIn('num-buffers={total_frames}', source)
        self.assertIn("if frame_count == total_frames", source)
        self.assertIn("timeout = 10 * Gst.SECOND", source)

    def test_recording_alert_hook_event_types_exist(self) -> None:
        source = (ROOT / "src/video-pipeline/recording_service.py").read_text(encoding="utf-8")
        self.assertIn("recording_overload_guard_triggered", source)
        self.assertIn("recording_stop_non_graceful", source)
        self.assertIn("recording_integrity_failed", source)
        self.assertIn("recording_fps_below_slo", source)


if __name__ == "__main__":
    unittest.main()

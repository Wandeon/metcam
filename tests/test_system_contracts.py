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
        self.assertIn("preview_service.start_preview(camera_id=camera_id)", body)
        self.assertNotIn("kwargs[\"mode\"]", body)
        self.assertNotIn("start_preview(**kwargs)", body)

    def test_ws_panorama_processing_uses_panorama_service(self) -> None:
        source = (ROOT / "src/platform/simple_api_v3.py").read_text(encoding="utf-8")
        self.assertIn("pano_service.get_processing_status(match_id)", source)
        self.assertNotIn("return get_processing_status(match_id)", source)

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
        self.assertIn("await startCalibrationViaRest()", source)
        self.assertIn("await stopPreviewViaRest()", source)

    def test_dedup_replays_cached_command_result(self) -> None:
        source = (ROOT / "src/platform/ws_manager.py").read_text(encoding="utf-8")
        self.assertIn("_recent_commands", source)
        self.assertIn("cached = self._recent_commands[cmd_id].get(\"result\")", source)
        self.assertIn("replay[\"deduplicated\"] = True", source)
        self.assertIn("\"in_progress\": True", source)

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


if __name__ == "__main__":
    unittest.main()

import importlib.util
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path


def load_pipeline_builders_module():
    module_name = f"pipeline_builders_test_{time.time_ns()}"
    module_path = Path(__file__).resolve().parents[1] / "src/video-pipeline/pipeline_builders.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if not spec or not spec.loader:
        raise RuntimeError("Could not load pipeline_builders module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class TestPipelineBuilders(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_pipeline_builders_module()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "camera_config.json"
        self.config_data = {
            "recording_quality": "balanced",
            "cameras": {
                "0": {
                    "crop": {"left": 480, "right": 480, "top": 272, "bottom": 272},
                    "exposure_compensation": 0.15,
                },
                "1": {
                    "crop": {"left": 0, "right": 0, "top": 0, "bottom": 0},
                    "exposure_compensation": -0.1,
                },
            },
        }
        self.config_path.write_text(json.dumps(self.config_data), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_resolve_config_path_default_location(self) -> None:
        resolved = self.module._resolve_config_path()
        self.assertTrue(str(resolved).endswith("config/camera_config.json"))

    def test_load_camera_config_from_explicit_path(self) -> None:
        data = self.module.load_camera_config(str(self.config_path))
        self.assertEqual(data["recording_quality"], "balanced")
        self.assertEqual(data["cameras"]["0"]["crop"]["left"], 480)

    def test_pixel_count_to_edge_coords(self) -> None:
        coords = self.module.pixel_count_to_edge_coords({"left": 100, "right": 150, "top": 20, "bottom": 30})
        self.assertEqual(coords, (100, 3690, 20, 2130))

    def test_build_camera_source_converts_crop_to_nvvidconv_coordinates(self) -> None:
        cam_cfg = self.config_data["cameras"]["0"]
        pipeline, width, height = self.module._build_camera_source(0, cam_cfg)
        self.assertEqual(width, 2880)
        self.assertEqual(height, 1616)
        self.assertIn("left=480 right=3360 top=272 bottom=1888", pipeline)
        self.assertIn("width=2880,height=1616", pipeline)
        self.assertIn("exposurecompensation=0.15", pipeline)
        self.assertIn("video/x-raw,format=I420,width=2880,height=1616", pipeline)

    def test_build_camera_source_clamps_oversized_crop_values(self) -> None:
        cam_cfg = {
            "crop": {"left": 99999, "right": 99999, "top": 99999, "bottom": 99999},
            "exposure_compensation": 0.0,
        }
        pipeline, width, height = self.module._build_camera_source(0, cam_cfg)
        self.assertEqual(width, 16)
        self.assertEqual(height, 16)
        self.assertIn("left=3840 right=3840 top=2160 bottom=2160", pipeline)

    def test_build_recording_pipeline_uses_requested_quality_preset(self) -> None:
        pipeline = self.module.build_recording_pipeline(
            camera_id=0,
            output_pattern="/tmp/cam0_%02d.mp4",
            config_path=str(self.config_path),
            quality_preset="balanced",
        )
        self.assertIn("speed-preset=fast", pipeline)
        self.assertIn("bitrate=22000", pipeline)
        self.assertIn("vbv-maxrate=22000", pipeline)
        self.assertIn("vbv-bufsize=44000", pipeline)
        self.assertIn("splitmuxsink", pipeline)
        self.assertIn("location=/tmp/cam0_%02d.mp4", pipeline)
        self.assertIn("queue name=preenc_queue", pipeline)
        self.assertIn("queue name=postenc_queue", pipeline)
        self.assertIn("queue name=mux_queue", pipeline)
        self.assertIn("queue name=preenc_queue max-size-time=2000000000 max-size-buffers=0 max-size-bytes=0 leaky=downstream", pipeline)
        self.assertIn("queue name=postenc_queue max-size-time=2000000000 max-size-buffers=0 max-size-bytes=0 !", pipeline)
        self.assertIn("queue name=mux_queue max-size-time=2000000000 max-size-buffers=0 max-size-bytes=0 !", pipeline)
        self.assertNotIn("queue name=postenc_queue max-size-time=2000000000 max-size-buffers=0 max-size-bytes=0 leaky=downstream", pipeline)
        self.assertNotIn("queue name=mux_queue max-size-time=2000000000 max-size-buffers=0 max-size-bytes=0 leaky=downstream", pipeline)
        self.assertIn("aud=false byte-stream=false", pipeline)
        self.assertNotIn("aud=true byte-stream=false", pipeline)
        self.assertIn("h264parse config-interval=-1", pipeline)
        self.assertNotIn("h264parse config-interval=-1 disable-passthrough=true", pipeline)

    def test_build_recording_pipeline_defaults_to_high_for_invalid_preset(self) -> None:
        pipeline = self.module.build_recording_pipeline(
            camera_id=0,
            output_pattern="/tmp/cam0_%02d.mp4",
            config_path=str(self.config_path),
            quality_preset="does_not_exist",
        )
        self.assertIn("speed-preset=veryfast", pipeline)
        self.assertIn("bitrate=25000", pipeline)
        self.assertIn("vbv-maxrate=25000", pipeline)
        self.assertIn("vbv-bufsize=50000", pipeline)

    def test_build_recording_pipeline_fast_keeps_validated_gop(self) -> None:
        pipeline = self.module.build_recording_pipeline(
            camera_id=0,
            output_pattern="/tmp/cam0_%02d.mp4",
            config_path=str(self.config_path),
            quality_preset="fast",
        )
        self.assertIn("speed-preset=ultrafast", pipeline)
        self.assertIn("key-int-max=90", pipeline)

    def test_build_preview_pipeline_contains_hls_outputs(self) -> None:
        pipeline = self.module.build_preview_pipeline(
            camera_id=1,
            hls_location="/dev/shm/hls/cam1.m3u8",
            config_path=str(self.config_path),
        )
        self.assertIn("hlssink2", pipeline)
        self.assertIn("playlist-location=/dev/shm/hls/cam1.m3u8", pipeline)
        self.assertIn("location=/dev/shm/hls/cam1_%05d.ts", pipeline)
        self.assertIn("aud=true", pipeline)

    def test_build_preview_webrtc_pipeline_contains_webrtcbin(self) -> None:
        pipeline = self.module.build_preview_webrtc_pipeline(
            camera_id=0,
            stun_server="stun://stun.example.org:3478",
            turn_server="turn://user:pass@turn.example.org:3478",
            config_path=str(self.config_path),
        )
        self.assertIn("webrtcbin", pipeline)
        self.assertIn("webrtcbin name=webrtc", pipeline)
        self.assertIn("! webrtc.", pipeline)
        self.assertIn("stun-server=stun://stun.example.org:3478", pipeline)
        self.assertIn("turn-server=turn://user:pass@turn.example.org:3478", pipeline)
        self.assertIn("rtph264pay", pipeline)

    def test_build_panorama_output_webrtc_pipeline_contains_webrtcbin(self) -> None:
        pipeline = self.module.build_panorama_output_webrtc_pipeline(
            width=1920,
            height=1080,
            fps=24,
            stun_server="stun://stun.example.org:3478",
            turn_server="turn://user:pass@turn.example.org:3478",
        )
        self.assertIn("appsrc name=panorama_source", pipeline)
        self.assertIn("width=1920,height=1080,framerate=24/1", pipeline)
        self.assertIn("webrtcbin", pipeline)
        self.assertIn("webrtcbin name=webrtc", pipeline)
        self.assertIn("! webrtc.", pipeline)
        self.assertIn("stun-server=stun://stun.example.org:3478", pipeline)
        self.assertIn("turn-server=turn://user:pass@turn.example.org:3478", pipeline)

    def test_build_panorama_capture_pipeline_contains_appsink_branch(self) -> None:
        pipeline = self.module.build_panorama_capture_pipeline(camera_id=0, config_path=str(self.config_path))
        self.assertIn("tee name=t", pipeline)
        self.assertIn("appsink name=appsink", pipeline)
        self.assertIn("playlist-location=/dev/shm/hls/panorama_cam0.m3u8", pipeline)


if __name__ == "__main__":
    unittest.main()

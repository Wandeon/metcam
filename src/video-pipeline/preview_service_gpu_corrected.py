#!/usr/bin/env python3
"""
FootballVision Pro - GPU Barrel Corrected HLS Preview Service

EXACT same pipeline as recording:
  - Same FOV: 2880×1620 (56% crop)
  - Same barrel correction shader
  - Lower bitrate: 3 Mbps (vs 12 Mbps recording)
  - HLS segments for web streaming
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import signal
import subprocess
import sys
import time
import threading
from pathlib import Path

# Initialize GStreamer
Gst.init(None)


class PreviewServiceGPUCorrected:
    def __init__(self, hls_dir="/dev/shm/hls"):
        self.hls_dir = Path(hls_dir)
        self.web_hls_dir = Path("/var/www/hls")
        self.pipelines = []
        self.main_loop = None
        self.loop_thread = None
        self.is_streaming = False

        # Load camera configuration manager
        repo_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo_root / "src" / "video-pipeline"))
        sys.path.insert(0, str(repo_root / "shaders"))

        try:
            from camera_config_manager import get_config_manager
            import shader_generator

            self.config_manager = get_config_manager()
            self.shader_generator = shader_generator
            self.enable_correction = True

            print(f"✅ Loaded camera configuration manager")
            for cam_id in [0, 1]:
                config = self.config_manager.get_camera_config(cam_id)
                print(f"   Camera {cam_id}: {config['rotation']:+.1f}° "
                      f"{config['correction_type']} correction")
        except Exception as e:
            print(f"⚠️  Failed to load camera config manager: {e}")
            print(f"⚠️  Correction disabled")
            self.config_manager = None
            self.shader_generator = None
            self.enable_correction = False

        # Store shader code per camera
        self.shader_codes = {}

    def _recording_active(self) -> bool:
        """Check if recording is active"""
        result = subprocess.run(
            "ps aux | grep 'nvarguscamerasrc.*splitmuxsink' | grep -v grep",
            shell=True,
            capture_output=True,
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def _cleanup_dir(self, directory: Path) -> None:
        """Clean up old HLS files"""
        directory.mkdir(parents=True, exist_ok=True)
        for pattern in ("*.ts", "*.m3u8"):
            for item in directory.glob(pattern):
                try:
                    item.unlink()
                except FileNotFoundError:
                    pass

    def _create_camera_pipeline(self, camera_id: int) -> Gst.Pipeline:
        """Create HLS preview pipeline for one camera - SAME FOV as recording"""

        playlist_location = str(self.hls_dir / f"cam{camera_id}.m3u8")
        segment_location = str(self.hls_dir / f"cam{camera_id}_%05d.ts")

        # Load camera configuration
        if self.config_manager:
            cam_config = self.config_manager.get_camera_config(camera_id)
            crop_config = cam_config.get('crop', {})
            crop_left = crop_config.get('left', 480)
            crop_right = crop_config.get('right', 480)
            crop_top = crop_config.get('top', 270)
            crop_bottom = crop_config.get('bottom', 270)
        else:
            # Fallback to center crop
            crop_left, crop_right, crop_top, crop_bottom = 480, 480, 270, 270

        # Generate camera-specific shader code based on correction type
        if self.enable_correction and self.shader_generator and self.config_manager:
            cam_config = self.config_manager.get_camera_config(camera_id)
            shader_code = self.shader_generator.get_shader_for_camera(camera_id, cam_config)
            self.shader_codes[camera_id] = shader_code
        else:
            shader_code = None

        # Pipeline WITH distortion correction BEFORE crop (better quality)
        if self.enable_correction and shader_code:
            # Apply distortion correction + rotation on full 4K, then crop
            # Linked exposure: Both cameras use same constrained exposure range
            # Camera-specific crop offsets loaded from configuration

            pipeline_str = (
                f"nvarguscamerasrc name=src sensor-id={camera_id} "
                "tnr-mode=0 ee-mode=0 wbmode=1 aelock=false "
                "exposuretimerange=\"13000 33000000\" gainrange=\"1 16\" "
                "ispdigitalgainrange=\"1 4\" saturation=1.0 ! "
                "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1,format=NV12 ! "

                # Convert to RGBA for OpenGL (full 4K)
                "nvvidconv ! "
                "video/x-raw,format=RGBA,width=3840,height=2160 ! "

                # Apply barrel correction + rotation on full 4K image
                "glupload name=upload ! "
                "glshader name=shader ! "
                "gldownload name=download ! "

                # Camera-specific software crop AFTER correction
                f"videocrop left={crop_left} right={crop_right} top={crop_top} bottom={crop_bottom} ! "
                "video/x-raw,width=2880,height=1620 ! "

                # Convert to I420 for encoding
                "videoconvert ! "
                "video/x-raw,format=I420,width=2880,height=1620 ! "

                # Encode to H.264
                "x264enc name=enc speed-preset=ultrafast bitrate=3000 tune=zerolatency key-int-max=60 ! "
                "h264parse ! "

                # HLS output
                "hlssink2 name=sink "
                f"playlist-location={playlist_location} "
                f"location={segment_location} "
                "target-duration=2 "
                "max-files=10"
            )
        else:
            # Pipeline WITHOUT barrel correction - HARDWARE CROP ONLY
            # Linked exposure: Both cameras use same constrained exposure range
            pipeline_str = (
                f"nvarguscamerasrc name=src sensor-id={camera_id} "
                "tnr-mode=0 ee-mode=0 wbmode=1 aelock=false "
                "exposuretimerange=\"13000 33000000\" gainrange=\"1 16\" "
                "ispdigitalgainrange=\"1 4\" saturation=1.0 ! "
                "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1,format=NV12 ! "

                # VIC hardware crop to 2880×1620 (EDGE COORDINATES)
                "nvvidconv left=480 right=3360 top=270 bottom=1890 ! "
                "video/x-raw(memory:NVMM),format=NV12,width=2880,height=1620,framerate=30/1 ! "

                # Second nvvidconv for format conversion
                "nvvidconv ! "
                "video/x-raw,format=NV12,width=2880,height=1620,framerate=30/1 ! "

                # Encode to H.264 - Low bitrate for streaming
                "videoconvert ! "
                "video/x-raw,format=I420 ! "
                "x264enc name=enc speed-preset=ultrafast bitrate=3000 tune=zerolatency key-int-max=60 ! "
                "h264parse ! "

                # HLS output
                "hlssink2 name=sink "
                f"playlist-location={playlist_location} "
                f"location={segment_location} "
                "target-duration=2 "
                "max-files=10"
            )

        pipeline = Gst.parse_launch(pipeline_str)

        # If correction is enabled, set the shader fragment property
        if self.enable_correction and shader_code:
            shader_element = pipeline.get_by_name("shader")
            if shader_element:
                shader_element.set_property("fragment", shader_code)

        return pipeline

    def start(self) -> dict:
        """Start HLS preview for both cameras"""
        if self.is_streaming:
            return {"status": "already_streaming", "streaming": True}

        if self._recording_active():
            return {
                "status": "error",
                "streaming": False,
                "message": "Recording is active. Stop recording first."
            }

        # Reload camera configuration from disk
        if self.config_manager:
            self.config_manager.load_config()
            print(f"✅ Reloaded camera configuration before starting preview")

        # Clean up old segments
        self._cleanup_dir(self.hls_dir)
        self._cleanup_dir(self.web_hls_dir)

        # Create pipelines for both cameras
        for camera_id in [0, 1]:
            pipeline = self._create_camera_pipeline(camera_id)

            # Set up bus
            bus = pipeline.get_bus()
            bus.add_signal_watch()

            def make_on_message(cam_id):
                def on_message(bus, message):
                    t = message.type
                    if t == Gst.MessageType.ERROR:
                        err, debug = message.parse_error()
                        print(f"[Cam {cam_id}] Error: {err}")
                return on_message

            bus.connect("message", make_on_message(camera_id))

            self.pipelines.append(pipeline)

        # Start all pipelines
        for pipeline in self.pipelines:
            ret = pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                self.stop()
                return {
                    "status": "error",
                    "streaming": False,
                    "message": "Failed to start pipeline"
                }

        # Start GLib main loop in separate thread
        self.main_loop = GLib.MainLoop()
        self.loop_thread = threading.Thread(target=self.main_loop.run)
        self.loop_thread.daemon = True
        self.loop_thread.start()

        # Give pipelines time to start
        time.sleep(2)

        # Sync to web directory
        subprocess.run(
            f"rsync -a --delete {self.hls_dir}/ {self.web_hls_dir}/",
            shell=True,
            check=False
        )

        self.is_streaming = True

        # Get camera configurations for status
        cam0_config = self.config_manager.get_camera_config(0) if self.config_manager else {}
        cam1_config = self.config_manager.get_camera_config(1) if self.config_manager else {}

        return {
            "status": "streaming",
            "streaming": True,
            "cam0_url": f"/hls/cam0.m3u8",
            "cam1_url": f"/hls/cam1.m3u8",
            "output_resolution": "2880x1620",
            "framerate": 30,
            "bitrate_kbps": 3000,
            "correction_enabled": self.enable_correction,
            "cam0_correction": cam0_config.get('correction_type', 'none'),
            "cam1_correction": cam1_config.get('correction_type', 'none'),
        }

    def stop(self) -> dict:
        """Stop preview stream"""
        if not self.is_streaming:
            return {"status": "not_streaming", "streaming": False}

        # Send EOS to all pipelines
        for pipeline in self.pipelines:
            pipeline.send_event(Gst.Event.new_eos())

        time.sleep(1)

        # Set to NULL state
        for pipeline in self.pipelines:
            pipeline.set_state(Gst.State.NULL)

        # Stop main loop
        if self.main_loop:
            self.main_loop.quit()
            if self.loop_thread:
                self.loop_thread.join(timeout=2)

        self.pipelines = []
        self.main_loop = None
        self.loop_thread = None
        self.is_streaming = False

        return {"status": "stopped", "streaming": False}

    def get_status(self) -> dict:
        """Get current preview status"""
        if not self.is_streaming:
            return {
                "status": "idle",
                "streaming": False,
                "output_resolution": "2880x1620",
                "framerate": 30,
            }

        # Get camera configurations for status
        cam0_config = self.config_manager.get_camera_config(0) if self.config_manager else {}
        cam1_config = self.config_manager.get_camera_config(1) if self.config_manager else {}

        return {
            "status": "streaming",
            "streaming": True,
            "cam0_url": f"/hls/cam0.m3u8",
            "cam1_url": f"/hls/cam1.m3u8",
            "output_resolution": "2880x1620",
            "framerate": 30,
            "bitrate_kbps": 3000,
            "correction_enabled": self.enable_correction,
            "cam0_correction": cam0_config.get('correction_type', 'none'),
            "cam1_correction": cam1_config.get('correction_type', 'none'),
        }


if __name__ == "__main__":
    preview = PreviewServiceGPUCorrected()

    print("Starting GPU-corrected preview...")
    result = preview.start()
    print(result)

    print("\nPress Ctrl+C to stop...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        preview.stop()

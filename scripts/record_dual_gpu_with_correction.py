#!/usr/bin/env python3
"""FootballVision Pro - Dual Camera Recording with GPU Crop + Barrel Correction

Pipeline per camera:
  1. nvarguscamerasrc (4K @ 30fps)
  2. nvvidconv GPU crop (2880×1620, 56% FOV)
  3. glupload + glshader (barrel correction)
  4. gldownload
  5. nvvidconv (chroma fix)
  6. x264enc → MKV segments
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import sys
import os
import signal
from pathlib import Path
from datetime import datetime

# Initialize GStreamer
Gst.init(None)

class DualCameraRecorder:
    def __init__(self, match_id: str, output_dir: Path, enable_correction: bool = True):
        self.match_id = match_id
        self.output_dir = output_dir
        self.enable_correction = enable_correction
        self.pipelines = []
        self.loops = []

        # Load camera configuration manager
        repo_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo_root / "src" / "video-pipeline"))
        sys.path.insert(0, str(repo_root / "shaders"))

        try:
            from camera_config_manager import get_config_manager
            import shader_generator

            self.config_manager = get_config_manager()
            self.shader_generator = shader_generator

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

        # Create output directories
        self.segments_dir = self.output_dir / match_id / "segments"
        self.segments_dir.mkdir(parents=True, exist_ok=True)

    def create_camera_pipeline(self, camera_id: int) -> Gst.Pipeline:
        """Create pipeline for one camera with correction, rotation, and crop"""

        output_pattern = str(self.segments_dir / f"cam{camera_id}_%05d.mkv")

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
        shader_code = None
        if self.enable_correction and self.shader_generator and self.config_manager:
            cam_config = self.config_manager.get_camera_config(camera_id)

            # Check if correction is effectively disabled (all params are zero/default)
            correction_params = cam_config.get('correction_params', {})
            correction_type = cam_config.get('correction_type', 'barrel')

            correction_disabled = False
            if correction_type == 'barrel':
                k1 = correction_params.get('k1', 0)
                k2 = correction_params.get('k2', 0)
                correction_disabled = (abs(k1) < 0.001 and abs(k2) < 0.001)

            if not correction_disabled:
                shader_code = self.shader_generator.get_shader_for_camera(camera_id, cam_config)
                self.shader_codes[camera_id] = shader_code
                print(f"  Camera {camera_id}: {cam_config['correction_type']} correction "
                      f"with rotation {cam_config['rotation']:+.1f}°")
            else:
                print(f"  Camera {camera_id}: Correction disabled (params are zero), "
                      f"using rotation {cam_config.get('rotation', 0):+.1f}° only")

        if self.enable_correction and shader_code:
            # Pipeline WITH correction - VIC crop FIRST, then GL correction (like preview)
            pipeline_str = (
                f"nvarguscamerasrc name=src sensor-id={camera_id} "
                "tnr-mode=0 ee-mode=0 wbmode=1 aelock=false "
                "exposuretimerange=\"13000 33000000\" gainrange=\"1 16\" "
                "ispdigitalgainrange=\"1 4\" saturation=1.0 ! "
                "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1,format=NV12 ! "

                # VIC GPU crop to 2880×1620 (BEFORE GL processing) - stays in NVMM
                f"nvvidconv name=crop compute-hw=1 left={crop_left} right={crop_right} top={crop_top} bottom={crop_bottom} ! "
                f"video/x-raw(memory:NVMM),format=NV12,width={3840-crop_left-crop_right},height={2160-crop_top-crop_bottom},framerate=30/1 ! "

                # Convert to RGBA for OpenGL (cropped 2880×1620)
                "nvvidconv ! "
                f"video/x-raw,format=RGBA,width={3840-crop_left-crop_right},height={2160-crop_top-crop_bottom} ! "

                # Apply distortion correction + rotation on cropped image
                "glupload name=upload ! "
                "glshader name=shader ! "
                "gldownload name=download ! "


                # Encode to H.264 at 12 Mbps (recording quality)
                "x264enc name=enc threads=6 speed-preset=ultrafast bitrate=12000 tune=zerolatency key-int-max=60 ! "
                "h264parse ! "

                # Segment into 10-minute chunks (MKV format)
                "splitmuxsink name=sink "
                f"location={output_pattern} "
                "max-size-time=600000000000 "
                "muxer-factory=matroskamux "
                "async-finalize=true"
            )
        else:
            # Pipeline WITHOUT correction - VIC crop only (like preview)
            pipeline_str = (
                f"nvarguscamerasrc name=src sensor-id={camera_id} "
                "tnr-mode=0 ee-mode=0 wbmode=1 aelock=false "
                "exposuretimerange=\"13000 33000000\" gainrange=\"1 16\" "
                "ispdigitalgainrange=\"1 4\" saturation=1.0 ! "
                "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1,format=NV12 ! "

                # VIC hardware crop using EDGE COORDINATES (like preview)
                "nvvidconv left=480 right=3360 top=270 bottom=1890 ! "
                "video/x-raw(memory:NVMM),format=NV12,width=2880,height=1620,framerate=30/1 ! "

                # Second nvvidconv for format conversion
                "nvvidconv ! "
                "video/x-raw,format=NV12,width=2880,height=1620,framerate=30/1 ! "

                # Convert to I420 for encoding
                "videoconvert ! "
                "video/x-raw,format=I420 ! "

                # Encode to H.264 at 12 Mbps (4x preview bitrate)
                "x264enc name=enc threads=6 speed-preset=ultrafast bitrate=12000 tune=zerolatency key-int-max=60 ! "
                "h264parse ! "

                # Segment into 10-minute chunks
                "splitmuxsink name=sink "
                f"location={output_pattern} "
                "max-size-time=600000000000 "
                "muxer-factory=matroskamux "
                "async-finalize=true"
            )

        pipeline = Gst.parse_launch(pipeline_str)

        # If correction is enabled, set the shader fragment property
        if self.enable_correction and shader_code:
            shader_element = pipeline.get_by_name("shader")
            if shader_element:
                shader_element.set_property("fragment", shader_code)
            else:
                print(f"⚠️  Warning: Could not find shader element for camera {camera_id}")

        return pipeline

    def start_recording(self):
        """Start recording both cameras"""

        print("=" * 70)
        print(f"   FootballVision Pro - Dual Camera Recording")
        print("=" * 70)
        print()
        print(f"Match ID: {self.match_id}")
        print(f"Output: {self.segments_dir}")
        print(f"Barrel Correction: {'ENABLED' if self.enable_correction else 'DISABLED'}")
        print()
        print("Pipeline: nvarguscamerasrc → GPU crop → ", end="")
        if self.enable_correction:
            print("GL correction → ", end="")
        print("chroma fix → x264enc → MKV segments")
        print()

        # Create pipelines for both cameras
        for camera_id in [0, 1]:
            print(f"Creating pipeline for camera {camera_id}...")
            pipeline = self.create_camera_pipeline(camera_id)

            # Set up bus
            bus = pipeline.get_bus()
            bus.add_signal_watch()

            def make_on_message(cam_id):
                def on_message(bus, message):
                    t = message.type
                    if t == Gst.MessageType.EOS:
                        print(f"\n[Cam {cam_id}] EOS received")
                    elif t == Gst.MessageType.ERROR:
                        err, debug = message.parse_error()
                        err_str = str(err)

                        # Log the error but don't stop on non-fatal GL errors
                        print(f"\n[Cam {cam_id}] ⚠️  Error: {err}")
                        if debug:
                            print(f"[Cam {cam_id}] Debug: {debug}")

                        # Only stop on critical errors (not GL shader warnings)
                        if "Internal data stream error" in err_str or "Failed to allocate" in err_str:
                            print(f"[Cam {cam_id}] 🛑 Fatal error detected, stopping all cameras")
                            for p in self.pipelines:
                                p.send_event(Gst.Event.new_eos())
                    elif t == Gst.MessageType.WARNING:
                        warn, debug = message.parse_warning()
                        print(f"[Cam {cam_id}] ⚠️  Warning: {warn}")
                return on_message

            bus.connect("message", make_on_message(camera_id))

            self.pipelines.append(pipeline)

        # Start all pipelines
        print()
        print("Starting pipelines...")
        for i, pipeline in enumerate(self.pipelines):
            ret = pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                print(f"❌ Failed to start camera {i}")
                return False

        print()
        print("=" * 70)
        print("✅ Recording started!")
        print("   Press Ctrl+C to stop")
        print("=" * 70)
        print()

        return True

    def stop_recording(self):
        """Stop recording and cleanup"""
        print("\nStopping recording...")

        # Send EOS to all pipelines
        for pipeline in self.pipelines:
            pipeline.send_event(Gst.Event.new_eos())

        # Wait a bit for EOS to propagate
        import time
        time.sleep(3)

        # Set to NULL state
        for pipeline in self.pipelines:
            pipeline.set_state(Gst.State.NULL)

        print("✅ Recording stopped")

    def run(self):
        """Run the recorder until interrupted"""

        if not self.start_recording():
            return 1

        # Set up signal handler
        def signal_handler(sig, frame):
            print("\n\nReceived signal, stopping...")
            self.stop_recording()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Create main loop
        loop = GLib.MainLoop()

        try:
            loop.run()
        except KeyboardInterrupt:
            print("\nInterrupted by user")
        finally:
            self.stop_recording()

        return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: record_dual_gpu_with_correction.py <match_id> [--no-correction]")
        print()
        print("Examples:")
        print("  ./record_dual_gpu_with_correction.py match_20251019")
        print("  ./record_dual_gpu_with_correction.py match_20251019 --no-correction")
        sys.exit(1)

    match_id = sys.argv[1]
    enable_correction = "--no-correction" not in sys.argv

    output_dir = Path(os.getenv("RECORDING_OUTPUT_DIR", "/mnt/recordings"))

    recorder = DualCameraRecorder(match_id, output_dir, enable_correction)
    sys.exit(recorder.run())

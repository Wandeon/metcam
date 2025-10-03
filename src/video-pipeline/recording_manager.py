#!/usr/bin/env python3
from datetime import datetime
from pathlib import Path
import signal
import subprocess
import time
import json
import re

class RecordingManager:
    """
    Launches two gst-launch processes with splitmuxsink for segmented recording
    and HLS preview streams.
    """
    def __init__(self, output_root: str = "/mnt/recordings", hls_root: str = "/var/www/hls"):
        self.output_root = Path(output_root)
        self.hls_root = Path(hls_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.hls_root.mkdir(parents=True, exist_ok=True)
        self.cam0_process = None
        self.cam1_process = None
        self.match_id = None
        self.start_time = None
        self.match_dir = None
        self.hls_dir = None
        self.vi_errors_baseline = {}

    def _read_vi_errors(self) -> dict:
        """Read VI error counters from traceFS"""
        errors = {}
        try:
            result = subprocess.run(
                ["cat", "/sys/kernel/debug/traceFS/vi/vi_errors"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    match = re.match(r"(\w+):\s+(\d+)", line)
                    if match:
                        errors[match.group(1)] = int(match.group(2))
        except Exception:
            pass
        return errors

    def _check_vi_errors(self) -> bool:
        """Check if VI errors increased since baseline. Returns True if OK, False if errors detected."""
        if not self.vi_errors_baseline:
            return True
        
        current = self._read_vi_errors()
        for key in ["PIXEL_LONG_LINE", "FALCON_ERROR", "ChanselFault"]:
            baseline_val = self.vi_errors_baseline.get(key, 0)
            current_val = current.get(key, 0)
            if current_val > baseline_val:
                return False
        return True

    def _build_pipeline(self, sensor_id: int, sensor_mode: int,
                        width: str, height: str, fps: int,
                        bitrate_kbps: int, segments_dir: Path,
                        hls_dir: Path, hls_fps: int, hls_bitrate_kbps: int,
                        exposure_range: str, gain_range: str,
                        enable_hls: bool = True) -> list:
        """Build GStreamer pipeline with splitmuxsink for segments and optional HLS preview"""
        gop = fps * 2  # 2-second GOPs
        hls_gop = hls_fps  # 1-second GOPs for HLS
        
        # Base pipeline
        cmd = [
            "gst-launch-1.0", "-e",
            "nvarguscamerasrc", f"sensor-id={sensor_id}", f"sensor-mode={sensor_mode}",
            "wbmode=1",
            "aelock=false",
            f"exposuretimerange={exposure_range}",
            f"gainrange={gain_range}",
            "ispdigitalgainrange=1 1",
            "saturation=1.0",
            "!", f"video/x-raw(memory:NVMM),width={width},height={height},framerate={fps}/1",
        ]
        
        if enable_hls:
            # Tee pipeline: recording + HLS preview
            cmd.extend([
                "!", "tee", f"name=t{sensor_id}",
                # Recording branch
                f"t{sensor_id}.", "!", "queue", "max-size-buffers=30", "max-size-time=0", "max-size-bytes=0",
                "!", "nvvidconv",
                "!", "video/x-raw,format=I420",
                "!", "x264enc",
                    f"bitrate={bitrate_kbps}",
                    "speed-preset=ultrafast",
                    f"key-int-max={gop}",
                    "threads=4",
                "!", "h264parse", "config-interval=-1",
                "!", "splitmuxsink",
                    f"location={segments_dir}/cam{sensor_id}_%05d.mp4",
                    "muxer=mp4mux",
                    f"max-size-time={5*60*1000000000}",  # 5 minutes in nanoseconds
                    "max-files=0",
                    "async-finalize=true",
                # HLS preview branch
                f"t{sensor_id}.", "!", "queue", "max-size-buffers=5", "leaky=2",
                "!", "nvvidconv",
                "!", "video/x-raw,format=I420",
                "!", "videorate",
                "!", f"video/x-raw,framerate={hls_fps}/1",
                "!", "x264enc",
                    f"bitrate={hls_bitrate_kbps}",
                    "speed-preset=ultrafast",
                    "tune=zerolatency",
                    f"key-int-max={hls_gop}",
                    "threads=1",
                "!", "h264parse", "config-interval=1",
                "!", "mpegtsmux",
                "!", "hlssink",
                    f"location={hls_dir}/cam{sensor_id}_%05d.ts",
                    f"playlist-location={hls_dir}/cam{sensor_id}.m3u8",
                    "max-files=10",
                    "target-duration=2",
                    "playlist-length=3",
            ])
        else:
            # Recording only (no HLS)
            cmd.extend([
                "!", "queue", "max-size-buffers=30", "max-size-time=0", "max-size-bytes=0",
                "!", "nvvidconv",
                "!", "video/x-raw,format=I420",
                "!", "x264enc",
                    f"bitrate={bitrate_kbps}",
                    "speed-preset=ultrafast",
                    f"key-int-max={gop}",
                    "threads=4",
                "!", "h264parse", "config-interval=-1",
                "!", "splitmuxsink",
                    f"location={segments_dir}/cam{sensor_id}_%05d.mp4",
                    "muxer=mp4mux",
                    f"max-size-time={5*60*1000000000}",
                    "max-files=0",
                    "async-finalize=true",
            ])
        
        return cmd

    def start_recording(self, match_id: str,
                        resolution: str = "1920x1080",
                        fps: int = 30,
                        bitrate_kbps: int = 12000,
                        hls_preview: bool = True,
                        hls_fps: int = 10,
                        hls_bitrate_kbps: int = 2000) -> dict:
        if self.cam0_process or self.cam1_process:
            raise RuntimeError("Recording already in progress")

        # Set 25W power mode for maximum performance
        try:
            subprocess.run(["sudo", "nvpmodel", "-m", "1"], check=True, capture_output=True)
            subprocess.run(["sudo", "jetson_clocks"], check=True, capture_output=True)
        except Exception:
            pass

        # Read VI error baseline
        self.vi_errors_baseline = self._read_vi_errors()

        self.match_id = match_id
        self.start_time = datetime.now()

        self.match_dir = self.output_root / match_id
        self.match_dir.mkdir(parents=True, exist_ok=True)
        
        segments_dir = self.match_dir / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)

        self.hls_dir = self.hls_root / match_id if hls_preview else None
        if self.hls_dir:
            self.hls_dir.mkdir(parents=True, exist_ok=True)

        width, height = resolution.split("x")
        sensor_mode = 1 if int(width) <= 1920 else 0

        exposure_range = "13000 33333333"  # up to 1/30 s
        gain_range = "1 10"

        cam0_cmd = self._build_pipeline(
            0, sensor_mode, width, height, fps,
            bitrate_kbps, segments_dir, self.hls_dir, hls_fps, hls_bitrate_kbps,
            exposure_range, gain_range, hls_preview
        )
        cam1_cmd = self._build_pipeline(
            1, sensor_mode, width, height, fps,
            bitrate_kbps, segments_dir, self.hls_dir, hls_fps, hls_bitrate_kbps,
            exposure_range, gain_range, hls_preview
        )

        self.cam0_process = subprocess.Popen(cam0_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(0.5)
        self.cam1_process = subprocess.Popen(cam1_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(5.0)  # Wait for pipelines to stabilize

        # Check if processes started successfully
        for idx, proc in enumerate((self.cam0_process, self.cam1_process)):
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode(errors="ignore") if proc.stderr else ""
                self.stop_recording()
                camera = f"camera {idx}"
                detail = stderr.strip() or "GStreamer pipeline failed"
                raise RuntimeError(f"Failed to start recording for {camera}: {detail}")

        # Check VI errors after 5 seconds
        if not self._check_vi_errors():
            self.stop_recording()
            raise RuntimeError("VI errors detected (PIXEL_LONG_LINE/FALCON_ERROR/ChanselFault) - check sensor connections")

        hls_urls = {}
        if hls_preview and self.hls_dir:
            hls_urls = {
                "cam0_url": f"http://192.168.0.191/hls/{match_id}/cam0.m3u8",
                "cam1_url": f"http://192.168.0.191/hls/{match_id}/cam1.m3u8",
            }

        return {
            "status": "recording",
            "match_id": match_id,
            "cam0_pid": self.cam0_process.pid,
            "cam1_pid": self.cam1_process.pid,
            "start_time": self.start_time.isoformat(),
            "segments_dir": str(segments_dir),
            **hls_urls
        }

    def stop_recording(self) -> dict:
        if not self.cam0_process and not self.cam1_process:
            return {"status": "not_recording"}

        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0

        # Send SIGINT to gracefully finalize segments
        for proc in (self.cam0_process, self.cam1_process):
            if proc:
                try:
                    proc.send_signal(signal.SIGINT)
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                except Exception:
                    proc.kill()

        time.sleep(2)  # Allow filesystems to sync

        segments_dir = self.match_dir / "segments" if self.match_dir else None
        cam0_segments = sorted(segments_dir.glob("cam0_*.mp4")) if segments_dir and segments_dir.exists() else []
        cam1_segments = sorted(segments_dir.glob("cam1_*.mp4")) if segments_dir and segments_dir.exists() else []

        total_size_mb = sum(s.stat().st_size for s in cam0_segments + cam1_segments) / 1024 / 1024

        result = {
            "status": "stopped",
            "match_id": self.match_id,
            "duration_seconds": duration,
            "segments": {
                "cam0_count": len(cam0_segments),
                "cam1_count": len(cam1_segments),
                "total_size_mb": total_size_mb,
                "segments_dir": str(segments_dir) if segments_dir else None,
            },
        }

        self.cam0_process = None
        self.cam1_process = None
        self.match_id = None
        self.start_time = None
        self.match_dir = None
        self.hls_dir = None
        self.vi_errors_baseline = {}

        return result

    def get_status(self) -> dict:
        if not self.cam0_process and not self.cam1_process:
            return {"status": "idle"}

        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        segments_dir = self.match_dir / "segments" if self.match_dir else None
        cam0_segments = sorted(segments_dir.glob("cam0_*.mp4")) if segments_dir and segments_dir.exists() else []
        cam1_segments = sorted(segments_dir.glob("cam1_*.mp4")) if segments_dir and segments_dir.exists() else []

        vi_ok = self._check_vi_errors()

        return {
            "status": "recording",
            "match_id": self.match_id,
            "duration_seconds": duration,
            "cam0_running": self.cam0_process.poll() is None if self.cam0_process else False,
            "cam1_running": self.cam1_process.poll() is None if self.cam1_process else False,
            "cam0_segments": len(cam0_segments),
            "cam1_segments": len(cam1_segments),
            "vi_errors_ok": vi_ok,
        }

if __name__ == "__main__":
    manager = RecordingManager()
    print("Starting 10 second test recording...")
    manager.start_recording("cli_test", resolution="1920x1080", fps=30, bitrate_kbps=12000)
    time.sleep(10)
    print("Stopping recording...")
    result = manager.stop_recording()
    print(f"Recording saved: {result}")

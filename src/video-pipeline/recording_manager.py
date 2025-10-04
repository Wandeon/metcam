#!/usr/bin/env python3
from datetime import datetime
from pathlib import Path
import signal
import subprocess
import time
import re

class RecordingManager:
    """
    Launches two gst-launch processes with splitmuxsink for segmented recording.
    """
    def __init__(self, output_root: str = "/mnt/recordings"):
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.cam0_process = None
        self.cam1_process = None
        self.match_id = None
        self.start_time = None
        self.match_dir = None
        self.vi_errors_baseline = {}
        self.capture_fps_native = 60  # IMX477 native streaming rate at 1080p
        self.output_fps = 30         # Encode at 30 fps for bandwidth/CPU headroom
        self.encoder_threads = 3
        self.gop_size = 60           # 2-second GOP at 30 fps

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

    def _preview_active(self) -> bool:
        """Check if an external preview pipeline is using the sensors"""
        result = subprocess.run(
            "ps aux | grep 'nvarguscamerasrc.*hlssink' | grep -v grep",
            shell=True,
            capture_output=True,
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def _calibration_active(self) -> bool:
        """Check if calibration snapshot pipelines are still running"""
        result = subprocess.run(
            "ps aux | grep 'multifilesink.*cam[01]\.jpg' | grep -v grep",
            shell=True,
            capture_output=True,
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def _build_pipeline(
            self,
            sensor_id: int,
            sensor_mode: int,
            width: str,
            height: str,
            sensor_fps: int,
            bitrate_kbps: int,
            segments_dir: Path,
            exposure_range: str,
            gain_range: str
        ) -> list:
        """Build native 60 fps capture with 30 fps CPU encode"""
        return [
            'gst-launch-1.0', '-e',
            'nvarguscamerasrc',
            f'sensor-id={sensor_id}',
            f'sensor-mode={sensor_mode}',
            'wbmode=1',
            'aelock=false',
            f'exposuretimerange={exposure_range}',
            f'gainrange={gain_range}',
            'ispdigitalgainrange=1 1',
            'saturation=1.0',
            '!', f'video/x-raw(memory:NVMM),width={width},height={height},framerate={sensor_fps}/1',
            '!', 'nvvidconv',
            '!', 'video/x-raw,format=I420',
            '!', 'videorate',
            '!', f'video/x-raw,framerate={self.output_fps}/1',
            '!', 'x264enc',
            f'bitrate={bitrate_kbps}',
            'speed-preset=ultrafast',
            'tune=zerolatency',
            f'key-int-max={self.gop_size}',
            f'threads={self.encoder_threads}',
            '!', 'h264parse', 'config-interval=-1',
            '!', 'splitmuxsink',
            f'location={segments_dir}/cam{sensor_id}_%05d.mp4',
            'muxer=mp4mux',
            f'max-size-time={5*60*1000000000}',
            'max-files=0',
            'async-finalize=true',
        ]

    def start_recording(self, match_id: str,
                        resolution: str = "1920x1080",
                        fps: int = 60,
                        bitrate_kbps: int = 12000,
                        **_: int) -> dict:
        if self.cam0_process or self.cam1_process:
            raise RuntimeError("Recording already in progress")

        if self._preview_active():
            raise RuntimeError("Preview stream is active. Stop preview before starting the recording.")

        if self._calibration_active():
            subprocess.run(["sudo", "systemctl", "stop", "calibration-preview"], check=False)
            time.sleep(2)
            if self._calibration_active():
                raise RuntimeError("Calibration preview is active. Stop calibration before starting the recording.")

        try:
            subprocess.run(["sudo", "nvpmodel", "-m", "1"], check=True, capture_output=True)
            subprocess.run(["sudo", "jetson_clocks"], check=True, capture_output=True)
        except Exception:
            pass

        self.vi_errors_baseline = self._read_vi_errors()
        self.match_id = match_id
        self.start_time = datetime.now()

        self.match_dir = self.output_root / match_id
        self.match_dir.mkdir(parents=True, exist_ok=True)

        segments_dir = self.match_dir / "segments"
        segments_dir.mkdir(parents=True, exist_ok=True)

        width, height = resolution.split("x")
        sensor_mode = 1 if int(width) <= 1920 else 0
        sensor_fps = self.capture_fps_native if sensor_mode == 1 else 30

        exposure_range = "13000 33333333"
        gain_range = "1 10"

        cam0_cmd = self._build_pipeline(
            0, sensor_mode, width, height, sensor_fps, bitrate_kbps, segments_dir, exposure_range, gain_range
        )
        cam1_cmd = self._build_pipeline(
            1, sensor_mode, width, height, sensor_fps, bitrate_kbps, segments_dir, exposure_range, gain_range
        )

        self.cam0_process = subprocess.Popen(cam0_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(0.5)
        self.cam1_process = subprocess.Popen(cam1_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(5.0)

        for idx, proc in enumerate((self.cam0_process, self.cam1_process)):
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode(errors="ignore") if proc.stderr else ""
                self.stop_recording()
                camera = f"camera {idx}"
                detail = stderr.strip() or "GStreamer pipeline failed"
                raise RuntimeError(f"Failed to start recording for {camera}: {detail}")

        if not self._check_vi_errors():
            self.stop_recording()
            raise RuntimeError("VI errors detected (PIXEL_LONG_LINE/FALCON_ERROR/ChanselFault) - check sensor connections")

        return {
            "status": "recording",
            "match_id": match_id,
            "cam0_pid": self.cam0_process.pid,
            "cam1_pid": self.cam1_process.pid,
            "start_time": self.start_time.isoformat(),
            "segments_dir": str(segments_dir),
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
    manager.start_recording("cli_test", resolution="1920x1080", fps=60, bitrate_kbps=12000)
    time.sleep(10)
    print("Stopping recording...")
    result = manager.stop_recording()
    print(f"Recording saved: {result}")

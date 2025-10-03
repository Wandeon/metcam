#!/usr/bin/env python3
from datetime import datetime
from pathlib import Path
import signal
import subprocess
import time
import shutil

class RecordingManager:
    """
    Launches two gst-launch processes that write /mnt/recordings/<match>/cam[0|1].mp4.
    """
    def __init__(self, output_root: str = "/mnt/recordings"):
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.cam0_process = None
        self.cam1_process = None
        self.match_id = None
        self.start_time = None
        self.match_dir = None

    def _build_pipeline(self, sensor_id: int, sensor_mode: int,
                        width: str, height: str, fps: int,
                        bitrate_kbps: int, output_path: Path,
                        exposure_range: str, gain_range: str) -> list:
        gop = max(fps * 2, fps)
        return [
            "gst-launch-1.0", "-e",
            "nvarguscamerasrc", f"sensor-id={sensor_id}", f"sensor-mode={sensor_mode}",
            "wbmode=1",
            "aelock=false",
            f"exposuretimerange={exposure_range}",
            f"gainrange={gain_range}",
            "ispdigitalgainrange=1 1",
            "saturation=1.0",
            "!", f"video/x-raw(memory:NVMM),width={width},height={height},framerate={fps}/1",
            "!", "queue", "max-size-buffers=20", "max-size-time=0", "max-size-bytes=0",
            "!", "nvvidconv",
            "!", "video/x-raw,format=I420",
            "!", "x264enc",
                f"bitrate={bitrate_kbps}",
                "speed-preset=ultrafast",
                f"key-int-max={gop}",
                "threads=4",
            "!", "h264parse", "config-interval=-1",
            "!", "mp4mux", "faststart=true",
            "!", "filesink", f"location={output_path}", "sync=false",
        ]

    def start_recording(self, match_id: str,
                        resolution: str = "3840x2160",
                        fps: int = 22,
                        bitrate: int = 100000) -> dict:
        if self.cam0_process or self.cam1_process:
            raise RuntimeError("Recording already in progress")

        # Set 25W power mode for maximum performance
        try:
            subprocess.run(["sudo", "nvpmodel", "-m", "1"], check=True, capture_output=True)
            subprocess.run(["sudo", "jetson_clocks"], check=True, capture_output=True)
        except Exception:
            # Log but don't fail if power mode setting fails
            pass

        self.match_id = match_id
        self.start_time = datetime.now()

        self.match_dir = self.output_root / match_id
        self.match_dir.mkdir(parents=True, exist_ok=True)

        width, height = resolution.split("x")
        sensor_mode = 1 if int(width) <= 1920 else 0

        exposure_range = "13000 33333333"  # up to 1/30 s
        gain_range = "1 10"
        bitrate_kbps = max(int(bitrate), 1)

        cam0_file = self.match_dir / "cam0.mp4"
        cam1_file = self.match_dir / "cam1.mp4"

        cam0_cmd = self._build_pipeline(
            0, sensor_mode, width, height, fps,
            bitrate_kbps, cam0_file, exposure_range, gain_range
        )
        cam1_cmd = self._build_pipeline(
            1, sensor_mode, width, height, fps,
            bitrate_kbps, cam1_file, exposure_range, gain_range
        )

        self.cam0_process = subprocess.Popen(cam0_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(0.5)
        self.cam1_process = subprocess.Popen(cam1_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(1.0)

        for idx, proc in enumerate((self.cam0_process, self.cam1_process)):
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode(errors="ignore") if proc.stderr else ""
                self.stop_recording()
                camera = f"camera {idx}"
                detail = stderr.strip() or "GStreamer pipeline failed"
                raise RuntimeError(f"Failed to start recording for {camera}: {detail}")

        return {
            "status": "recording",
            "match_id": match_id,
            "cam0_pid": self.cam0_process.pid,
            "cam1_pid": self.cam1_process.pid,
            "start_time": self.start_time.isoformat(),
        }

    def stop_recording(self) -> dict:
        if not self.cam0_process and not self.cam1_process:
            return {"status": "not_recording"}

        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0

        for proc in (self.cam0_process, self.cam1_process):
            if proc:
                try:
                    proc.send_signal(signal.SIGINT)
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                except Exception:
                    proc.kill()

        cam0_file = self.match_dir / "cam0.mp4" if self.match_dir else None
        cam1_file = self.match_dir / "cam1.mp4" if self.match_dir else None

        cam0_size = cam0_file.stat().st_size / 1024 / 1024 if cam0_file and cam0_file.exists() else 0
        cam1_size = cam1_file.stat().st_size / 1024 / 1024 if cam1_file and cam1_file.exists() else 0

        result = {
            "status": "stopped",
            "match_id": self.match_id,
            "duration_seconds": duration,
            "files": {
                "cam0": str(cam0_file) if cam0_file and cam0_file.exists() else None,
                "cam1": str(cam1_file) if cam1_file and cam1_file.exists() else None,
                "cam0_size_mb": cam0_size,
                "cam1_size_mb": cam1_size,
            },
        }

        self.cam0_process = None
        self.cam1_process = None
        self.match_id = None
        self.start_time = None
        self.match_dir = None

        return result

    def get_status(self) -> dict:
        if not self.cam0_process and not self.cam1_process:
            return {"status": "idle"}

        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0

        return {
            "status": "recording",
            "match_id": self.match_id,
            "duration_seconds": duration,
            "cam0_running": self.cam0_process.poll() is None if self.cam0_process else False,
            "cam1_running": self.cam1_process.poll() is None if self.cam1_process else False,
        }

if __name__ == "__main__":
    manager = RecordingManager()
    print("Starting 10 second test recording...")
    manager.start_recording("cli_test", resolution="1920x1080", fps=30, bitrate=50000)
    time.sleep(10)
    print("Stopping recording...")
    result = manager.stop_recording()
    print(f"Recording saved: {result['files']}")

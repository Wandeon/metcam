#!/usr/bin/env python3
"""
FootballVision Pro - HLS Preview Service
Full-frame preview at recording resolution with throttled frame rate.
"""

import signal
import subprocess
import time
from pathlib import Path


class PreviewService:
    def __init__(self, hls_dir="/var/www/footballvision/hls"):
        self.hls_dir = Path(hls_dir)
        self.cam0_process = None
        self.cam1_process = None
        self.is_streaming = False

        # Match recording resolution but keep FPS low for bandwidth
        self.width = 1920
        self.height = 1080
        self.framerate = 10
        self.preview_bitrate_kbps = 4000

    def _recording_active(self) -> bool:
        result = subprocess.run(
            "ps aux | grep 'nvarguscamerasrc.*splitmuxsink' | grep -v grep",
            shell=True,
            capture_output=True,
        )
        return result.returncode == 0 and bool(result.stdout.strip())

    def _cleanup_dir(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        for pattern in ("*.ts", "*.m3u8"):
            for item in directory.glob(pattern):
                try:
                    item.unlink()
                except FileNotFoundError:
                    pass

    def _build_pipeline(self, sensor_id: int, target_dir: Path) -> list[str]:
        return [
            "gst-launch-1.0",
            "-e",
            "nvarguscamerasrc",
            f"sensor-id={sensor_id}",
            "wbmode=1",
            "aelock=false",
            "exposuretimerange=500 4000",
            "gainrange=1 8",
            "saturation=1.2",
            "!",
            f"video/x-raw(memory:NVMM),width={self.width},height={self.height},framerate={self.framerate}/1",
            "!",
            "nvvidconv",
            "!",
            "video/x-raw,format=I420",
            "!",
            "x264enc",
            f"bitrate={self.preview_bitrate_kbps}",
            "speed-preset=ultrafast",
            "tune=zerolatency",
            f"key-int-max={self.framerate}",
            "threads=2",
            "cabac=true",
            "!",
            "h264parse",
            "!",
            "mpegtsmux",
            "!",
            "hlssink",
            f"location={target_dir}/segment%05d.ts",
            f"playlist-location={target_dir}/playlist.m3u8",
            "max-files=5",
            "target-duration=2",
            "playlist-length=3",
        ]

    def _launch_pipeline(self, sensor_id: int, target_dir: Path) -> subprocess.Popen:
        cmd = self._build_pipeline(sensor_id, target_dir)
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def _terminate_processes(self) -> None:
        for proc in (self.cam0_process, self.cam1_process):
            if not proc:
                continue
            if proc.poll() is None:
                try:
                    proc.send_signal(signal.SIGINT)
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                except Exception:
                    proc.kill()
        self.cam0_process = None
        self.cam1_process = None
        self.is_streaming = False

    def start(self) -> dict:
        if self.is_streaming:
            raise RuntimeError("Preview already streaming")
        if self._recording_active():
            raise RuntimeError("Stop the recording before starting the preview stream")

        cam0_dir = self.hls_dir / "cam0"
        cam1_dir = self.hls_dir / "cam1"
        self._cleanup_dir(cam0_dir)
        self._cleanup_dir(cam1_dir)

        self.cam0_process = self._launch_pipeline(0, cam0_dir)
        time.sleep(0.5)
        self.cam1_process = self._launch_pipeline(1, cam1_dir)
        time.sleep(1.0)

        for idx, proc in enumerate((self.cam0_process, self.cam1_process)):
            if proc and proc.poll() is not None:
                stderr = proc.stderr.read().decode(errors='ignore') if proc.stderr else ''
                self._terminate_processes()
                camera = f"camera {idx}"
                detail = stderr.strip() or "GStreamer pipeline failed"
                raise RuntimeError(f"Unable to start preview for {camera}: {detail}")

        self.is_streaming = True

        return {
            "status": "streaming",
            "resolution": f"{self.width}x{self.height}",
            "framerate": self.framerate,
            "cam0_url": "/hls/cam0/playlist.m3u8",
            "cam1_url": "/hls/cam1/playlist.m3u8",
            "cam0_pid": self.cam0_process.pid if self.cam0_process else None,
            "cam1_pid": self.cam1_process.pid if self.cam1_process else None,
        }

    def stop(self) -> dict:
        if not self.is_streaming:
            return {"status": "not_streaming"}

        self._terminate_processes()
        return {"status": "stopped"}

    def get_status(self) -> dict:
        if not self.is_streaming:
            return {"status": "idle", "streaming": False}

        cam0_running = self.cam0_process.poll() is None if self.cam0_process else False
        cam1_running = self.cam1_process.poll() is None if self.cam1_process else False

        return {
            "status": "streaming",
            "streaming": True,
            "resolution": f"{self.width}x{self.height}",
            "framerate": self.framerate,
            "cam0_running": cam0_running,
            "cam1_running": cam1_running,
            "cam0_url": "/hls/cam0/playlist.m3u8",
            "cam1_url": "/hls/cam1/playlist.m3u8",
        }


if __name__ == "__main__":
    preview = PreviewService()
    print("Starting preview stream. Press Ctrl+C to stop.")
    try:
        result = preview.start()
        print("Preview URLs:")
        print(f"  Camera 0: {result['cam0_url']}")
        print(f"  Camera 1: {result['cam1_url']}")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        preview.stop()
        print("Preview stopped.")

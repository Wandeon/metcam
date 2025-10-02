#!/usr/bin/env python3
"""
FootballVision Pro - Recording Manager
Real GStreamer implementation for dual camera recording
"""

import subprocess
import signal
import time
from pathlib import Path
from datetime import datetime

class RecordingManager:
    def __init__(self, output_dir="/mnt/recordings"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cam0_process = None
        self.cam1_process = None
        self.match_id = None
        self.start_time = None

    def start_recording(self, match_id, resolution="3840x2160", fps=22, bitrate=100000):
        """Start dual camera recording - 4K@30fps or 1080p@60fps max"""
        if self.cam0_process or self.cam1_process:
            raise RuntimeError("Recording already in progress")

        self.match_id = match_id
        self.start_time = datetime.now()
        width, height = resolution.split('x')

        # Determine sensor mode based on resolution
        # mode 0: 4K (4032x3040 @ 21fps), mode 1: 1080p (1920x1080 @ 60fps)
        sensor_mode = 1 if int(width) <= 1920 else 0

        # Sports recording constraints:
        # - Minimum shutter speed: 1/250s (4ms = 4,000,000 ns) to freeze motion
        # - Maximum ISO ~1600 (analog gain ~8.0) to limit noise
        # Sensor exposure range: 13,000 ns to 683,709,000 ns
        # Sensor gain range: 1.0 to 22.25
        exposure_range = "4000000 683709000"  # 4ms to 683ms (1/250s to max)
        gain_range = "1 8"  # ISO 100 to ~1600 equivalent

        # Camera 0 pipeline - Software H.264 encoder (x264) with constant framerate
        cam0_cmd = [
            'gst-launch-1.0', '-e',
            'nvarguscamerasrc', 'sensor-id=0', f'sensor-mode={sensor_mode}',
            f'exposuretimerange={exposure_range}', f'gainrange={gain_range}',
            '!', f'video/x-raw(memory:NVMM),width={width},height={height},framerate={fps}/1',
            '!', 'nvvidconv',
            '!', f'video/x-raw,format=I420,framerate={fps}/1',
            '!', 'videorate',  # Force constant framerate
            '!', f'video/x-raw,framerate={fps}/1',
            '!', 'x264enc', f'bitrate={bitrate}', 'speed-preset=ultrafast', 'tune=zerolatency', 'key-int-max=30',
            '!', 'h264parse',
            '!', 'qtmux',
            '!', 'filesink', f'location={self.output_dir}/{match_id}_cam0.mp4'
        ]

        # Camera 1 pipeline - Software H.264 encoder (x264) with constant framerate
        cam1_cmd = [
            'gst-launch-1.0', '-e',
            'nvarguscamerasrc', 'sensor-id=1', f'sensor-mode={sensor_mode}',
            f'exposuretimerange={exposure_range}', f'gainrange={gain_range}',
            '!', f'video/x-raw(memory:NVMM),width={width},height={height},framerate={fps}/1',
            '!', 'nvvidconv',
            '!', f'video/x-raw,format=I420,framerate={fps}/1',
            '!', 'videorate',  # Force constant framerate
            '!', f'video/x-raw,framerate={fps}/1',
            '!', 'x264enc', f'bitrate={bitrate}', 'speed-preset=ultrafast', 'tune=zerolatency', 'key-int-max=30',
            '!', 'h264parse',
            '!', 'qtmux',
            '!', 'filesink', f'location={self.output_dir}/{match_id}_cam1.mp4'
        ]

        # Start both pipelines
        self.cam0_process = subprocess.Popen(cam0_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(0.5)  # Stagger startup
        self.cam1_process = subprocess.Popen(cam1_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

        print(f"Recording started: {match_id}")
        print(f"  Resolution: {resolution}")
        print(f"  Output: {self.output_dir}")

        return {
            'status': 'recording',
            'match_id': match_id,
            'cam0_pid': self.cam0_process.pid,
            'cam1_pid': self.cam1_process.pid,
            'start_time': self.start_time.isoformat()
        }

    def stop_recording(self):
        """Stop recording gracefully"""
        if not self.cam0_process and not self.cam1_process:
            return {'status': 'not_recording'}

        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0

        # Send SIGINT for graceful shutdown (allows muxer to finalize)
        if self.cam0_process:
            self.cam0_process.send_signal(signal.SIGINT)
        if self.cam1_process:
            self.cam1_process.send_signal(signal.SIGINT)

        # Wait for processes to finish
        if self.cam0_process:
            self.cam0_process.wait(timeout=5)
        if self.cam1_process:
            self.cam1_process.wait(timeout=5)

        # Get file sizes
        cam0_file = self.output_dir / f"{self.match_id}_cam0.mp4"
        cam1_file = self.output_dir / f"{self.match_id}_cam1.mp4"

        result = {
            'status': 'stopped',
            'match_id': self.match_id,
            'duration_seconds': duration,
            'files': {
                'cam0': str(cam0_file) if cam0_file.exists() else None,
                'cam1': str(cam1_file) if cam1_file.exists() else None,
                'cam0_size_mb': cam0_file.stat().st_size / 1024 / 1024 if cam0_file.exists() else 0,
                'cam1_size_mb': cam1_file.stat().st_size / 1024 / 1024 if cam1_file.exists() else 0,
            }
        }

        # Reset state
        self.cam0_process = None
        self.cam1_process = None
        self.match_id = None
        self.start_time = None

        print(f"Recording stopped: {result}")
        return result

    def get_status(self):
        """Get current recording status"""
        if not self.cam0_process and not self.cam1_process:
            return {'status': 'idle'}

        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0

        return {
            'status': 'recording',
            'match_id': self.match_id,
            'duration_seconds': duration,
            'cam0_running': self.cam0_process.poll() is None if self.cam0_process else False,
            'cam1_running': self.cam1_process.poll() is None if self.cam1_process else False,
        }


if __name__ == "__main__":
    # Test the recording manager
    manager = RecordingManager()

    print("Starting 10 second test recording...")
    manager.start_recording("cli_test", resolution="1920x1080")

    time.sleep(10)

    print("Stopping recording...")
    result = manager.stop_recording()
    print(f"Recording saved: {result['files']}")

#!/usr/bin/env python3
"""
FootballVision Pro - HLS Preview Service
Full HD (1920x1080) @ 30fps preview stream for web UI
"""

import subprocess
import os
import signal
import time
from pathlib import Path
from datetime import datetime

class PreviewService:
    def __init__(self, hls_dir="/var/www/footballvision/hls"):
        self.hls_dir = Path(hls_dir)
        self.cam0_process = None
        self.cam1_process = None
        self.is_streaming = False

        # 720p at 10fps for preview (optimized for streaming)
        self.width = 1280
        self.height = 720
        self.framerate = 10

    def start(self):
        """Start HLS preview streams for both cameras"""
        if self.is_streaming:
            raise RuntimeError("Preview already streaming")

        # Create HLS directories
        cam0_dir = self.hls_dir / "cam0"
        cam1_dir = self.hls_dir / "cam1"
        cam0_dir.mkdir(parents=True, exist_ok=True)
        cam1_dir.mkdir(parents=True, exist_ok=True)

        # Clean old segments
        for f in cam0_dir.glob("*.ts"):
            f.unlink()
        for f in cam0_dir.glob("*.m3u8"):
            f.unlink()
        for f in cam1_dir.glob("*.ts"):
            f.unlink()
        for f in cam1_dir.glob("*.m3u8"):
            f.unlink()

        # Camera 0 HLS pipeline - Full HD @ 30fps
        cam0_cmd = [
            'gst-launch-1.0',
            'nvarguscamerasrc', 'sensor-id=0',
            '!', f'video/x-raw(memory:NVMM),width={self.width},height={self.height},framerate={self.framerate}/1',
            '!', 'nvvidconv',
            '!', 'video/x-raw,format=I420',
            '!', 'x264enc', 'bitrate=3000', 'speed-preset=ultrafast', 'tune=zerolatency', 'key-int-max=40',
            '!', 'h264parse',
            '!', 'mpegtsmux',
            '!', 'hlssink',
                f'location={cam0_dir}/segment%05d.ts',
                f'playlist-location={cam0_dir}/playlist.m3u8',
                'max-files=5',
                'target-duration=4',
                'playlist-length=3'
        ]

        # Camera 1 HLS pipeline - Full HD @ 30fps
        cam1_cmd = [
            'gst-launch-1.0',
            'nvarguscamerasrc', 'sensor-id=1',
            '!', f'video/x-raw(memory:NVMM),width={self.width},height={self.height},framerate={self.framerate}/1',
            '!', 'nvvidconv',
            '!', 'video/x-raw,format=I420',
            '!', 'x264enc', 'bitrate=3000', 'speed-preset=ultrafast', 'tune=zerolatency', 'key-int-max=40',
            '!', 'h264parse',
            '!', 'mpegtsmux',
            '!', 'hlssink',
                f'location={cam1_dir}/segment%05d.ts',
                f'playlist-location={cam1_dir}/playlist.m3u8',
                'max-files=5',
                'target-duration=4',
                'playlist-length=3'
        ]

        print(f"[PreviewService] Starting HLS streams at {self.width}x{self.height}@{self.framerate}fps")
        print(f"[PreviewService] HLS directory: {self.hls_dir}")

        # Start both pipelines
        self.cam0_process = subprocess.Popen(
            cam0_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        time.sleep(1)  # Stagger startup

        self.cam1_process = subprocess.Popen(
            cam1_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

        self.is_streaming = True

        return {
            'status': 'streaming',
            'resolution': f'{self.width}x{self.height}',
            'framerate': self.framerate,
            'cam0_url': 'https://vid.nk-otok.hr/hls/cam0/playlist.m3u8',
            'cam1_url': 'https://vid.nk-otok.hr/hls/cam1/playlist.m3u8',
            'cam0_pid': self.cam0_process.pid,
            'cam1_pid': self.cam1_process.pid
        }

    def stop(self):
        """Stop HLS preview streams"""
        if not self.is_streaming:
            return {'status': 'not_streaming'}

        # Send SIGINT for graceful shutdown
        if self.cam0_process:
            self.cam0_process.send_signal(signal.SIGINT)
            self.cam0_process.wait(timeout=5)

        if self.cam1_process:
            self.cam1_process.send_signal(signal.SIGINT)
            self.cam1_process.wait(timeout=5)

        self.cam0_process = None
        self.cam1_process = None
        self.is_streaming = False

        print("[PreviewService] Stopped HLS streams")

        return {'status': 'stopped'}

    def get_status(self):
        """Get current preview status"""
        if not self.is_streaming:
            return {
                'status': 'idle',
                'streaming': False
            }

        cam0_running = self.cam0_process.poll() is None if self.cam0_process else False
        cam1_running = self.cam1_process.poll() is None if self.cam1_process else False

        return {
            'status': 'streaming',
            'streaming': True,
            'resolution': f'{self.width}x{self.height}',
            'framerate': self.framerate,
            'cam0_running': cam0_running,
            'cam1_running': cam1_running,
            'cam0_url': 'https://vid.nk-otok.hr/hls/cam0/playlist.m3u8',
            'cam1_url': 'https://vid.nk-otok.hr/hls/cam1/playlist.m3u8'
        }


if __name__ == "__main__":
    # Test the preview service
    preview = PreviewService()

    print("Starting preview stream for 30 seconds...")
    result = preview.start()
    print(f"Preview URLs:")
    print(f"  Camera 0: {result['cam0_url']}")
    print(f"  Camera 1: {result['cam1_url']}")

    time.sleep(30)

    print("Stopping preview...")
    preview.stop()

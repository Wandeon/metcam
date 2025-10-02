#!/usr/bin/env python3
"""
Simple side-by-side video processor
Combines two camera feeds horizontally without complex stitching
"""

import subprocess
import sys
import os
from pathlib import Path
import time

def create_sidebyside(cam0_path: str, cam1_path: str, output_path: str, progress_callback=None):
    """
    Create side-by-side video using ffmpeg

    Args:
        cam0_path: Path to camera 0 video
        cam1_path: Path to camera 1 video
        output_path: Path for output video
        progress_callback: Optional callback for progress updates
    """

    if progress_callback:
        progress_callback(0, "Starting processing...")

    # Check input files exist
    if not os.path.exists(cam0_path):
        raise FileNotFoundError(f"Camera 0 file not found: {cam0_path}")
    if not os.path.exists(cam1_path):
        raise FileNotFoundError(f"Camera 1 file not found: {cam1_path}")

    if progress_callback:
        progress_callback(10, "Validating input files...")

    # Get video duration for progress tracking
    duration_cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {cam0_path}"
    duration_str = subprocess.check_output(duration_cmd, shell=True).decode().strip()
    total_duration = float(duration_str)

    if progress_callback:
        progress_callback(20, "Creating side-by-side layout...")

    # FFmpeg command for side-by-side with scaling
    # Scales each camera to 1920x1080, then places side-by-side = 3840x1080
    cmd = f"""ffmpeg -y \
        -i {cam0_path} \
        -i {cam1_path} \
        -filter_complex "\
            [0:v]scale=1920:1080,setsar=1[left]; \
            [1:v]scale=1920:1080,setsar=1[right]; \
            [left][right]hstack=inputs=2[v]" \
        -map "[v]" \
        -c:v libx264 \
        -preset medium \
        -crf 23 \
        -movflags +faststart \
        {output_path} \
        -progress pipe:1 2>&1
    """

    print(f"[Processing] Starting ffmpeg...")
    print(f"[Processing] Output: {output_path}")

    # Run ffmpeg and track progress
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )

    last_progress = 20
    for line in process.stdout:
        # Parse ffmpeg progress
        if "time=" in line:
            try:
                time_str = line.split("time=")[1].split()[0]
                h, m, s = time_str.split(":")
                current_time = int(h) * 3600 + int(m) * 60 + float(s)
                progress = 20 + int((current_time / total_duration) * 70)

                if progress > last_progress:
                    last_progress = progress
                    if progress_callback:
                        progress_callback(progress, f"Processing... {current_time:.0f}s / {total_duration:.0f}s")
            except:
                pass

    process.wait()

    if process.returncode != 0:
        raise RuntimeError("FFmpeg processing failed")

    if progress_callback:
        progress_callback(90, "Finalizing video...")

    # Verify output exists and has size
    if not os.path.exists(output_path):
        raise RuntimeError("Output file was not created")

    output_size = os.path.getsize(output_path) / (1024**3)  # GB

    if progress_callback:
        progress_callback(100, f"Complete! Output: {output_size:.2f} GB")

    return {
        'success': True,
        'output_path': output_path,
        'output_size_gb': output_size,
        'duration_seconds': total_duration
    }


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: python3 simple_sidebyside.py <cam0.mp4> <cam1.mp4> <output.mp4>")
        sys.exit(1)

    def print_progress(percent, message):
        print(f"[{percent}%] {message}")

    try:
        result = create_sidebyside(
            sys.argv[1],
            sys.argv[2],
            sys.argv[3],
            progress_callback=print_progress
        )
        print(f"\n✅ Success!")
        print(f"   Output: {result['output_path']}")
        print(f"   Size: {result['output_size_gb']:.2f} GB")
        print(f"   Duration: {result['duration_seconds']:.0f} seconds")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

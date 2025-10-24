#!/usr/bin/env python3
"""
Pipeline builders for FootballVision Pro
Constructs GStreamer pipeline strings for recording and preview
"""

import json
import os
from typing import Dict, Tuple


def load_camera_config(config_path: str = "/home/mislav/footballvision-pro/config/camera_config.json") -> Dict:
    """Load camera configuration from JSON file"""
    with open(config_path, 'r') as f:
        return json.load(f)


def pixel_count_to_edge_coords(crop: Dict[str, int], input_width: int = 3840, input_height: int = 2160) -> Tuple[int, int, int, int]:
    """
    Convert pixel count crop to edge coordinates for nvvidconv
    
    Args:
        crop: Dict with 'left', 'right', 'top', 'bottom' pixel counts to remove
        input_width: Input video width (default 3840 for 4K)
        input_height: Input video height (default 2160 for 4K)
    
    Returns:
        Tuple of (left_edge, right_edge, top_edge, bottom_edge) coordinates
    """
    left_edge = crop['left']
    right_edge = input_width - crop['right']
    top_edge = crop['top']
    bottom_edge = input_height - crop['bottom']
    
    return left_edge, right_edge, top_edge, bottom_edge


def build_recording_pipeline(camera_id: int, output_pattern: str, config_path: str = None) -> str:
    """
    Build GStreamer pipeline string for recording
    
    Args:
        camera_id: Camera sensor ID (0 or 1)
        output_pattern: Output file pattern for splitmuxsink (e.g., "/path/cam0_%05d.mkv")
        config_path: Optional path to camera config JSON
    
    Returns:
        GStreamer pipeline description string
    """
    # Load camera config
    config = load_camera_config(config_path) if config_path else load_camera_config()
    cam_config = config['cameras'][str(camera_id)]
    
    # nvvidconv wants pixels to TRIM from edges, not edge coordinates
    crop = cam_config['crop']
    left = crop['left']
    right = crop['right']
    top = crop['top']
    bottom = crop['bottom']
    
    # Calculate output dimensions
    output_width = 3840 - left - right
    output_height = 2160 - top - bottom
    
    # Build pipeline string
    pipeline = (
        f"nvarguscamerasrc name=src sensor-mode=0 sensor-id={camera_id} "
        "tnr-mode=0 ee-mode=0 wbmode=1 aelock=false "
        'exposuretimerange="13000 33000000" gainrange="1 16" '
        'ispdigitalgainrange="1 4" saturation=1.0 ! '
        "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1,format=NV12 ! "

        # Convert NVMM to system memory first (no crop yet)
        "nvvidconv ! "
        "video/x-raw,format=NV12,width=3840,height=2160,framerate=30/1 ! "

        # CPU crop using videocrop (preserves chroma correctly)
        f"videocrop left={left} right={right} top={top} bottom={bottom} ! "
        f"video/x-raw,format=NV12,width={output_width},height={output_height},framerate=30/1,"
        f"colorimetry=bt709,interlace-mode=progressive ! "

        # Step 2 - CPU colorspace conversion NV12 → I420
        "videoconvert ! "
        f"video/x-raw,format=I420,width={output_width},height={output_height},framerate=30/1,"
        f"colorimetry=bt709,interlace-mode=progressive ! "

        # Encode to H.264 at 12 Mbps with optimized settings
        "x264enc name=enc speed-preset=ultrafast tune=zerolatency "
        "bitrate=12000 key-int-max=60 b-adapt=false bframes=0 "
        "aud=true byte-stream=false option-string=repeat-headers=1:scenecut=0:open-gop=0 ! "
        "h264parse config-interval=-1 disable-passthrough=true ! "
        "video/x-h264,stream-format=avc ! "
        
        # Segment into 10-minute chunks as MP4
        "splitmuxsink name=sink "
        f"location={output_pattern} "
        "max-size-time=600000000000 "
        "muxer-factory=mp4mux "
        "async-finalize=true"
    )
    
    return pipeline


def build_preview_pipeline(camera_id: int, hls_location: str, config_path: str = None) -> str:
    """
    Build GStreamer pipeline string for HLS preview
    
    Args:
        camera_id: Camera sensor ID (0 or 1)
        hls_location: Base path for HLS playlist (e.g., "/tmp/hls/cam0.m3u8")
        config_path: Optional path to camera config JSON
    
    Returns:
        GStreamer pipeline description string
    """
    # Load camera config
    config = load_camera_config(config_path) if config_path else load_camera_config()
    cam_config = config['cameras'][str(camera_id)]
    
    # nvvidconv wants pixels to TRIM from edges, not edge coordinates
    crop = cam_config['crop']
    left = crop['left']
    right = crop['right']
    top = crop['top']
    bottom = crop['bottom']
    
    # Calculate output dimensions
    output_width = 3840 - left - right
    output_height = 2160 - top - bottom
    
    # Build pipeline string
    pipeline = (
        f"nvarguscamerasrc name=src sensor-mode=0 sensor-id={camera_id} "
        "tnr-mode=0 ee-mode=0 wbmode=1 aelock=false "
        'exposuretimerange="13000 33000000" gainrange="1 16" '
        'ispdigitalgainrange="1 4" saturation=1.0 ! '
        "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1,format=NV12 ! "

        # Convert NVMM to system memory first (no crop yet)
        "nvvidconv ! "
        "video/x-raw,format=NV12,width=3840,height=2160,framerate=30/1 ! "

        # CPU crop using videocrop (preserves chroma correctly)
        f"videocrop left={left} right={right} top={top} bottom={bottom} ! "
        f"video/x-raw,format=NV12,width={output_width},height={output_height},framerate=30/1,"
        f"colorimetry=bt709,interlace-mode=progressive ! "

        # Step 2 - CPU colorspace conversion NV12 → I420
        "videoconvert ! "
        f"video/x-raw,format=I420,width={output_width},height={output_height},framerate=30/1,"
        f"colorimetry=bt709,interlace-mode=progressive ! "

        # Software H.264 encoder with deterministic GOP (IDR every 60 frames)
        "x264enc name=enc speed-preset=ultrafast tune=zerolatency "
        "bitrate=3000 key-int-max=60 b-adapt=false bframes=0 "
        "byte-stream=true aud=true intra-refresh=false "
        "option-string=repeat-headers=1:scenecut=0:open-gop=0 ! "
        
        # Normalize stream for HLS segmenter (force parsing + AU alignment)
        "h264parse config-interval=1 disable-passthrough=true ! "
        "video/x-h264,stream-format=byte-stream ! "

        # MPEG-TS muxer with alignment before HLS
        
        # HLS output (2s segments, keeps recent segments/playlist fresh)
        "hlssink2 name=sink "
        f"playlist-location={hls_location} "
        f"location={hls_location.replace('.m3u8', '_%05d.ts')} "
        "target-duration=2 "
        "playlist-length=8 "
        "max-files=8 "
        "send-keyframe-requests=true"
    )
    
    return pipeline

"""GStreamer pipeline builders for the preview/recording services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple


# Camera sensor characteristics (IMX477 – 12.3MP sensor in 4K mode)
# Using sensor-mode=0 which provides 3840×2160@30fps
SENSOR_WIDTH = 3840
SENSOR_HEIGHT = 2160
SENSOR_FORMAT = "NV12"


def _resolve_config_path(config_path: str | None = None) -> Path:
    """Resolve the configuration file path.

    The historic implementation hard-coded a developer specific path, which
    breaks when the repository is deployed to a different device.  We instead
    resolve the path relative to the repository root (``config/camera_config.json``)
    unless an explicit ``config_path`` is provided.
    """

    if config_path is not None:
        return Path(config_path)

    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "config" / "camera_config.json"


def load_camera_config(config_path: str | None = None) -> Dict:
    """Load camera configuration from JSON file."""

    path = _resolve_config_path(config_path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def pixel_count_to_edge_coords(
    crop: Dict[str, int],
    input_width: int = SENSOR_WIDTH,
    input_height: int = SENSOR_HEIGHT,
) -> Tuple[int, int, int, int]:
    """Convert pixel count crop to edge coordinates for nvvidconv."""

    left_edge = crop["left"]
    right_edge = input_width - crop["right"]
    top_edge = crop["top"]
    bottom_edge = input_height - crop["bottom"]

    return left_edge, right_edge, top_edge, bottom_edge


def _build_camera_source(camera_id: int, cam_config: Dict[str, Any]) -> Tuple[str, int, int]:
    """Build the common camera → CPU colour space conversion pipeline section.

    This function creates a GStreamer pipeline that:
    1. Captures video from nvarguscamerasrc (NVIDIA Argus camera)
    2. Crops the video using VIC hardware acceleration
    3. Converts color space using VIC (NVMM to I420)

    CRITICAL: nvvidconv crop coordinate system
    ==========================================
    The nvvidconv element uses a BOUNDING BOX coordinate system, NOT pixel counts.

    nvvidconv properties:
      - left   = X coordinate where cropped region STARTS (pixels from left edge)
      - right  = X coordinate where cropped region ENDS (pixels from left edge)
      - top    = Y coordinate where cropped region STARTS (pixels from top edge)
      - bottom = Y coordinate where cropped region ENDS (pixels from top edge)

    Config file format (camera_config.json):
      - left   = pixels to REMOVE from left edge
      - right  = pixels to REMOVE from right edge
      - top    = pixels to REMOVE from top edge
      - bottom = pixels to REMOVE from bottom edge

    Example with 3840x2160 sensor and config {"left": 480, "right": 480, "top": 272, "bottom": 272}:
      Config interpretation:
        - Remove 480px from left edge
        - Remove 480px from right edge
        - Remove 272px from top edge
        - Remove 272px from bottom edge

      nvvidconv coordinates:
        - left   = 480 (start X at 480px from left)
        - right  = 3360 (end X at 3840 - 480 = 3360px from left)
        - top    = 272 (start Y at 272px from top)
        - bottom = 1888 (end Y at 2160 - 272 = 1888px from top)

      Output size: 2880x1616 (3840 - 480 - 480 = 2880, 2160 - 272 - 272 = 1616)

    Common mistakes:
      ❌ Using "src-crop" property (doesn't exist)
      ❌ Passing crop pixel counts directly as coordinates
      ❌ Using negative values or coordinates outside sensor dimensions

    Hardware acceleration:
      - VIC (Video Image Compositor) performs crop in hardware
      - Zero-copy operation (stays in NVMM memory)
      - Typical VIC utilization: 60-90% during dual-camera preview
      - CPU utilization: ~60-70%

    Args:
        camera_id: Camera sensor ID (0 or 1)
        cam_config: Camera configuration dict from camera_config.json

    Returns:
        Tuple of (pipeline_string, output_width, output_height)
    """

    crop = cam_config.get("crop", {})
    crop_left = int(crop.get("left", 0))      # Pixels to remove from left edge
    crop_right = int(crop.get("right", 0))    # Pixels to remove from right edge
    crop_top = int(crop.get("top", 0))        # Pixels to remove from top edge
    crop_bottom = int(crop.get("bottom", 0))  # Pixels to remove from bottom edge

    # Clamp in case a config accidentally overshoots the sensor dimensions.
    crop_left = max(0, min(crop_left, SENSOR_WIDTH))
    crop_right = max(0, min(crop_right, SENSOR_WIDTH - crop_left))
    crop_top = max(0, min(crop_top, SENSOR_HEIGHT))
    crop_bottom = max(0, min(crop_bottom, SENSOR_HEIGHT - crop_top))

    # Calculate output dimensions after cropping
    output_width = max(16, SENSOR_WIDTH - crop_left - crop_right)
    output_height = max(16, SENSOR_HEIGHT - crop_top - crop_bottom)

    # Convert config crop values (pixels to remove) to nvvidconv bounding box coordinates
    # nvvidconv uses: left=start_x right=end_x top=start_y bottom=end_y
    cropper_props = ""
    if any((crop_left, crop_right, crop_top, crop_bottom)):
        # Bounding box coordinates: (left_coord, top_coord) to (right_coord, bottom_coord)
        left_coord = crop_left                      # Start X = pixels removed from left
        right_coord = SENSOR_WIDTH - crop_right     # End X = sensor_width - pixels removed from right
        top_coord = crop_top                        # Start Y = pixels removed from top
        bottom_coord = SENSOR_HEIGHT - crop_bottom  # End Y = sensor_height - pixels removed from bottom

        cropper_props = f" left={left_coord} right={right_coord} top={top_coord} bottom={bottom_coord}"

    # Get exposure compensation from config (default 0.0 for no adjustment)
    exposure_compensation = cam_config.get("exposure_compensation", 0.0)

    pipeline = (
        f"nvarguscamerasrc name=src sensor-mode=0 sensor-id={camera_id} "
        "tnr-mode=1 ee-mode=1 wbmode=1 aelock=false "
        f"aeantibanding=3 exposurecompensation={exposure_compensation} "
        'exposuretimerange="13000 33000000" gainrange="1 16" '
        'ispdigitalgainrange="1 1" saturation=1.0 ! '
        f"video/x-raw(memory:NVMM),width={SENSOR_WIDTH},height={SENSOR_HEIGHT},"
        f"format={SENSOR_FORMAT} ! "

        # VIC crop in NVMM
        f"nvvidconv name=cropper{cropper_props} ! "
        f"video/x-raw(memory:NVMM),format={SENSOR_FORMAT},width={output_width},"
        f"height={output_height} ! "

        # Hardware colour conversion to CPU memory for x264enc
        "nvvidconv ! "
        f"video/x-raw,format=I420,width={output_width},height={output_height},"
        f"colorimetry=bt709,interlace-mode=progressive ! "
    )

    return pipeline, output_width, output_height


def build_recording_pipeline(camera_id: int, output_pattern: str, config_path: str = None, quality_preset: str = "high") -> str:
    """Build GStreamer pipeline string for recording.

    Args:
        camera_id: Camera sensor ID (0 or 1)
        output_pattern: Output file pattern for splitmuxsink
        config_path: Path to camera config JSON
        quality_preset: Recording quality preset - "high" (default), "balanced", or "fast"

    Quality Presets:
        high: Best quality for archival (veryfast preset, bframes=3, 25Mbps, tune=film)
              ~25-40% better quality, +15-20% CPU usage
        balanced: Good quality with moderate CPU (fast preset, bframes=2, 22Mbps, tune=film)
              ~15-25% better quality, +10-15% CPU usage
        fast: Original settings for maximum compatibility (ultrafast, no bframes, 20Mbps)
              Lowest CPU, fastest encoding
    """

    config = load_camera_config(config_path)
    cam_config = config["cameras"][str(camera_id)]

    source_section, _, _ = _build_camera_source(camera_id, cam_config)

    # Define quality presets
    presets = {
        "high": {
            "speed_preset": "veryfast",
            "tune": 0x00000000,  # No tune flags (not zerolatency)
            "psy_tune": "film",
            "bitrate": 25000,
            "key_int_max": 90,
            "bframes": 3,
            "b_adapt": "true",
            "options": "repeat-headers=1:scenecut=0:open-gop=0:ref=3:rc-lookahead=30:qpmin=18:qpmax=32:vbv-maxrate=25000:vbv-bufsize=50000"
        },
        "balanced": {
            "speed_preset": "fast",
            "tune": 0x00000000,  # No tune flags
            "psy_tune": "film",
            "bitrate": 22000,
            "key_int_max": 75,
            "bframes": 2,
            "b_adapt": "true",
            "options": "repeat-headers=1:scenecut=0:open-gop=0:ref=2:rc-lookahead=20:qpmin=18:qpmax=32:vbv-maxrate=22000:vbv-bufsize=44000"
        },
        "fast": {
            "speed_preset": "ultrafast",
            "tune": 0x00000000,  # No tune flags (removed zerolatency to allow bframes)
            "psy_tune": "none",
            "bitrate": 20000,
            "key_int_max": 90,
            "bframes": 3,
            "b_adapt": "true",
            "options": "repeat-headers=1:scenecut=0:open-gop=0:vbv-maxrate=20000:vbv-bufsize=40000"
        }
    }

    # Default to "high" if invalid preset provided
    preset = presets.get(quality_preset, presets["high"])

    pipeline = "".join(
        [
            source_section,
            # Queue isolation protects camera capture from encoder/sink backpressure.
            "queue name=preenc_queue max-size-time=2000000000 max-size-buffers=0 max-size-bytes=0 leaky=downstream ! ",
            f"x264enc name=enc speed-preset={preset['speed_preset']} tune={preset['tune']} ",
            f"psy-tune={preset['psy_tune']} threads=0 ",
            f"bitrate={preset['bitrate']} key-int-max={preset['key_int_max']} ",
            f"b-adapt={preset['b_adapt']} bframes={preset['bframes']} ",
            f"aud=true byte-stream=false option-string={preset['options']} ! ",
            "queue name=postenc_queue max-size-time=2000000000 max-size-buffers=0 max-size-bytes=0 leaky=downstream ! ",
            "h264parse config-interval=-1 disable-passthrough=true ! ",
            "video/x-h264,stream-format=avc ! ",
            "queue name=mux_queue max-size-time=2000000000 max-size-buffers=0 max-size-bytes=0 leaky=downstream ! ",
            "splitmuxsink name=sink ",
            f"location={output_pattern} ",
            "max-size-time=600000000000 ",
            "muxer-factory=mp4mux ",
            "async-finalize=true",
        ]
    )

    return pipeline


def build_preview_pipeline(camera_id: int, hls_location: str, config_path: str = None) -> str:
    """Build GStreamer pipeline string for HLS preview."""

    config = load_camera_config(config_path)
    cam_config = config["cameras"][str(camera_id)]

    source_section, _, _ = _build_camera_source(camera_id, cam_config)

    pipeline = "".join(
        [
            source_section,
            "x264enc name=enc speed-preset=ultrafast tune=zerolatency threads=0 ",
            "bitrate=6000 key-int-max=60 b-adapt=false bframes=0 ",
            "byte-stream=true aud=true intra-refresh=false ",
            "option-string=repeat-headers=1:scenecut=0:open-gop=0 ! ",
            "h264parse config-interval=1 disable-passthrough=true ! ",
            "video/x-h264,stream-format=byte-stream ! ",
            "hlssink2 name=sink ",
            f"playlist-location={hls_location} ",
            f"location={hls_location.replace('.m3u8', '_%05d.ts')} ",
            "target-duration=2 ",
            "playlist-length=8 ",
            "max-files=8 ",
            "send-keyframe-requests=true",
        ]
    )

    return pipeline


def build_panorama_capture_pipeline(
    camera_id: int,
    config_path: str = None
) -> str:
    """
    Build GStreamer pipeline for panorama frame capture with HLS output.

    This pipeline extracts frames via appsink for panorama stitching while
    also providing an HLS preview stream for calibration monitoring.

    Args:
        camera_id: Camera sensor ID (0 or 1)
        config_path: Path to camera config (default: standard location)

    Returns:
        GStreamer pipeline string
    """

    config = load_camera_config(config_path)
    cam_config = config["cameras"][str(camera_id)]

    source_section, _, _ = _build_camera_source(camera_id, cam_config)

    hls_location = f"/dev/shm/hls/panorama_cam{camera_id}.m3u8"

    pipeline = "".join(
        [
            source_section,
            "tee name=t ! ",

            # Branch 1: HLS output for preview
            "queue ! ",
            "x264enc name=enc speed-preset=ultrafast tune=zerolatency threads=0 ",
            "bitrate=6000 key-int-max=60 b-adapt=false bframes=0 ",
            "byte-stream=true aud=true intra-refresh=false ",
            "option-string=repeat-headers=1:scenecut=0:open-gop=0 ! ",
            "h264parse config-interval=1 disable-passthrough=true ! ",
            "video/x-h264,stream-format=byte-stream ! ",
            "hlssink2 name=sink ",
            f"playlist-location={hls_location} ",
            f"location={hls_location.replace('.m3u8', '_%05d.ts')} ",
            "target-duration=2 ",
            "playlist-length=8 ",
            "max-files=8 ",
            "send-keyframe-requests=true ",

            # Branch 2: appsink for frame extraction
            "t. ! ",
            "queue max-size-buffers=2 leaky=downstream ! ",
            "appsink name=appsink emit-signals=true max-buffers=1 drop=true sync=false",
        ]
    )

    return pipeline

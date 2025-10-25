"""GStreamer pipeline builders for the preview/recording services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple


# Camera sensor characteristics (IMX274 – 4K @ 30fps)
SENSOR_WIDTH = 3840
SENSOR_HEIGHT = 2160
SENSOR_FRAMERATE = "30/1"
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
    """Build the common camera → CPU colour space conversion pipeline section."""

    crop = cam_config.get("crop", {})
    crop_left = int(crop.get("left", 0))
    crop_right = int(crop.get("right", 0))
    crop_top = int(crop.get("top", 0))
    crop_bottom = int(crop.get("bottom", 0))

    # Clamp in case a config accidentally overshoots the sensor dimensions.
    crop_left = max(0, min(crop_left, SENSOR_WIDTH))
    crop_right = max(0, min(crop_right, SENSOR_WIDTH - crop_left))
    crop_top = max(0, min(crop_top, SENSOR_HEIGHT))
    crop_bottom = max(0, min(crop_bottom, SENSOR_HEIGHT - crop_top))

    output_width = max(16, SENSOR_WIDTH - crop_left - crop_right)
    output_height = max(16, SENSOR_HEIGHT - crop_top - crop_bottom)

    # Convert crop pixels to nvvidconv coordinates
    # nvvidconv uses: left=start_x right=end_x top=start_y bottom=end_y
    cropper_props = ""
    if any((crop_left, crop_right, crop_top, crop_bottom)):
        left_coord = crop_left
        right_coord = SENSOR_WIDTH - crop_right
        top_coord = crop_top
        bottom_coord = SENSOR_HEIGHT - crop_bottom
        cropper_props = f" left={left_coord} right={right_coord} top={top_coord} bottom={bottom_coord}"

    pipeline = (
        f"nvarguscamerasrc name=src sensor-mode=0 sensor-id={camera_id} "
        "tnr-mode=0 ee-mode=0 wbmode=1 aelock=false "
        'exposuretimerange="13000 33000000" gainrange="1 16" '
        'ispdigitalgainrange="1 4" saturation=1.0 ! '
        f"video/x-raw(memory:NVMM),width={SENSOR_WIDTH},height={SENSOR_HEIGHT},"
        f"framerate={SENSOR_FRAMERATE},format={SENSOR_FORMAT} ! "

        # VIC crop in NVMM
        f"nvvidconv name=cropper{cropper_props} ! "
        f"video/x-raw(memory:NVMM),format={SENSOR_FORMAT},width={output_width},"
        f"height={output_height},framerate={SENSOR_FRAMERATE} ! "

        # Hardware colour conversion to CPU memory for x264enc
        "nvvidconv ! "
        f"video/x-raw,format=I420,width={output_width},height={output_height},"
        f"framerate={SENSOR_FRAMERATE},colorimetry=bt709,interlace-mode=progressive ! "
    )

    return pipeline, output_width, output_height


def build_recording_pipeline(camera_id: int, output_pattern: str, config_path: str = None) -> str:
    """Build GStreamer pipeline string for recording."""

    config = load_camera_config(config_path)
    cam_config = config["cameras"][str(camera_id)]

    source_section, _, _ = _build_camera_source(camera_id, cam_config)

    pipeline = "".join(
        [
            source_section,
            "x264enc name=enc speed-preset=ultrafast tune=zerolatency ",
            "bitrate=12000 key-int-max=60 b-adapt=false bframes=0 ",
            "aud=true byte-stream=false option-string=repeat-headers=1:scenecut=0:open-gop=0 ! ",
            "h264parse config-interval=-1 disable-passthrough=true ! ",
            "video/x-h264,stream-format=avc ! ",
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
            "x264enc name=enc speed-preset=ultrafast tune=zerolatency ",
            "bitrate=3000 key-int-max=60 b-adapt=false bframes=0 ",
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

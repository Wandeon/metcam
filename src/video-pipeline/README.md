# Video Pipeline (v3)

This directory contains the in-process GStreamer pipeline implementation used by FootballVision Pro on Jetson Orin Nano devices.

## Key Modules

- `gstreamer_manager.py` – Singleton that owns the GLib main loop, manages pipeline lifecycle, and propagates bus events.
- `pipeline_builders.py` – Generates canonical recording and preview pipeline strings (NV12 → videocrop → I420 → x264).
- `recording_service.py` – Dual-camera recorder with 10 s protection, state persistence, and timestamped MP4 segments.
- `preview_service.py` – Dual-camera HLS preview (`/dev/shm/hls/cam{N}.m3u8`) with per-camera control and restart support.
- `camera_config_manager.py` – Loads and atomically persists `config/camera_config.json` values.
- `shaders/` – Reserved for future GPU-based distortion correction (not used by the v3 CPU crop pipeline).

## Current Pipelines

Both pipelines share the same deterministic crop and colorspace chain. The only differences are encoder bitrate/flags and the sink element.

### Recording

```
nvarguscamerasrc (3840×2160 @ 30 fps NV12) →
nvvidconv (NVMM → system memory) →
videocrop (left=480, right=480, top=272, bottom=272) →
videoconvert (NV12 → I420) →
x264enc (12 Mbps, key-int=60, zerolatency) →
h264parse (AVC stream-format) →
splitmuxsink (10-minute MP4 segments: cam{N}_{timestamp}_%02d.mp4)
```

### Preview

```
nvarguscamerasrc (3840×2160 @ 30 fps NV12) →
nvvidconv (NVMM → system memory) →
videocrop (same trims as recording) →
videoconvert (NV12 → I420) →
x264enc (3 Mbps, byte-stream=true) →
h264parse (config-interval=1) →
hlssink2 (/dev/shm/hls/cam{N}.m3u8, 2 s segments)
```

## Runtime Behaviour

- Pipelines are created and started via `GStreamerManager` to avoid subprocess overhead.
- Recording and preview cannot run simultaneously; the API stops preview automatically before recording starts.
- Recording segments are written to `/mnt/recordings/<match>/segments/` and roll every 600 s.
- Preview segments live in `/dev/shm/hls/` (tmpfs) and should be bind-mounted or symlinked to `/tmp/hls` for HTTP serving.

## Development Tips

- Use `GStreamerManager.list_pipelines()` from a Python shell to inspect active pipelines.
- `pipeline_builders.py` should remain the single source of truth for crop values and encoder parameters; update docs alongside any changes.
- When adding new configuration fields, extend `camera_config_manager.py` and expose them through the API/UI layers.

## Legacy Files

Legacy shell scripts and managers (`recording_manager_enhanced.py`, `record_dual_*`) remain in the repository for reference only. The v3 deployment no longer invokes them.

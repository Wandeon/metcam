# Video Pipeline (v3)

This directory contains the in-process GStreamer pipeline implementation used by FootballVision Pro on Jetson Orin Nano devices.

## Key Modules

- `gstreamer_manager.py` – Singleton that owns the GLib main loop, manages pipeline lifecycle, and propagates bus events.
- `pipeline_builders.py` – Generates canonical recording and preview pipeline strings (NV12 → videocrop → I420 → x264).
- `pipeline_manager.py` ⭐ – **System-level mutual exclusion** using file locks in `/var/lock/footballvision/`. Ensures recording and preview never run simultaneously.
- `recording_service.py` – Dual-camera recorder with 10 s protection, state persistence, and timestamped MP4 segments.
- `preview_service.py` – Dual-camera HLS preview (`/dev/shm/hls/cam{N}.m3u8`) with per-camera control and restart support.
- `camera_config_manager.py` – Loads and atomically persists `config/camera_config.json` values.

## Current Pipelines

Both pipelines share the same deterministic crop and colorspace chain. The only differences are encoder bitrate/flags and the sink element.

### Recording

```
nvarguscamerasrc (3840×2160 @ 30 fps NV12) →
nvvidconv (NVMM → system memory) →
videocrop (left=480, right=480, top=272, bottom=272) →
videoconvert (NV12 → I420) →
x264enc (12 Mbps, key-int=60, zerolatency) →
h264parse (AVC stream-format) →
splitmuxsink (10-minute MP4 segments: cam{N}_{timestamp}_%02d.mp4)
```

### Preview

```
nvarguscamerasrc (3840×2160 @ 30 fps NV12) →
nvvidconv (NVMM → system memory) →
videocrop (same trims as recording) →
videoconvert (NV12 → I420) →
x264enc (3 Mbps, byte-stream=true) →
h264parse (config-interval=1) →
hlssink2 (/dev/shm/hls/cam{N}.m3u8, 2 s segments)
```

## Runtime Behaviour

- Pipelines are created and started via `GStreamerManager` to avoid subprocess overhead.
- **Recording and preview are mutually exclusive** – Enforced by `pipeline_manager.py` using OS-level file locks:
  - Recording acquires lock with `force=True` (takes priority, stops preview if running)
  - Preview acquires lock with `force=False` (respects recording, fails if recording active)
  - Locks persist across crashes and are automatically cleaned up after 5 minutes of staleness
- Recording segments are written to `/mnt/recordings/<match>/segments/` and roll every 600 s.
- Preview segments live in `/dev/shm/hls/` (tmpfs) and are served via Caddy at `/hls/cam{N}.m3u8`.

## Development Tips

- Use `GStreamerManager.list_pipelines()` from a Python shell to inspect active pipelines.
- Check pipeline lock state: `curl http://localhost:8000/api/v1/pipeline-state`
- `pipeline_builders.py` should remain the single source of truth for crop values and encoder parameters; update docs alongside any changes.
- When adding new configuration fields, extend `camera_config_manager.py` and expose them through the API/UI layers.
- **Never** bypass `pipeline_manager` locks – they prevent CPU overload from running 4 pipelines simultaneously.

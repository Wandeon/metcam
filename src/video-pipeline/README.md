# Video Pipeline (v3)

This directory contains the in-process GStreamer pipeline implementation used by FootballVision Pro on Jetson Orin Nano devices.

## Key Modules

- `gstreamer_manager.py` – Singleton that owns the GLib main loop, manages pipeline lifecycle, and propagates bus events.
- `pipeline_builders.py` – Generates canonical recording and preview pipeline strings with VIC hardware-accelerated cropping.
- `pipeline_manager.py` ⭐ – **System-level mutual exclusion** using file locks in `/var/lock/footballvision/`. Ensures recording and preview never run simultaneously.
- `recording_service.py` – Dual-camera recorder with 10 s protection, state persistence, and timestamped MP4 segments.
- `preview_service.py` – Dual-camera HLS preview (`/dev/shm/hls/cam{N}.m3u8`) with per-camera control and restart support.
- `camera_config_manager.py` – Loads and atomically persists `config/camera_config.json` values.

## Current Pipelines (Hardware Accelerated)

Both pipelines use **VIC (Video Image Compositor)** hardware acceleration for zero-copy cropping in NVMM memory. This is critical for performance.

### Recording Pipeline

```
nvarguscamerasrc (3840×2160 @ 30 fps NV12, memory:NVMM) →
nvvidconv [VIC crop in NVMM] (left=480, right=3360, top=272, bottom=1888) →
  output: 2880×1616 NV12 in NVMM →
nvvidconv [VIC color conversion] (NVMM NV12 → CPU I420) →
x264enc (12 Mbps, key-int=60, zerolatency) →
h264parse (AVC stream-format) →
splitmuxsink (10-minute MP4 segments: cam{N}_{timestamp}_%02d.mp4)
```

### Preview Pipeline

```
nvarguscamerasrc (3840×2160 @ 30 fps NV12, memory:NVMM) →
nvvidconv [VIC crop in NVMM] (left=480, right=3360, top=272, bottom=1888) →
  output: 2880×1616 NV12 in NVMM →
nvvidconv [VIC color conversion] (NVMM NV12 → CPU I420) →
x264enc (3 Mbps, byte-stream=true) →
h264parse (config-interval=1) →
hlssink2 (/dev/shm/hls/cam{N}.m3u8, 2 s segments)
```

## ⚠️ CRITICAL: nvvidconv Crop Coordinate System

**This is the most common source of bugs.** The `nvvidconv` element uses a **bounding box coordinate system**, NOT pixel counts to remove.

### nvvidconv Properties

```
left   = X coordinate where cropped region STARTS (pixels from left edge)
right  = X coordinate where cropped region ENDS (pixels from left edge)
top    = Y coordinate where cropped region STARTS (pixels from top edge)
bottom = Y coordinate where cropped region ENDS (pixels from top edge)
```

### Config File Format (camera_config.json)

```json
{
  "cameras": {
    "0": {
      "crop": {
        "left": 480,    // pixels to REMOVE from left edge
        "right": 480,   // pixels to REMOVE from right edge
        "top": 272,     // pixels to REMOVE from top edge
        "bottom": 272   // pixels to REMOVE from bottom edge
      }
    }
  }
}
```

### Coordinate Conversion Formula

For a **3840×2160 sensor** with config `{left: 480, right: 480, top: 272, bottom: 272}`:

```python
# Config values (pixels to remove)
crop_left = 480
crop_right = 480
crop_top = 272
crop_bottom = 272

# Convert to nvvidconv bounding box coordinates
left_coord = crop_left                      # = 480
right_coord = SENSOR_WIDTH - crop_right     # = 3840 - 480 = 3360
top_coord = crop_top                        # = 272
bottom_coord = SENSOR_HEIGHT - crop_bottom  # = 2160 - 272 = 1888

# Result: nvvidconv left=480 right=3360 top=272 bottom=1888
# Output size: 2880×1616 (3840 - 480 - 480 = 2880, 2160 - 272 - 272 = 1616)
```

### Visual Representation

```
Sensor: 3840×2160
┌─────────────────────────────────────┐
│         crop_top = 272              │  ← Remove 272px from top
├─────────────────────────────────────┤
│ c │                             │ c │
│ r │                             │ r │  ← Cropped region
│ o │      Cropped Region         │ o │     (2880×1616)
│ p │      2880×1616              │ p │
│ _ │                             │ _ │
│ l │                             │ r │
│ e │                             │ i │
│ f │                             │ g │
│ t │                             │ h │
│ = │                             │ t │
│ 4 │                             │ = │
│ 8 │                             │ 4 │
│ 0 │                             │ 8 │
│   │                             │ 0 │
├─────────────────────────────────────┤
│       crop_bottom = 272             │  ← Remove 272px from bottom
└─────────────────────────────────────┘

nvvidconv coordinates:
  left=480    (start X)
  right=3360  (end X)
  top=272     (start Y)
  bottom=1888 (end Y)
```

## Common Mistakes ❌

### 1. Using "src-crop" property (DOES NOT EXIST)
```gst
❌ nvvidconv src-crop=480:272:2880:1616
   Error: no property "src-crop" in element "cropper"

✅ nvvidconv left=480 right=3360 top=272 bottom=1888
```

### 2. Passing crop pixel counts directly
```python
❌ nvvidconv left=480 right=480 top=272 bottom=272
   # This crops to a 208×544 region starting at (480, 272) - WRONG!

✅ nvvidconv left=480 right=3360 top=272 bottom=1888
   # Correct: 2880×1616 region from (480, 272) to (3360, 1888)
```

### 3. Using negative values
```gst
❌ nvvidconv left=-480 right=-480
   Error: Integer out of range
```

## Hardware Acceleration Benefits

Using `nvvidconv` for cropping provides significant performance benefits:

- **VIC Hardware**: 60-90% VIC utilization during dual-camera operation
- **Zero-Copy**: Crop happens in NVMM (GPU) memory, no CPU transfer
- **Low CPU**: ~60-70% CPU usage (vs 90%+ with software crop)
- **No GPU**: GR3D (3D engine) remains at 0%, saves power
- **Memory Efficiency**: No intermediate buffers on CPU

### Verification

Check VIC usage while preview is running:
```bash
sudo tegrastats --interval 1000

# Expected output:
VIC 82%@435   ← VIC hardware actively processing
GR3D_FREQ 0%  ← GPU 3D engine idle
CPU [65%@1344,67%@1344,...]  ← Moderate CPU usage
```

## Runtime Behaviour

- Pipelines are created and started via `GStreamerManager` to avoid subprocess overhead.
- **Recording and preview are mutually exclusive** – Enforced by `pipeline_manager.py` using OS-level file locks:
  - Recording acquires lock with `force=True` (takes priority, stops preview if running)
  - Preview acquires lock with `force=False` (respects recording, fails if recording active)
  - Locks persist across crashes and are automatically cleaned up after 5 minutes of staleness
- Recording segments are written to `/mnt/recordings/<match>/segments/` and roll every 600 s.
- Preview segments live in `/dev/shm/hls/` (tmpfs) and are served via Caddy at `/hls/cam{N}.m3u8`.

## Brightness and Exposure Control

### Problem: Flickering Brightness
Auto-exposure (AE) in `nvarguscamerasrc` can cause flickering when cameras independently adjust exposure. This is especially noticeable when cameras view slightly different scenes.

### Solution: Synchronized Exposure Settings

Both cameras use **identical exposure compensation values** to ensure consistent brightness:

```python
# In pipeline_builders.py
nvarguscamerasrc aelock=false aeantibanding=3 exposurecompensation=0.0
```

**Key Settings:**
- `aelock=false` – Auto-exposure enabled (adapts to lighting changes)
- `aeantibanding=3` – 60Hz anti-banding mode (reduces flicker from artificial lighting)
- `exposurecompensation=0.0` – Brightness bias applied to both cameras (-2.0 to +2.0)
  - `0.0` = neutral (no bias)
  - `+0.5` = slightly brighter
  - `-0.5` = slightly darker

### Configuration
Edit `config/camera_config.json` to adjust exposure compensation:

```json
{
  "cameras": {
    "0": {
      "exposure_compensation": 0.0
    },
    "1": {
      "exposure_compensation": 0.0
    }
  }
}
```

**IMPORTANT**: Both cameras should use the **same value** to maintain brightness consistency.

### Exposure Ranges
The pipeline sets conservative exposure limits to prevent over/under-exposure:

- **Exposure time**: 13 µs to 33 ms (13000 to 33000000 nanoseconds)
- **Analog gain**: 1x to 16x
- **Digital gain**: 1x to 4x

These ranges allow the camera to adapt to various lighting conditions (indoor/outdoor, day/night) while staying within reasonable noise levels.

### Why Not Manual Exposure?
Manual exposure (`aelock=true`) would eliminate flicker entirely, but:
- Requires frequent manual adjustments as lighting changes
- No adaptation to shadows, clouds, or time-of-day changes
- More maintenance burden for operators

Auto-exposure with synchronized compensation provides the best balance of stability and adaptability.

## Troubleshooting

### Preview won't start: "no property src-crop"
**Problem**: Old incorrect pipeline syntax
**Solution**: Update to latest `pipeline_builders.py` with bounding box coordinates

### Preview won't start: "VIC Configuration failed image scale factor exceeds 16"
**Problem**: Incorrect coordinate values causing extreme scaling
**Solution**: Verify coordinate conversion math, ensure right_coord > left_coord and bottom_coord > top_coord

### Crop appears incorrect in output
**Problem**: Coordinates interpreted as pixel counts instead of bounding box
**Solution**: Use conversion formula: `right_coord = SENSOR_WIDTH - crop_right`, not `right_coord = crop_right`

## Development Tips

- Use `GStreamerManager.list_pipelines()` from a Python shell to inspect active pipelines.
- Check pipeline lock state: `curl http://localhost:8001/api/v1/pipeline-state`
- Test crop coordinates manually:
  ```bash
  gst-launch-1.0 nvarguscamerasrc sensor-id=0 num-buffers=30 ! \
    'video/x-raw(memory:NVMM),width=3840,height=2160,format=NV12' ! \
    nvvidconv left=480 right=3360 top=272 bottom=1888 ! \
    'video/x-raw(memory:NVMM),format=NV12,width=2880,height=1616' ! \
    nvvidconv ! fakesink
  ```
- `pipeline_builders.py` should remain the single source of truth for crop values and encoder parameters.
- When adding new configuration fields, extend `camera_config_manager.py` and expose them through the API/UI layers.
- **Never** bypass `pipeline_manager` locks – they prevent CPU overload from running 4 pipelines simultaneously.

## References

- [NVIDIA nvvidconv Documentation](https://docs.nvidia.com/jetson/archives/r35.2.1/DeveloperGuide/text/SD/Multimedia/AcceleratedGstreamer.html)
- [DeepStream nvvideoconvert Plugin](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvvideoconvert.html)
- Check nvvidconv properties: `gst-inspect-1.0 nvvidconv`

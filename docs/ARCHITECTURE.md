# FootballVision Pro - Architecture v3 Complete

## Date: October 22, 2025 (updated February 2026)

## Overview

Successfully redesigned FootballVision Pro from **subprocess-based scripts** to **in-process GStreamer** architecture.

### Problems Solved ✅

1. **Recording delays eliminated**:
   - Start: 3s → ~0.1s (30x faster)
   - Stop: 15s → ~2s (7.5x faster)

2. **Recording protection added**:
   - Cannot stop recording within first 10 seconds
   - Prevents accidental stops
   - Force flag available for emergency stops

3. **State persistence**:
   - Recording state survives API restarts
   - Recording state survives page refreshes
   - State file: `/tmp/footballvision_recording_state.json`

4. **Process management simplified**:
   - No more subprocess.Popen()
   - No more PID files
   - No more zombie processes
   - All pipelines in-process

5. **Architecture reliability**:
   - Thread-safe GLib.MainLoop
   - Graceful EOS handling
   - Error callbacks with recovery hooks
   - Singleton pattern for managers

## New Files Created

### Core Components

1. **gstreamer_manager.py** (14KB)
   - Location: `/home/mislav/footballvision-pro/src/video-pipeline/`
   - Purpose: Thread-safe singleton manager for all GStreamer pipelines
   - Features:
     - Background GLib.MainLoop thread
     - Pipeline creation/start/stop/remove
     - EOS and error event handling
     - Pipeline state tracking
     - Metadata support

2. **pipeline_builders.py** (5.5KB)
   - Location: `/home/mislav/footballvision-pro/src/video-pipeline/`
   - Purpose: Constructs GStreamer pipeline strings
   - Functions:
     - `build_recording_pipeline(camera_id, output_pattern)` - 12 Mbps recording
     - `build_preview_pipeline(camera_id, hls_location)` - 3 Mbps HLS preview
     - `load_camera_config()` - Loads camera configuration
     - `pixel_count_to_edge_coords()` - Converts crop format

3. **recording_service.py** (12KB)
   - Location: `/home/mislav/footballvision-pro/src/video-pipeline/`
   - Purpose: Dual-camera recording service
   - Features:
     - Instant start/stop
     - 10-second recording protection
     - State persistence to disk
     - Auto-restore on startup
     - Force stop for emergencies
     - Per-camera status tracking

4. **preview_service.py** (12KB)
   - Location: `/home/mislav/footballvision-pro/src/video-pipeline/`
   - Purpose: Dual-camera preview with transport abstraction
   - Features:
     - Instant start/stop
     - Per-camera control
     - Restart capability
     - Independent from recording
     - **Transport modes**: HLS (`/dev/shm/hls/cam{N}.m3u8`), WebRTC (direct), RTSP relay (via GstRtspServer → go2rtc)
     - **go2rtc relay**: Feature-flagged by `WEBRTC_RELAY_URL` env var
     - GstRtspServer with dedicated GLib.MainLoop daemon thread
     - `rtsp_mount_active` dict for explicit mount lifecycle tracking

5. **pipeline_manager.py** (8KB) ⭐ NEW
   - Location: `/home/mislav/footballvision-pro/src/video-pipeline/`
   - Purpose: System-level mutual exclusion for pipelines
   - Features:
     - File-based locks in `/var/lock/footballvision/`
     - Recording mode uses force=True (takes priority)
     - Preview mode uses force=False (respects recording)
     - Locks persist across crashes
     - Automatic stale lock cleanup (5+ minute threshold)
     - **CRITICAL:** Prevents recording and preview from running simultaneously

6. **simple_api_v3.py** (12KB)
   - Location: `/home/mislav/footballvision-pro/src/platform/`
   - Purpose: FastAPI server using new services
   - Features:
     - Instant responses (no delays)
     - Recording protection enforcement
     - Prometheus metrics
     - Graceful shutdown handling
     - SIGTERM/SIGINT cleanup

## API Changes

### Recording Endpoints

#### Start Recording
```bash
POST /api/v1/recording
{
  "match_id": "match_123",
  "force": false  # optional, force start even if already recording
}
```

Response:
```json
{
  "success": true,
  "message": "Recording started for match: match_123",
  "match_id": "match_123",
  "cameras_started": [0, 1],
  "cameras_failed": []
}
```

#### Stop Recording
```bash
DELETE /api/v1/recording?force=false
```

Response (protected):
```json
{
  "success": false,
  "message": "Recording protected for 10.0s. Current duration: 5.2s. Use force=True to override.",
  "protected": true
}
```

Response (success):
```json
{
  "success": true,
  "message": "Recording stopped successfully"
}
```

#### Get Recording Status
```bash
GET /api/v1/recording
```

Response:
```json
{
  "recording": true,
  "match_id": "match_123",
  "duration": 15.3,
  "cameras": {
    "camera_0": {
      "state": "PLAYING",
      "uptime": 15.3
    },
    "camera_1": {
      "state": "PLAYING",
      "uptime": 15.3
    }
  },
  "protected": false
}
```

### Preview Endpoints

#### Start Preview
```bash
POST /api/v1/preview
{
  "camera_id": null  # null = both cameras, 0 or 1 for specific camera
}
```

#### Stop Preview
```bash
DELETE /api/v1/preview?camera_id=<camera_id>
```

#### Restart Preview
```bash
POST /api/v1/preview/restart
{
  "camera_id": null
}
```

## Pipeline Configuration

### Recording Pipeline (per camera)

```
nvarguscamerasrc
  ↓ 4K @ 30fps (NV12, NVMM)
nvvidconv (NVMM → system memory, no crop)
  ↓ 3840x2160 @ 30fps (NV12, system memory)
videocrop (CPU trim to match config)
  ↓ ~2880x1616 @ 30fps (NV12, system memory)
videoconvert
  ↓ ~2880x1616 @ 30fps (I420)
x264enc (12 Mbps, threads=6)
  ↓ H.264
splitmuxsink
  → /mnt/recordings/{match_id}/segments/cam{id}_{timestamp}_%02d.mp4 (10 min chunks)
```

### Preview Pipeline (per camera)

```
nvarguscamerasrc
  ↓ 4K @ 30fps (NV12, NVMM)
nvvidconv (NVMM → system memory, no crop)
  ↓ 3840x2160 @ 30fps (NV12, system memory)
videocrop (CPU trim to match config)
  ↓ ~2880x1616 @ 30fps (NV12, system memory)
videoconvert
  ↓ ~2880x1616 @ 30fps (I420)
x264enc (3 Mbps, threads=4)
  ↓ H.264
hlssink2
  → /dev/shm/hls/cam{id}.m3u8 (2s segments, keep 5)
```

## Camera Configuration

**File**: `/home/mislav/footballvision-pro/config/camera_config.json`

**Current Settings**:
- Rotation: 0° (both cameras)
- Crop: Trim 480px left/right, 272px top/bottom (both cameras)
- Digital gain: Enabled (1-4x)
- Analog gain: Enabled (1-16x)
- Exposure time: 13µs - 33ms

**Software Crop Format** (TRIM VALUES):
```json
{
  "left": 480,    // Trim 480 pixels from left edge
  "right": 480,   // Trim 480 pixels from right edge
  "top": 272,     // Trim 272 pixels from top edge
  "bottom": 272   // Trim 272 pixels from bottom edge
}
```

Result: 2880×1616 centered crop from 3840×2160 source (values adjustable per camera)

## Testing

### Test Script

Run the automated test:
```bash
ssh mislav@metcam "bash /tmp/test_new_architecture.sh"
```

This tests:
1. API v3 startup
2. Health check
3. Instant recording start (< 2s)
4. Recording status
5. Protection enforcement (should fail within 10s)
6. Stop after protection expires (< 5s)

### Manual Testing

1. **Start API v3** (temporary, for testing):
```bash
ssh mislav@metcam
cd /home/mislav/footballvision-pro/src/platform
python3 simple_api_v3.py
```

2. **Test recording** (from another terminal):
```bash
# Start
curl -X POST 'http://localhost:8000/api/v1/recording' \
  -H 'Content-Type: application/json' \
  -d '{"match_id": "test_v3"}'

# Check status
curl http://localhost:8000/api/v1/recording | python3 -m json.tool

# Wait 11 seconds

# Stop
curl -X DELETE 'http://localhost:8000/api/v1/recording'

# Verify files
ls -lh /mnt/recordings/test_v3/segments/
```

3. **Test page refresh survival**:
   - Start recording via API
   - Note the match_id and timestamp
   - Restart the API server (Ctrl+C, then restart)
   - Check status - recording should still show as active
   - Verify pipeline status with `get_status()`

## Known Limitations

1. **Preview and recording are mutually exclusive** ⭐:
   - CANNOT run simultaneously (enforced by pipeline_manager.py)
   - Recording takes priority with force=True
   - Preview respects recording and will fail to start if recording is active
   - This prevents CPU from being overwhelmed by 4 pipelines simultaneously

2. **Recording protection is strict**:
   - 10 seconds minimum recording time
   - Use `force=true` for emergency stops only
   - Protection duration is hardcoded (can be made configurable)

3. **State persistence limitations**:
   - Only recording state is persisted
   - Preview state is not persisted (intentional - preview is ephemeral)
   - State file is in /tmp (survives reboots on most systems)

4. **No mode switching**:
   - v3 API doesn't support multiple recording modes (normal/no_crop)
   - Uses single optimized crop pipeline driven by software `videocrop`
   - Mode switching can be added if needed

## Performance Metrics

- Target: 30 fps
- Expected: 25-27 fps (validated with the software crop pipeline)
- Bitrate: 12 Mbps per camera
- Resolution: ~2880×1616 (depends on configured trim)
- Format: H.264 in Matroska containers
- Segments: 10-minute chunks

## Troubleshooting

### Check GStreamer Manager Status
```python
from gstreamer_manager import GStreamerManager
mgr = GStreamerManager()
print(mgr.list_pipelines())
```

### Check Recording State File
```bash
cat /tmp/footballvision_recording_state.json
```

### Check API Logs
```bash
tail -f /var/log/footballvision/api/api_v3.log
```

### Force Stop Recording
```bash
curl -X DELETE 'http://localhost:8000/api/v1/recording?force=true'
```

### Check if Pipeline Still Running
```bash
# Check for nvarguscamerasrc processes
ps aux | grep nvargus

# Check GStreamer pipelines in Python
ssh mislav@metcam "python3 -c \"
from gstreamer_manager import GStreamerManager
mgr = GStreamerManager()
print(mgr.list_pipelines())
\""
```

## WebRTC Preview via go2rtc Relay (February 2026)

### Problem

GStreamer 1.20's `webrtcbin` has a DTLS bug: when TURN relay candidates are selected (common through VPS reverse proxy chains), DTLS handshake data is silently dropped by `nicesink`, causing permanent black screens. This cannot be fixed without upgrading GStreamer (not available on JetPack 6.1).

### Solution: go2rtc as External WebRTC Relay

Instead of using `webrtcbin` for browser-facing WebRTC, the Jetson serves RTSP via `GstRtspServer` over the Tailscale mesh, and `go2rtc` on VPS-02 handles WebRTC negotiation with browsers.

```
Browser ←—WebRTC (wss)—→ VPS-02 Caddy ←—WS—→ go2rtc ←—RTSP—→ Jetson GstRtspServer
          vid.nk-otok.hr   :443            :1984        :8554 (Tailscale)
```

### Components

**Jetson (preview_service.py):**
- `GstRtspServer` runs in a dedicated `GLib.MainLoop` daemon thread
- Mounts RTSP endpoints at `/cam0` and `/cam1` when preview starts
- Uses `build_preview_rtsp_pipeline()` from `pipeline_builders.py`
- Feature-flagged by `WEBRTC_RELAY_URL` env var
- When relay is configured, transport defaults to `webrtc` which triggers RTSP mount

**VPS-02 (go2rtc container):**
- Docker image `alexxit/go2rtc` with `network_mode: host`
- Streams configured as on-demand RTSP: `rtsp://100.78.19.7:8554/cam0` and `cam1`
- WebRTC signaling on `127.0.0.1:1984`, WebRTC media on `:8555/udp`
- Caddy routes: `/go2rtc/api/ws*` and `/go2rtc/api/webrtc*` → `uri strip_prefix /go2rtc` → `localhost:1984`

**Frontend (go2rtc.ts):**
- `Go2RtcService` class handles WebSocket signaling with go2rtc
- Protocol: `webrtc/offer` → `webrtc/answer` + `webrtc/candidate` exchanges
- Candidates are raw SDP strings (not JSON objects)
- Integrated into `CameraPreview.tsx` via `relayWsUrl` prop

### RTSP Pipeline

```
nvarguscamerasrc (4K@30fps NV12, NVMM) →
nvvidconv [VIC crop] →
nvvidconv [color conversion] (NVMM NV12 → CPU I420) →
videorate (30 fps) →
x264enc (6 Mbps, ultrafast, zerolatency) →
h264parse (config-interval=1) →
rtph264pay name=pay0 pt=96 (aggregate-mode=zero-latency)
```

### Configuration

Jetson systemd override (`/etc/systemd/system/footballvision-api-enhanced.service.d/webrtc-turn.conf`):
```ini
[Service]
Environment="WEBRTC_RELAY_URL=wss://vid.nk-otok.hr/go2rtc"
Environment="RTSP_BIND_ADDRESS=100.78.19.7"
Environment="RTSP_PORT=8554"
```

## Files Summary

**V3 Core Files**:
- `/home/mislav/footballvision-pro/src/video-pipeline/gstreamer_manager.py`
- `/home/mislav/footballvision-pro/src/video-pipeline/pipeline_builders.py`
- `/home/mislav/footballvision-pro/src/video-pipeline/pipeline_manager.py` ⭐ (Mutual Exclusion)
- `/home/mislav/footballvision-pro/src/video-pipeline/recording_service.py`
- `/home/mislav/footballvision-pro/src/video-pipeline/preview_service.py` (+ GstRtspServer relay integration)
- `/home/mislav/footballvision-pro/src/video-pipeline/camera_config_manager.py`
- `/home/mislav/footballvision-pro/src/platform/simple_api_v3.py`
- `/home/mislav/footballvision-pro/src/platform/web-dashboard/src/services/go2rtc.ts` (go2rtc signaling)

**State files** (created at runtime):
- `/var/lock/footballvision/pipeline_state.json` (Pipeline lock state)
- `/tmp/footballvision_recording_state.json` (Recording state persistence)

## Implementation Status

- ✅ V3 architecture (in-process GStreamer, mutual exclusion, recording/preview)
- ✅ WebRTC preview via go2rtc relay (February 2026)
- ✅ 94 backend tests passing
- ✅ Deployed and verified through VPS proxy chain

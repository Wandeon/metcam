# Video Pipeline

This directory mirrors the in-field configuration running on the Jetson Orin Nano rigs.

## Components
- `recording_manager.py` – Python wrapper around the production shell script. Handles lifecycle and manifest creation.
- `preview_service_optimized.py` – Optimised dual-camera HLS preview (720p @ 15 fps, tmpfs-backed segments).
- `scripts/record_dual_1080p30_optimized.sh` – Production dual-camera recorder invoked by the API.

## Architecture: Separated Preview & Recording

**IMPORTANT:** Preview and recording NEVER run simultaneously. This ensures maximum CPU efficiency and prevents resource contention.

### Recording Flow
1. API calls `RecordingManager.start_recording()`.
2. API automatically stops `PreviewService` if running.
3. The manager spawns `record_dual_1080p30_optimized.sh`, which starts two independent pipelines:
   - `nvarguscamerasrc → nvvidconv (rotate + VIC/GPU crop) → x264enc (15 Mbps) → splitmuxsink`
4. On stop, the manager signals the script, waits for segment finalisation, and writes an upload manifest.

**Output:** `/mnt/recordings/<match_id>/segments/cam{0,1}_*.mkv` (5-minute segments)

### Preview Flow
1. API calls `PreviewService.start()`.
2. Service launches two independent GStreamer pipelines:
   - `nvarguscamerasrc (sensor-mode=0) → nvvidconv (VIC/GPU crop) → nvvidconv (NV12→I420 + scale) → x264enc (2 Mbps, ultrafast) → hlssink2`
3. Segments are written to `/dev/shm/hls/cam{0,1}/` and synced to `/var/www/hls/cam{0,1}/playlist.m3u8`

**Output:** HLS segments in `/var/www/hls/cam{0,1}/` (2-second segments, 10 files max, backed by tmpfs)

**Note:** Preview refuses to start while recording is active (enforced by API layer).

## Requirements
- `gst-launch-1.0`, NVIDIA `nvarguscamerasrc`, and Jetson multimedia stack.
- `x264enc`, `h264parse`, `splitmuxsink`, `hlssink`/`hlssink2` plugins.
- Jetson power tools: `nvpmodel`, `jetson_clocks`.

The repository no longer ships the placeholder C++ GStreamer core; the shell + Python orchestration seen here is the source of truth.

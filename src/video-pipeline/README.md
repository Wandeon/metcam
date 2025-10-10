# Video Pipeline

This directory mirrors the in-field configuration running on the Jetson Orin Nano rigs.

## Components
- `recording_manager.py` – Python wrapper around the production shell script. Handles lifecycle, manifest creation, and merge trigger.
- `preview_service.py` – Independent dual-camera HLS preview service (1080p @ 30fps, 6 Mbps per camera).

The heavy lifting lives in `scripts/record_dual_1080p30.sh`, the same script invoked on the deployed device. Additional helpers (`record_test_simple.sh`, `record_dual_4k30_rotated.sh`, `merge_segments.sh`) are under `scripts/`.

## Architecture: Separated Preview & Recording

**IMPORTANT:** Preview and recording NEVER run simultaneously. This ensures maximum CPU efficiency and prevents resource contention.

### Recording Flow
1. API calls `RecordingManager.start_recording()`.
2. API automatically stops `PreviewService` if running.
3. The manager spawns `record_dual_1080p30.sh`, which starts two independent pipelines:
   - `nvarguscamerasrc → nvvidconv → x264enc (45 Mbps, 4 threads) → splitmuxsink`
4. On stop, the manager signals the script, waits for segment finalisation, and writes an upload manifest.

**Output:** `/mnt/recordings/<match_id>/segments/cam{0,1}_*.mp4` (5-minute segments)

### Preview Flow
1. API calls `PreviewService.start()`.
2. Service launches two independent GStreamer pipelines:
   - `nvarguscamerasrc (sensor-mode=1) → nvvidconv → videobalance → videorate → x264enc (6 Mbps, 2 threads) → hlssink2`
3. HLS streams available at `/var/www/hls/cam{0,1}/playlist.m3u8`

**Output:** HLS segments in `/var/www/hls/cam{0,1}/` (2-second segments, 10 files max)

**Note:** Preview refuses to start while recording is active (enforced by API layer).

## Requirements
- `gst-launch-1.0`, NVIDIA `nvarguscamerasrc`, and Jetson multimedia stack.
- `x264enc`, `h264parse`, `splitmuxsink`, `hlssink`/`hlssink2` plugins.
- Jetson power tools: `nvpmodel`, `jetson_clocks`.

The repository no longer ships the placeholder C++ GStreamer core; the shell + Python orchestration seen here is the source of truth.

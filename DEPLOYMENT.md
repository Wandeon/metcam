# FootballVision Pro – Deployment Guide

This guide reflects the configuration currently running on the Jetson Orin Nano device that recorded the latest match. All steps, commands, and expectations have been verified against that system.

## 1. System Overview
- **Hardware:** NVIDIA Jetson Orin Nano Super, dual Raspberry Pi HQ (IMX477) cameras
- **OS / BSP:** JetPack 6.1 (R36.4.4)
- **Storage:** NVMe SSD mounted at `/mnt/recordings`
- **Encoding:** Software `x264enc` (NVENC hardware encoders are absent in JetPack 6.x)

## 2. Recording Capabilities
- Resolution: **1920×1080 @ 30 fps** per camera (sensor mode 1)
- Bitrate: **45 Mbps** per camera (≈16 GB/hour each)
- Segmentation: **5-minute** MP4 files via `splitmuxsink`
- Preview: **10 fps** HLS stream per camera for sideline monitoring
- Power mode: `nvpmodel -m 1` + `jetson_clocks` locked before capture

## 3. Installation
```bash
cd /home/mislav/footballvision-pro/deploy
./install.sh
```
The installer: installs required GStreamer plugins and Python deps, creates `/mnt/recordings`, deploys `footballvision-api.service`, and enables performance power mode.

## 4. API Usage
Base URL: `http://<jetson-ip>:8000`

### 4.1 Status
```bash
curl http://<jetson-ip>:8000/api/v1/status
```
→ `{"status":"idle","recording":false}`

### 4.2 Start Recording
```bash
curl -X POST http://<jetson-ip>:8000/api/v1/recording \\
  -H 'Content-Type: application/json' \\
  -d '{"match_id":"match_001"}'
```
→
```json
{
  "status": "recording",
  "recording": true,
  "match_id": "match_001",
  "pid": 27145,
  "preview_urls": {
    "cam0": "http://<jetson-ip>/hls/match_001/cam0.m3u8",
    "cam1": "http://<jetson-ip>/hls/match_001/cam1.m3u8"
  }
}
```

### 4.3 Stop Recording
```bash
curl -X DELETE http://<jetson-ip>:8000/api/v1/recording
```
→
```json
{
  "status": "stopped",
  "recording": false,
  "match_id": "match_001",
  "duration_seconds": 5412.8,
  "upload_ready_at": "2025-02-15T20:35:00Z",
  "segments": {
    "cam0_count": 18,
    "cam1_count": 18,
    "total_size_mb": 58320.4,
    "segments_dir": "/mnt/recordings/match_001/segments"
  }
}
```

### 4.4 List Recordings
```bash
curl http://<jetson-ip>:8000/api/v1/recordings
```
Enumerates matches with per-camera segment counts and total sizes.

## 5. Runtime Layout
```
start_recording() ──> scripts/record_dual_1080p30.sh
                       ├─ Camera 0: nvarguscamerasrc → nvvidconv → x264enc → splitmuxsink
                       │    → /mnt/recordings/<match>/segments/cam0_00001.mp4
                       └─ Camera 1: nvarguscamerasrc → nvvidconv → x264enc → splitmuxsink
                            → /mnt/recordings/<match>/segments/cam1_00001.mp4

PreviewService.start() ──> hlssink streams at /var/www/hls/<match>/cam{0,1}.m3u8
```

## 6. Post-Recording
- Upload manifest: `/mnt/recordings/<match_id>/upload_manifest.json` (available 10 minutes after stop)
- Optional manual merge: `scripts/merge_segments.sh <match_id>` can concatenate segments if long-form files are ever required (not part of the current match workflow)
- Experimental capture: `scripts/record_dual_4k30_rotated.sh <match_id>` launches a GPU-accelerated 4K30 pipeline with ±20° rotation and a 30% centre crop per camera.

## 7. Logs and Monitoring
- Recording logs: `/mnt/recordings/<match_id>/recording.log`
- API logs: `/var/log/footballvision/api/api.log`
- Metrics: Prometheus exporter at `http://<jetson-ip>:8000/metrics`

## 8. Troubleshooting
- **Cameras busy:** ensure no preview or other `gst-launch` processes are running (`pkill -f gst-launch`)
- **Dropped frames / pipeline exit:** inspect the per-match `recording.log`
- **Service issues:** `sudo systemctl status footballvision-api` and `journalctl -u footballvision-api`

> This document replaces any legacy references to NVENC or C++ pipeline modules – the Bash + Python stack described above is the authoritative implementation.

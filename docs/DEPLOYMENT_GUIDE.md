# FootballVision Pro Deployment Guide

This guide covers the steps required to install and verify the current FootballVision Pro stack on a Jetson Orin Nano device. The deployment enables the web UI, native 4K recording pipeline, preview pipeline, and matches download workflow.

## 1. Prerequisites
- NVIDIA Jetson Orin Nano (8 GB) running JetPack 6.1 (R36.4.4)
- SSH access with sudo privileges
- Dual IMX477 cameras connected to ports `CSI 0` and `CSI 1`
- Stable power supply and 64 GB+ of free NVMe storage
- Optional: Internet access for remote uploads (SFTP)

## 2. Clone the Repository
```bash
cd /home/mislav
git clone https://github.com/your-org/footballvision-pro.git
cd footballvision-pro
```

## 3. Install Dependencies and Services
Run the bundled installer; it configures GStreamer, creates directories, and installs the `footballvision-api-enhanced` service.

```bash
cd deploy
./install.sh
```

What the script does:
- Installs required system packages (`gstreamer`, `python3-pip`, `ffmpeg`, etc.)
- Installs core Python dependencies (`fastapi`, `uvicorn`, `prometheus`, etc.)
- Creates `/mnt/recordings` with the correct permissions
- Installs the `footballvision-api-enhanced.service` systemd unit
- Configures CPU frequency governor to performance mode for stable encoding

## 4. Configure Runtime Directories
```bash
sudo mkdir -p /var/www/hls /var/lib/footballvision
sudo chown $USER:$USER /var/www/hls /var/lib/footballvision
```

## 5. Set Power Mode for Recording

The native 4K recording pipeline requires 25W power mode for optimal performance:

```bash
sudo nvpmodel -m 1  # Set to 25W mode
sudo nvpmodel -q    # Verify mode is set to 1
```

**Available Power Modes**:
- Mode 0: 15W (preview only, not suitable for recording)
- Mode 1: 25W (required for native 4K recording)

## 6. Start the Enhanced API
```bash
sudo systemctl start footballvision-api-enhanced
sudo systemctl enable footballvision-api-enhanced  # optional: run on boot
```

Verify the service:
```bash
sudo systemctl status footballvision-api-enhanced
curl http://localhost:8000/api/v1/status | python3 -m json.tool
```

Expected response:
```json
{
  "recording": {
    "recording": false,
    "match_id": null,
    "duration": 0.0,
    "cameras": {}
  },
  "preview": {
    "preview_active": false,
    "cameras": {
      "camera_0": {
        "active": false,
        "state": "stopped",
        "uptime": 0.0,
        "hls_url": "/hls/cam0.m3u8"
      },
      "camera_1": {
        "active": false,
        "state": "stopped",
        "uptime": 0.0,
        "hls_url": "/hls/cam1.m3u8"
      }
    }
  }
}
```

## 7. Validate Recording and Preview Pipelines

### Test Preview Stream

**Start preview** (2880×1616 @ 30 fps, 3 Mbps):
```bash
curl -X POST http://localhost:8000/api/v1/preview \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Confirm `.ts` segments appear under `/dev/shm/hls/` (tmpfs). If the API is serving `/hls/*`, ensure `/dev/shm/hls` is bind-mounted or symlinked to `/tmp/hls`.

**Stop preview**:
```bash
curl -X DELETE http://localhost:8000/api/v1/preview
```

### Test Native 4K Recording

**Start recording** (Native 4K: 2880×1616 @ 25 fps):
```bash
curl -X POST http://localhost:8000/api/v1/recording \
  -H 'Content-Type: application/json' \
  -d '{"match_id":"test_match"}'
```

**Expected Behavior**:
- Recording starts using the optimized in-process pipeline
- Resolution: 2880×1616 (56% FOV, trim-based crop from 4K sensor)
- Framerate: 25 fps (steady, no drops)
- Bitrate: 18 Mbps per camera
- CPU usage: ~88% (166% on cores 0-2, 162% on cores 3-5)
- Segment files created every 10 minutes (timestamped MP4s)

**Monitor recording** (optional):
```bash
# Check status
curl http://localhost:8000/api/v1/status | python3 -m json.tool

# Monitor CPU usage
top -p $(pgrep -d',' gst-launch)

# Check CPU frequency (should be 2.0 GHz)
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
```

**Stop recording** (wait at least 30 seconds for a valid test):
```bash
curl -X DELETE http://localhost:8000/api/v1/recording
```

**Verify output files**:
```bash
ls -lh /mnt/recordings/test_match/segments/
```

**Expected Output**:
- MP4 segments: `cam0_<timestamp>_00.mp4`, `cam1_<timestamp>_00.mp4`
- Segment size: ~1.1 GB every 10 minutes (~110 MB/minute per camera)
- Container: MP4 (H.264 video stream)

**Verify framerate and resolution** (replace `<timestamp>` with the generated value):
```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,avg_frame_rate,nb_frames \
  /mnt/recordings/test_match/segments/cam0_20250101_123000_00.mp4
```

Expected for a 30-second test segment:
- Width: 2880
- Height: 1616
- FPS: 25/1
- Frames: ~750

### Recording Modes

API v3 runs a single optimized crop pipeline. Mode-switching endpoints from earlier releases have been removed, and the `POST /api/v1/recording` endpoint ignores any legacy `mode` parameters. Adjustments to the field of view should be made through the camera configuration system instead.

### Performance Validation

After successful test recording, validate system performance:

```bash
# Verify power mode remained at 25W
sudo nvpmodel -q

# Check CPU frequency didn't throttle
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
# Should show: 2000000 (2.0 GHz)

# Check thermal state
cat /sys/class/thermal/thermal_zone*/temp
# Should be < 70000 (70°C during recording)

# Verify framerate from actual recording
ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=nb_read_frames,avg_frame_rate \
  /mnt/recordings/test_match/segments/cam0_20250101_123000_00.mp4
# Should show: 25/1 fps, ~750 frames for a 30s sample
# Replace the timestamp with the actual filename produced during your test
```

### Web UI Validation

**Access Dashboard**:
1. Open web browser to `http://<device-ip>:8000`
2. Navigate to **Dashboard** page
3. Verify recording controls are functional

**Check Matches**:
1. Navigate to **Matches** tab
2. Verify "test_match" appears with:
   - Both camera segments listed
   - Correct file sizes (~1.1 GB per 10-minute segment)
   - Download links functional

**Test Preview Mode**:
1. Navigate to **Preview** page
2. Click "Start Preview"
3. Verify dual camera streams load
4. Test fullscreen toggle (should not restart stream)
5. Stop preview

## 8. Optional: Configure SFTP Uploads

Set environment variables in `src/platform/api-server/.env`:
```
SFTP_HOST=example.com
SFTP_USERNAME=username
SFTP_PASSWORD=secret
SFTP_REMOTE_DIR=/recordings
```

Restart the service:
```bash
sudo systemctl restart footballvision-api-enhanced
```

Completed matches will upload automatically after the manifest delay.

## 9. Maintenance Commands

**Service Management**:
```bash
# Check logs
journalctl -u footballvision-api-enhanced -f

# Restart service
sudo systemctl restart footballvision-api-enhanced

# Stop service
sudo systemctl stop footballvision-api-enhanced

# Check service status
systemctl status footballvision-api-enhanced
```

**Cleanup**:
```bash
# Clear preview cache (tmpfs)
sudo rm -rf /dev/shm/hls/*
# If /hls is served from /tmp/hls, clear that mirror as well
sudo rm -rf /tmp/hls/*

# Remove specific match
sudo rm -rf /mnt/recordings/<match_id>

# Check storage usage
df -h /mnt/recordings
du -sh /mnt/recordings/*
```

**System Monitoring**:
```bash
# Monitor CPU temperature
watch -n 1 cat /sys/class/thermal/thermal_zone*/temp

# Monitor CPU frequency
watch -n 1 cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq

# Monitor disk I/O
iostat -x 1

# Monitor active recording processes
watch -n 1 'ps aux | grep gst-launch'
```

## 10. Troubleshooting

### Recording Won't Start

**Check power mode**:
```bash
sudo nvpmodel -q  # Should show mode 1 (25W)
```

**Check cameras detected**:
```bash
ls /dev/video*  # Should show video0 and video1
```

**Check storage space**:
```bash
df -h /mnt/recordings  # Need >50 GB free
```

**Check service logs**:
```bash
journalctl -u footballvision-api-enhanced -n 50
```

### Frame Drops During Recording

**Symptoms**: Actual fps < 25 fps

**Check CPU throttling**:
```bash
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
# Should be 2000000 (2.0 GHz), not lower
```

**Check temperature**:
```bash
cat /sys/class/thermal/thermal_zone*/temp
# Should be < 80000 (80°C)
```

**Check other processes**:
```bash
top  # Verify no other heavy processes running
```

### Green or Grey Screen in Recording

**Cause**: Pipeline configuration error (using nvvidconv crop instead of videocrop)

**Fix**: Verify recording script uses correct pipeline sequence:
```bash
cat /home/mislav/footballvision-pro/scripts/record_dual_native4k_55fov.sh | grep -A 5 videocrop
```

Should see: `nvvidconv → videorate → videocrop → videoconvert`

### UI Not Updating Recording State

**Check API response**:
```bash
curl http://localhost:8000/api/v1/status | python3 -m json.tool
```

Should show top-level `"status": "recording"` when active.

**Check browser console**: Press F12 → Console tab → look for API errors

## 11. Technical Documentation

For detailed technical information about the recording pipeline:

- **[Recording Pipeline Technical Reference](./docs/technical/RECORDING_PIPELINE.md)** - Complete pipeline architecture, GStreamer details, performance characteristics
- **[API Reference](./docs/technical/API_REFERENCE.md)** - REST API endpoints and usage
- **[Troubleshooting Guide](./docs/user/TROUBLESHOOTING.md)** - Common issues and solutions

## 12. Post-Deployment Checklist

- [ ] Both cameras detected (`ls /dev/video*`)
- [ ] Power mode set to 25W (`sudo nvpmodel -q`)
- [ ] API service running (`systemctl status footballvision-api-enhanced`)
- [ ] Test recording completes successfully
- [ ] Framerate verified at 25 fps
- [ ] Web UI accessible and functional
- [ ] Matches appear in dashboard
- [ ] Preview stream works without interruption
- [ ] Storage mounted at `/mnt/recordings`
- [ ] Sufficient free space (>50 GB)

The device is now ready for match-day operation with the native 4K recording pipeline.

---

**Document Version**: 2.0
**Last Updated**: October 17, 2025
**Pipeline**: Native 4K @ 25fps (2880×1616, 56% FOV)

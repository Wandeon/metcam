# FootballVision Pro - Deployment Guide

## System Overview

**Platform:** NVIDIA Jetson Orin Nano Super
**JetPack:** 6.1 (R36.4.4)
**Cameras:** Dual Raspberry Pi HQ Camera (IMX477 12MP sensors)
**Storage:** 238GB NVMe SSD (954 MB/s write speed)
**Recording:** Software H.265 encoding (no hardware encoding available in JetPack 6.x)

## Recording Capabilities

### Supported Configuration
- **Resolution:** 1920x1080 @ 30fps (both cameras)
- **Encoder:** x265enc (software)
- **Bitrate:** 4000 kbps per camera
- **Preset:** superfast
- **Output Format:** H.265/MP4
- **Throughput:** ~415 KB/s per camera (~24.5 MB/minute per camera)

### Limitations
- **No 4K support:** Hardware H.264/H.265 encoding unavailable in JetPack 6.x
- **Software encoding only:** CPU-based encoding limits resolution to 1080p
- **Dual camera maximum:** System can handle 2x 1080p@30fps streams simultaneously
- **Fixed framerate:** 30fps recommended for stability

## Installation

### Prerequisites
```bash
# Ensure cameras are detected
v4l2-ctl --list-devices
# Should show /dev/video0 and /dev/video1

# Verify IMX477 device tree loaded
cat /boot/extlinux/extlinux.conf | grep imx477
```

### Install FootballVision Pro
```bash
cd /home/mislav/footballvision-pro/deploy
./install.sh
```

This will:
1. Install system dependencies (GStreamer, Python packages)
2. Install Python dependencies (FastAPI, uvicorn)
3. Create recordings directory (`/mnt/recordings`)
4. Install systemd service
5. Set CPU governor to performance mode

### Start the Service
```bash
# Start service
sudo systemctl start footballvision-api

# Enable auto-start on boot
sudo systemctl enable footballvision-api

# Check status
sudo systemctl status footballvision-api

# View logs
sudo journalctl -u footballvision-api -f
```

## API Usage

### Base URL
```
http://localhost:8000
```

### Interactive Documentation
```
http://localhost:8000/docs
```

### API Endpoints

#### 1. Get Status
```bash
curl http://localhost:8000/api/v1/status
```

Response:
```json
{
  "status": "idle"
}
```

#### 2. Start Recording
```bash
curl -X POST http://localhost:8000/api/v1/recording \
  -H "Content-Type: application/json" \
  -d '{
    "match_id": "match_001",
    "resolution": "1920x1080",
    "fps": 30,
    "bitrate": 4000
  }'
```

Response:
```json
{
  "status": "recording",
  "match_id": "match_001",
  "cam0_pid": 12345,
  "cam1_pid": 12346,
  "start_time": "2025-10-02T00:00:00"
}
```

#### 3. Stop Recording
```bash
curl -X DELETE http://localhost:8000/api/v1/recording
```

Response:
```json
{
  "status": "stopped",
  "match_id": "match_001",
  "duration_seconds": 1800,
  "files": {
    "cam0": "/mnt/recordings/match_001_cam0.mp4",
    "cam1": "/mnt/recordings/match_001_cam1.mp4",
    "cam0_size_mb": 44.1,
    "cam1_size_mb": 44.3
  }
}
```

#### 4. List Recordings
```bash
curl http://localhost:8000/api/v1/recordings
```

Response:
```json
{
  "recordings": {
    "match_001": [
      {"file": "match_001_cam0.mp4", "size_mb": 44.1},
      {"file": "match_001_cam1.mp4", "size_mb": 44.3}
    ]
  }
}
```

## System Architecture

```
┌─────────────────────────────────────────────┐
│         FastAPI Server (Port 8000)          │
│              simple_api.py                  │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│         Recording Manager                   │
│       recording_manager.py                  │
└─────────────┬───────────────────────────────┘
              │
              ├──────────────┬─────────────────┐
              ▼              ▼                 ▼
         GStreamer      GStreamer         File System
         Pipeline 0     Pipeline 1        /mnt/recordings
              │              │
              ▼              ▼
         Camera 0       Camera 1
       (sensor-id=0)  (sensor-id=1)
       /dev/video0    /dev/video1
```

## GStreamer Pipeline

Each camera uses the following pipeline:

```
nvarguscamerasrc sensor-id=N
  ! video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1
  ! nvvidconv
  ! video/x-raw,format=I420
  ! x265enc bitrate=4000 speed-preset=superfast tune=zerolatency
  ! h265parse
  ! mp4mux
  ! filesink location=/mnt/recordings/MATCH_ID_camN.mp4
```

### Pipeline Components
- **nvarguscamerasrc:** Argus camera capture (NVMM buffers)
- **nvvidconv:** Format conversion (NVMM → I420)
- **x265enc:** Software H.265 encoder
- **h265parse:** Parse H.265 stream
- **mp4mux:** Multiplex into MP4 container
- **filesink:** Write to NVMe storage

## Performance Metrics

### Recording Performance (1080p@30fps dual camera)
- **Video bitrate:** ~4 Mbps per camera
- **File throughput:** ~415 KB/s per camera
- **Storage usage:** ~24.5 MB/minute per camera (~49 MB/min total)
- **CPU load:** ~6-7 average (6 cores)
- **Temperature:** ~50°C sustained

### Storage Capacity
With 238GB NVMe:
- **1 hour recording:** ~2.9 GB (both cameras)
- **Maximum duration:** ~80 hours of dual camera recording

## Troubleshooting

### Camera Not Detected
```bash
# Check device tree
cat /boot/extlinux/extlinux.conf | grep imx477

# Should show:
# FDT /boot/dtb/kernel_tegra234-p3768-0000+p3767-0005-nv-super-imx477-v2.dtb

# List cameras
ls -l /dev/video*
```

### Recording Fails to Start
```bash
# Check GStreamer elements
gst-inspect-1.0 nvarguscamerasrc
gst-inspect-1.0 x265enc

# Test camera 0 manually
gst-launch-1.0 nvarguscamerasrc sensor-id=0 num-buffers=100 ! fakesink

# Check CPU governor
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
# Should be: performance
```

### Poor Video Quality
```bash
# Increase bitrate (default 4000 kbps)
curl -X POST http://localhost:8000/api/v1/recording \
  -H "Content-Type: application/json" \
  -d '{"match_id": "test", "bitrate": 6000}'

# Note: Higher bitrate increases CPU load
# Monitor with: htop
```

### Service Won't Start
```bash
# Check service status
sudo systemctl status footballvision-api

# View detailed logs
sudo journalctl -u footballvision-api -n 50 --no-pager

# Check Python dependencies
python3 -c "import fastapi, uvicorn; print('OK')"
```

## Hardware Encoding Note

**IMPORTANT:** JetPack 6.x removed all hardware video encoding support. The NVENC hardware encoder is not available:
- No `/dev/nvhost-nvenc*` devices
- No `nvv4l2h264enc` or `nvv4l2h265enc` GStreamer elements
- Jetson Multimedia API encoder creation fails

This is a known limitation of JetPack 6.x. The system is configured to use software encoding (x265enc) as the only available option.

For hardware encoding, downgrade to JetPack 5.x is required, but this would require reflashing the device.

## System Configuration

### CPU Governor
The system sets CPU governor to "performance" for stable encoding:
```bash
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
```

This is automatically configured by the systemd service.

### Boot Configuration
Camera device tree loaded via `/boot/extlinux/extlinux.conf`:
```
FDT /boot/dtb/kernel_tegra234-p3768-0000+p3767-0005-nv-super-imx477-v2.dtb
```

## File Structure
```
footballvision-pro/
├── src/
│   ├── video-pipeline/
│   │   ├── recording_manager.py    # Core recording logic
│   │   └── main/
│   │       └── recorder_main.cpp    # C++ pipeline (not used)
│   └── platform/
│       └── simple_api.py           # FastAPI server
├── deploy/
│   ├── footballvision-api.service  # systemd service
│   └── install.sh                  # installation script
└── DEPLOYMENT.md                   # this file
```

## Contact & Support

For issues related to:
- **Hardware encoding:** Not available in JetPack 6.x (known limitation)
- **Camera detection:** Verify device tree configuration
- **Performance:** Monitor CPU usage and temperature
- **API usage:** See `/docs` endpoint for interactive documentation

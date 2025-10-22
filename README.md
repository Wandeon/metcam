# FootballVision Pro

Professional dual-camera recording system for football matches on NVIDIA Jetson Orin Nano.

## System Overview

**Hardware:**
- NVIDIA Jetson Orin Nano (8GB)
- 2x IMX477 CSI cameras (4K@30fps)
- JetPack 6.x (R36.4.4)

**Features:**
- Dual-camera synchronized recording
- VIC GPU hardware crop (2880x1620 output)
- In-process GStreamer pipelines
- 10-second recording protection
- State persistence across restarts
- HLS preview streaming
- Recording management (list, download, delete)
- FastAPI REST interface
- React-based web UI

## Quick Start

### Start Recording
```bash
curl -X POST 'http://localhost:8000/api/v1/recording' \
  -H 'Content-Type: application/json' \
  -d '{"match_id": "match_2025_01_15"}'
```

### Stop Recording
```bash
curl -X DELETE 'http://localhost:8000/api/v1/recording'
```

### Check Status
```bash
curl http://localhost:8000/api/v1/status | python3 -m json.tool
```

## Architecture

### Recording Pipeline (Per Camera)
```
nvarguscamerasrc (4K@30fps)
  ↓
nvvidconv (VIC GPU crop → 2880x1620)
  ↓
nvvidconv (format conversion)
  ↓
videoconvert (NV12 → I420)
  ↓
x264enc (12 Mbps, 6 threads)
  ↓
splitmuxsink (10-minute segments)
  → /mnt/recordings/{match_id}/segments/
```

### Core Components
- **gstreamer_manager.py** - Thread-safe pipeline manager
- **pipeline_builders.py** - Pipeline string construction
- **recording_service.py** - Dual-camera recording with protection
- **preview_service.py** - HLS preview streaming
- **simple_api_v3.py** - FastAPI REST server

### Performance
- Recording start: ~100ms
- Recording stop: ~2s (graceful EOS)
- CPU usage: ~40% (encoding)
- Frame rate: 25-30 fps sustained

## Documentation

- [Architecture Details](docs/ARCHITECTURE.md)
- [API Reference](docs/technical/API_REFERENCE.md)
- [Camera Configuration](docs/CAMERA_CONFIGURATION.md)
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [Quick Start Guide](docs/user/QUICK_START_GUIDE.md)

## API Endpoints

### Recording
- `POST /api/v1/recording` - Start recording
- `DELETE /api/v1/recording` - Stop recording
- `GET /api/v1/recording` - Get recording status

### Preview
- `POST /api/v1/preview` - Start HLS preview
- `DELETE /api/v1/preview` - Stop preview
- `POST /api/v1/preview/restart` - Restart preview

### Recordings Management
- `GET /api/v1/recordings` - List all recordings
- `GET /api/v1/recordings/{id}/segments` - Get match segments
- `DELETE /api/v1/recordings/{id}` - Delete recording
- `GET /api/v1/recordings/{id}/download` - Download as zip

### Camera Configuration
- `GET /api/v1/camera/config` - Get all camera configs
- `POST /api/v1/camera/config/{id}` - Update camera config
- `POST /api/v1/camera/apply` - Apply config changes

## System Requirements

- NVIDIA Jetson Orin Nano (or better)
- JetPack 6.x
- Python 3.10+
- GStreamer 1.20+
- 64GB+ storage for recordings

## Installation

See [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) for detailed setup instructions.

## License

Proprietary - All rights reserved.

# FootballVision Pro Documentation

**System Version**: 3.0 (In-Process GStreamer Pipeline)
**Last Updated**: October 22, 2025

---

## Quick Links

### 👥 User Documentation

**[Quick Start Guide](./user/QUICK_START_GUIDE.md)**
- **Location**: `docs/user/QUICK_START_GUIDE.md`
- **Purpose**: End-user guide for match-day operation
- **Contents**: Basic setup, recording workflow, downloading videos
- **Audience**: Operators, coaches, non-technical users

**Troubleshooting**
- Refer to the [Deployment Guide – Troubleshooting](./DEPLOYMENT_GUIDE.md#10-troubleshooting) section for common issues and recovery steps.

### 🔧 Technical Documentation

**[GStreamer Pipeline Reference](./technical/GSTREAMER_PIPELINES.md)**
- **Location**: `docs/technical/GSTREAMER_PIPELINES.md`
- **Purpose**: Source of truth for recording and preview pipeline configuration
- **Contents**:
  - Current per-camera pipeline listings (recording + preview)
  - Crop math for 2880×1616 output and default trims
  - Performance characteristics and resource usage
  - Troubleshooting tips (caps negotiation, chroma integrity)
  - Historical notes on deprecated GPU/VIC cropping
- **Audience**: Developers, DevOps, technical support

**[API Reference](./technical/API_REFERENCE.md) (v3)**
- **Location**: `docs/technical/API_REFERENCE.md`
- **Purpose**: Complete REST API documentation
- **Contents**:
  - Recording & preview endpoints (start/stop/status/restart)
  - Health/status telemetry responses
  - Recordings management (list, segments, delete, download)
  - Error format and protection behaviour (10 s recording lock)
  - Example `curl` calls for common workflows
- **Audience**: Developers, integration engineers

**[Deployment Guide](./DEPLOYMENT_GUIDE.md)**
- **Location**: `docs/DEPLOYMENT_GUIDE.md`
- **Purpose**: Installation, configuration, and validation procedures
- **Contents**:
  - Prerequisites and dependencies
  - Step-by-step installation
  - Power mode configuration (25W requirement)
  - Recording and preview validation
  - Performance verification steps
  - Troubleshooting deployment issues
- **Audience**: DevOps, system administrators

**[Camera Configuration Guide](./CAMERA_CONFIGURATION.md)** ⭐ NEW (v1.1)
- **Location**: `docs/CAMERA_CONFIGURATION.md`
- **Size**: 1500+ lines of comprehensive documentation
- **Purpose**: Complete reference for interactive camera configuration system
- **Contents**:
  - All 4 distortion correction types (Barrel, Cylindrical, Equirectangular, Perspective)
  - Detailed parameter explanations with ranges and examples
  - Preset system usage and workflows
  - API endpoint documentation
  - Troubleshooting guide
  - Advanced topics (calibration, custom corrections, batch configuration)
  - Workflow examples for common scenarios
- **Audience**: Camera operators, developers, system administrators

**[Camera Controls Quick Reference](./CAMERA_CONTROLS_QUICK_GUIDE.md)** ⭐ NEW (v1.1)
- **Location**: `docs/CAMERA_CONTROLS_QUICK_GUIDE.md`
- **Purpose**: Fast, practical reference for daily camera adjustments
- **Contents**:
  - 5-minute quick start guide
  - Common adjustments (fix tilt, adjust coverage, fix distortion)
  - Parameter cheat sheet with ranges
  - Correction types at a glance
  - Workflow tips for match day and testing
  - Troubleshooting table
  - Current production settings backup
- **Audience**: Camera operators, match day staff, regular users

---

## System Overview

FootballVision Pro is a dual-camera recording system designed for capturing high-quality sports footage using NVIDIA Jetson hardware.

### Key Features

**Native 4K Recording Pipeline** ✨
- **Resolution**: 2880×1616 @ 25 fps (4.66 megapixels per frame)
- **FOV**: 56% center crop from 4K sensor (no downscaling)
- **Quality**: 18 Mbps H.264 encoding with native 4K sharpness
- **Reliability**: Rock-solid 25.0 fps with ±0.1 fps variance
- **Performance**: 88% CPU usage with 11% headroom for stability

**Dual Camera System**
- Simultaneous recording from 2× IMX477 cameras (12.3 MP sensors)
- Independent CPU core allocation (cores 0-2 for cam0, cores 3-5 for cam1)
- Segmented recording (10-minute MP4 files with timestamped filenames)

**Web Dashboard**
- Live preview streaming (same crop as recording, HLS)
- Recording control and monitoring
- Match downloads and management
- Real-time system status

**Interactive Camera Configuration** ✨ NEW (v1.1)
- Real-time adjustment of rotation, crop, and distortion correction
- 4 correction algorithms: Barrel, Cylindrical, Equirectangular, Perspective
- Preset save/load system for quick configuration switching
- Per-camera independent controls
- Live preview updates with Apply button
- RESTful API for automation
- Persistent configuration storage

---

## Documentation Structure

### For Users

**Getting Started**:
1. Read [Quick Start Guide](./user/QUICK_START_GUIDE.md) for basic setup
2. Follow [Deployment Guide](./DEPLOYMENT_GUIDE.md) for installation
3. Use the Troubleshooting section in the [Deployment Guide](./DEPLOYMENT_GUIDE.md#10-troubleshooting) if issues arise

**Daily Operation**:
- Start recording via web dashboard
- Monitor system status during matches
- Download recordings after completion

### For Developers

**System Architecture**:
1. **[GStreamer Pipeline Reference](./technical/GSTREAMER_PIPELINES.md)** - Current recording/preview pipeline details, caps, and troubleshooting
2. **[API Reference](./technical/API_REFERENCE.md)** - REST endpoints, request/response formats, and integration examples
3. **[Deployment Guide](./DEPLOYMENT_GUIDE.md)** - Installation procedures and system configuration

**Key Components**:
- **API Service**: `/home/mislav/footballvision-pro/src/platform/simple_api_v3.py`
- **Recording Pipeline**: `/home/mislav/footballvision-pro/src/video-pipeline/recording_service.py` and `pipeline_builders.py`
- **Preview Service**: `/home/mislav/footballvision-pro/src/video-pipeline/preview_service.py`
- **Web Dashboard**: `/home/mislav/footballvision-pro/src/platform/web-dashboard/`

---

## Recording Pipeline Defaults

- Resolution: 2880×1616 (software `videocrop` trims 480/480/272/272)
- Framerate: 25 fps (IDR every 60 frames)
- Bitrate: 18 Mbps per camera (x264, ultrafast/zerolatency)
- Segments: 10-minute MP4 files (`cam{N}_{timestamp}_%02d.mp4`)
- Protection: Stops within the first 10 seconds require `force=true`

### Preview Characteristics

- Resolution: 2880×1616 (matches recording crop)
- Framerate: 30 fps (IDR every 60 frames)
- Bitrate: 3 Mbps per camera
- Segments: 2‑second TS files in `/dev/shm/hls`, exposed at `/hls/cam{N}.m3u8`

---

## Technical Specifications

### Hardware Requirements

- **Platform**: NVIDIA Jetson Orin Nano (8 GB)
- **Cameras**: 2× IMX477 (12.3 MP) on CSI ports 0 and 1
- **Storage**: 64 GB+ NVMe SSD (128 GB+ recommended)
- **Power**: 25W mode required for recording
- **Cooling**: Active cooling recommended

### Software Stack

- **OS**: JetPack 6.1 (Ubuntu 22.04, L4T R36.4.4)
- **Pipeline**: GStreamer 1.20+ with NVIDIA plugins
- **API**: FastAPI (Python 3.10+)
- **Frontend**: React + TypeScript (Vite)
- **Encoding**: x264 (software H.264)

### Performance Metrics

**Recording**:
- CPU Usage: 88% (166% on cores 0-2, 162% on cores 3-5)
- Framerate: 25.0 ± 0.1 fps sustained
- Storage Rate: 270 MB/min (both cameras)
- Power Consumption: 25W mode

**Thermal**:
- Idle: 35-40°C
- Recording (low light): 50-55°C
- Recording (daylight): 45-50°C
- Safe operating range: 0-70°C

---

## Lighting Behavior

**Important**: The native 4K pipeline performs **equally well or better in daylight** compared to low-light conditions.

### Why Daylight Performance is Better

**Low Light** (worst case):
- Higher ISO gain (up to 10×)
- Longer exposure times (up to 33ms)
- Increased sensor noise
- More intensive ISP processing

**Daylight** (optimal):
- Lower ISO gain (1-2×)
- Faster exposure times (13µs - 1ms)
- Minimal sensor noise
- Easier ISP processing
- Lower power consumption

**CPU-intensive pipeline stages** (videocrop, x264enc) are **invariant to lighting**, so if the system maintains 25 fps in dark conditions (tested), it will maintain 25 fps in daylight (guaranteed).

---

## Storage Requirements

### Per Match (90 minutes, both cameras)

- **Total Size**: ~24.3 GB
- **Per Camera**: ~12.2 GB
- **Per Minute**: ~270 MB
- **Per Segment (10 min)**: ~1.35 GB per camera

### Storage Device Recommendations

| Capacity | Matches | Use Case |
|----------|---------|----------|
| 128 GB | ~5 | Basic |
| 256 GB | ~10 | Recommended |
| 512 GB | ~20 | Professional |
| 1 TB | ~40 | Archive |

---

## System Status

### Check Recording Status

```bash
curl http://localhost/api/v1/status | python3 -m json.tool
```

### Verify Power Mode

```bash
sudo nvpmodel -q  # Should show mode 1 (25W)
```

### Monitor CPU and Temperature

```bash
# CPU frequency (should be 2000000 = 2.0 GHz)
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq

# Temperature (should be < 70000 = 70°C)
cat /sys/class/thermal/thermal_zone*/temp

# CPU usage
top
```

---

## Common Tasks

### Start Recording

Via API:
```bash
curl -X POST http://localhost/api/v1/recording \
  -H 'Content-Type: application/json' \
  -d '{"match_id":"match_001"}'
```

Via UI:
1. Open web dashboard
2. Click "Start Recording"
3. Enter match ID
4. Confirm

### Stop Recording

```bash
curl -X DELETE http://localhost/api/v1/recording
```

### Start Preview

```bash
curl -X POST http://localhost/api/v1/preview \
  -H 'Content-Type: application/json' \
  -d '{}'
```

### Check Framerate in Recording

```bash
ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=nb_read_frames,avg_frame_rate \
  /mnt/recordings/match_001/segments/cam0_20250115_123456_00.mp4
```

---

## Version History

### Version 3.0 (October 22, 2025) – In-Process Architecture Refresh

- Migrated from shell-based scripts to in-process GStreamer services (`recording_service.py`, `preview_service.py`, `simple_api_v3.py`)
- Added 10-second recording protection, state persistence, and instant start/stop semantics
- Unified recording and preview pipelines with CPU-based `videocrop` for 2880×1616 output
- Switched recording segments to timestamped MP4 files (10-minute rolls)
- Removed API mode switching; camera configuration now controls FOV adjustments

### Version 2.1 (October 20, 2025) - Camera Configuration System

**Interactive Camera Controls** ✨:
- Added web-based camera configuration UI in Preview tab
- Real-time adjustment of rotation (-180° to +180°, 0.1° precision)
- Per-side crop controls (left, right, top, bottom)
- 4 distortion correction algorithms with live parameters

**Correction Types**:
- Barrel (radial distortion): k1, k2 coefficients
- Cylindrical projection: radius, axis (horizontal/vertical)
- Equirectangular (spherical): FOV H/V, center point
- Perspective transform: 4-corner keystone correction

**Preset System**:
- Save current configuration as named presets
- Quick load/delete preset functionality
- Protected "default" preset
- Persistent storage in camera_config.json

**Backend Architecture**:
- Thread-safe configuration manager with RLock
- RESTful API endpoints (8 new endpoints)
- Dynamic GLSL shader generation
- Fixed threading deadlock issue

**Documentation**:
- Comprehensive Camera Configuration Guide (1500+ lines)
- Quick Reference Guide for daily operations
- API documentation for all camera config endpoints
- Troubleshooting and workflow examples

### Version 2.0 (October 17, 2025)

**Native 4K Pipeline**:
- Implemented native 4K recording at 2880×1616 @ 25fps
- 56% FOV coverage with center crop
- No downscaling for maximum sharpness
- 25.0 fps sustained performance validated over 15+ minute recordings

**Pipeline Improvements**:
- Fixed chroma corruption by using videocrop instead of nvvidconv crop
- Added videorate for stable 25 fps conversion
- Optimized CPU core allocation with taskset
- Validated thermal and power performance

**UI Enhancements**:
- Fixed fullscreen toggle not interrupting preview stream
- Added calibration preview mode (1920×1080 @ 30fps) *(legacy feature, removed in v3)*
- Added calibration preview mode (1920×1080 @ 30fps)
- Updated recording state management for real-time updates

**Documentation**:
- Created comprehensive Recording Pipeline Technical Reference
- Updated API Reference with mode management (legacy, superseded by v3)
- Enhanced Deployment Guide with validation procedures
- Updated Troubleshooting Guide with pipeline-specific issues

### Version 1.0 (September 30, 2025)

- Initial documentation system
- Basic recording and preview functionality
- Web dashboard with matches tab

---

## Support and Contributing

**Internal Documentation**: This documentation is maintained for the FootballVision Pro development team.

**System Logs**:
```bash
journalctl -u footballvision-api-enhanced -f        # API service logs
journalctl -u footballvision-api-enhanced -n 100    # Last 100 lines
```
> Ensure the systemd unit points to `simple_api_v3.py` before relying on these commands.

---

## Documentation File Structure

```
footballvision-pro/
└── docs/
    ├── README.md                     # Documentation index (this file)
    ├── ARCHITECTURE.md               # In-process architecture overview
    ├── DEPLOYMENT_GUIDE.md           # Installation, validation & troubleshooting
    ├── CAMERA_CONFIGURATION.md       # Camera configuration reference
    ├── CAMERA_CONTROLS_QUICK_GUIDE.md# Operator quick reference
    ├── technical/
    │   ├── API_REFERENCE.md          # REST API reference (v3)
    │   └── GSTREAMER_PIPELINES.md    # Recording/preview pipeline details
    └── user/
        └── QUICK_START_GUIDE.md      # End-user workflow summary
```

## Key Source Code Locations

```
footballvision-pro/
├── config/
│   └── camera_config.json                # Persisted crop/rotation/distortion settings
│
├── src/
│   ├── platform/
│   │   ├── simple_api_v3.py             # FastAPI service (recording + preview control)
│   │   └── web-dashboard/               # React frontend
│   │       └── src/
│   │           ├── services/api.ts      # REST client (v3 endpoints)
│   │           └── components/          # UI components (Camera controls, Dashboard)
│   └── video-pipeline/
│       ├── gstreamer_manager.py         # GLib main loop + pipeline lifecycle
│       ├── pipeline_builders.py         # Canonical recording/preview pipeline strings
│       ├── recording_service.py         # Dual-camera recording orchestration
│       ├── preview_service.py           # Dual-camera HLS preview orchestration
│       └── camera_config_manager.py     # Thread-safe config loading/writing
│
└── docs/                                # Documentation bundle
```

Legacy shell scripts remain in `scripts/` for historical reference; v3 no longer depends on them.

---

**Documentation Version**: 3.0
**System Version**: In-Process GStreamer Pipeline @ 25 fps (2880×1616, 56% FOV)
**Last Updated**: October 22, 2025

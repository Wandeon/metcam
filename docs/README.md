# FootballVision Pro Documentation

**System Version**: 2.0 (Native 4K Pipeline)
**Last Updated**: October 17, 2025

---

## Quick Links

### 👥 User Documentation

**[Quick Start Guide](./user/QUICK_START_GUIDE.md)**
- **Location**: `docs/user/QUICK_START_GUIDE.md`
- **Purpose**: End-user guide for match-day operation
- **Contents**: Basic setup, recording workflow, downloading videos
- **Audience**: Operators, coaches, non-technical users

**[Troubleshooting Guide](./user/TROUBLESHOOTING.md)**
- **Location**: `docs/user/TROUBLESHOOTING.md`
- **Purpose**: Common issues and solutions
- **Contents**: System diagnostics, frame drops, video quality issues, green/grey screen fixes
- **Audience**: All users, first-line support

### 🔧 Technical Documentation

**[Recording Pipeline Reference](./technical/RECORDING_PIPELINE.md)** ⭐ NEW
- **Location**: `docs/technical/RECORDING_PIPELINE.md`
- **Size**: 900+ lines of detailed technical documentation
- **Purpose**: Complete architectural and technical reference for the native 4K recording pipeline
- **Contents**:
  - GStreamer pipeline architecture with flow diagrams
  - Detailed explanation of every pipeline element
  - Camera sensor and ISP configuration
  - Performance characteristics (CPU, thermal, storage, framerate)
  - Lighting behavior analysis (daylight vs low light)
  - Troubleshooting pipeline-specific issues
  - Advanced configuration and tuning
- **Audience**: Developers, DevOps, technical support

**[API Reference](./technical/API_REFERENCE.md)**
- **Location**: `docs/technical/API_REFERENCE.md`
- **Purpose**: Complete REST API documentation
- **Contents**:
  - All endpoints with request/response examples
  - Recording and preview mode management
  - Error codes and handling
  - TypeScript interfaces
  - Complete workflow examples
  - Prometheus metrics
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
- **Resolution**: 2880×1620 @ 25 fps (4.67 megapixels per frame)
- **FOV**: 56% center crop from 4K sensor (no downscaling)
- **Quality**: 18 Mbps H.264 encoding with native 4K sharpness
- **Reliability**: Rock-solid 25.0 fps with ±0.1 fps variance
- **Performance**: 88% CPU usage with 11% headroom for stability

**Dual Camera System**
- Simultaneous recording from 2× IMX477 cameras (12.3 MP sensors)
- Independent CPU core allocation (cores 0-2 for cam0, cores 3-5 for cam1)
- Segmented recording (5-minute MKV files for easy handling)

**Web Dashboard**
- Live preview streaming (calibration and setup modes)
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
3. Refer to [Troubleshooting Guide](./user/TROUBLESHOOTING.md) if issues arise

**Daily Operation**:
- Start recording via web dashboard
- Monitor system status during matches
- Download recordings after completion

### For Developers

**System Architecture**:
1. **[Recording Pipeline Reference](./technical/RECORDING_PIPELINE.md)** - Deep dive into GStreamer pipeline, performance characteristics, and technical specifications
2. **[API Reference](./technical/API_REFERENCE.md)** - REST API endpoints, request/response formats, and integration examples
3. **[Deployment Guide](./DEPLOYMENT_GUIDE.md)** - Installation procedures and system configuration

**Key Components**:
- **API Service**: `/home/mislav/footballvision-pro/src/platform/simple_api_enhanced.py`
- **Recording Scripts**: `/home/mislav/footballvision-pro/scripts/record_dual_native4k_55fov.sh`
- **Preview Service**: `/home/mislav/footballvision-pro/src/video-pipeline/preview_service_*.py`
- **Web Dashboard**: `/home/mislav/footballvision-pro/src/platform/web-dashboard/`

---

## Recording Modes

### Production Recording (Default)

**Mode**: `normal`
- **Resolution**: 2880×1620
- **Framerate**: 25 fps
- **FOV**: 56% (center crop)
- **Bitrate**: 18 Mbps per camera
- **Use Case**: Match-day recording

### Setup/Alignment

**Mode**: `no_crop`
- **Resolution**: 1920×1080
- **Framerate**: 30 fps
- **FOV**: 100% (full sensor, downscaled)
- **Bitrate**: 15 Mbps per camera
- **Use Case**: Camera positioning and alignment

### Preview Modes

**Normal Preview**: 1280×720 @ 15fps (50% FOV, 2 Mbps)
**Calibration Preview**: 1920×1080 @ 30fps (25% FOV, 8 Mbps) - for focus calibration

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
- **Per Segment (5 min)**: ~1.3 GB

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

### Start Calibration Preview

```bash
curl -X POST http://localhost/api/v1/preview/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"calibration"}'
```

### Check Framerate in Recording

```bash
ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=nb_read_frames,avg_frame_rate \
  /mnt/recordings/match_001/segments/cam0_00000.mkv
```

---

## Version History

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
- Implemented native 4K recording at 2880×1620 @ 25fps
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
- Added calibration preview mode (1920×1080 @ 30fps)
- Updated recording state management for real-time updates

**Documentation**:
- Created comprehensive Recording Pipeline Technical Reference
- Updated API Reference with mode management
- Enhanced Deployment Guide with validation procedures
- Updated Troubleshooting Guide with pipeline-specific issues

### Version 1.0 (September 30, 2025)

- Initial documentation system
- Basic recording and preview functionality
- Web dashboard with matches tab

---

## Support and Contributing

**Internal Documentation**: This documentation is maintained for the FootballVision Pro development team.

**For Questions**:
- Technical issues: Check [Troubleshooting Guide](./user/TROUBLESHOOTING.md)
- Pipeline details: See [Recording Pipeline Reference](./technical/RECORDING_PIPELINE.md)
- API integration: Refer to [API Reference](./technical/API_REFERENCE.md)

**System Logs**:
```bash
journalctl -u footballvision-api-enhanced -f  # API service logs
journalctl -u footballvision-api-enhanced -n 100  # Last 100 lines
```

---

---

## Documentation File Structure

Complete documentation tree with file locations:

```
footballvision-pro/
└── docs/
    ├── README.md                           # This file - Documentation index
    ├── DEPLOYMENT_GUIDE.md                 # Installation and setup guide
    ├── CAMERA_CONFIGURATION.md             # ⭐ NEW Camera config technical reference (1500+ lines)
    ├── CAMERA_CONTROLS_QUICK_GUIDE.md      # ⭐ NEW Quick reference for camera controls
    │
    ├── user/                               # End-user documentation
    │   ├── QUICK_START_GUIDE.md           # Basic operation guide
    │   └── TROUBLESHOOTING.md             # Common issues and fixes
    │
    └── technical/                          # Technical documentation
        ├── RECORDING_PIPELINE.md          # Complete pipeline reference (900+ lines)
        └── API_REFERENCE.md               # REST API documentation
```

### File Sizes and Content

| File | Size | Lines | Last Updated |
|------|------|-------|--------------|
| **CAMERA_CONFIGURATION.md** ⭐ NEW | 36 KB | 1500+ | Oct 20, 2025 |
| **CAMERA_CONTROLS_QUICK_GUIDE.md** ⭐ NEW | 9 KB | 400+ | Oct 20, 2025 |
| **RECORDING_PIPELINE.md** | 27 KB | 900+ | Oct 17, 2025 |
| **API_REFERENCE.md** | 15 KB | 670+ | Oct 17, 2025 |
| **DEPLOYMENT_GUIDE.md** | 10 KB | 370+ | Oct 17, 2025 |
| **TROUBLESHOOTING.md** | 4 KB | 100+ | Oct 17, 2025 |
| **README.md** (this file) | 10 KB | 480+ | Oct 20, 2025 |
| **QUICK_START_GUIDE.md** | 3 KB | 94 | Oct 1, 2025 |

### Key Source Code Locations

Referenced throughout the documentation:

```
footballvision-pro/
├── config/
│   └── camera_config.json                 # ⭐ Camera configuration storage
│
├── scripts/
│   ├── record_dual_native4k_55fov.sh      # Production recording pipeline
│   └── record_dual_1080p30_no_crop.sh     # Setup/alignment mode
│
├── shaders/
│   └── shader_generator.py                # ⭐ Dynamic GLSL shader generation
│
├── src/
│   ├── platform/
│   │   ├── simple_api_enhanced.py         # Enhanced API service (with camera config endpoints)
│   │   └── web-dashboard/
│   │       └── src/
│   │           ├── types/
│   │           │   └── camera.ts          # ⭐ Camera config TypeScript types
│   │           ├── services/
│   │           │   └── api.ts             # API client (with camera methods)
│   │           ├── components/
│   │           │   └── CameraControlPanel.tsx  # ⭐ Camera controls UI
│   │           └── pages/
│   │               └── Preview.tsx        # Preview page (with camera controls)
│   │
│   └── video-pipeline/
│       ├── camera_config_manager.py       # ⭐ Configuration management
│       ├── preview_service_gpu_corrected.py  # GPU-accelerated preview
│       ├── recording_manager_enhanced.py  # Recording mode management
│       └── preview_service.py             # Preview streaming
│
└── docs/                                  # Documentation (this directory)
```

---

**Documentation Version**: 2.1
**System Version**: Native 4K @ 25fps (2880×1620, 56% FOV) + Interactive Camera Configuration
**Last Updated**: October 20, 2025

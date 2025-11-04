# FootballVision Pro - Panorama Stitching Master Guide
## 🎯 THE COMPLETE REFERENCE ("PROJECT BIBLE")

**Version**: 1.0.0
**Created**: 2025-11-04
**Last Updated**: 2025-11-04
**Status**: Implementation in Progress (Phase 1)

---

## 📋 TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [What This Module Does](#what-this-module-does)
3. [System Requirements](#system-requirements)
4. [Architecture Overview](#architecture-overview)
5. [Implementation Status](#implementation-status)
6. [File Structure](#file-structure)
7. [Core Components](#core-components)
8. [API Reference](#api-reference)
9. [Configuration](#configuration)
10. [Calibration Process](#calibration-process)
11. [Testing Strategy](#testing-strategy)
12. [Performance Benchmarks](#performance-benchmarks)
13. [Troubleshooting](#troubleshooting)
14. [Deployment Guide](#deployment-guide)
15. [Handover Checklist](#handover-checklist)
16. [Future Enhancements](#future-enhancements)
17. [Development History](#development-history)

---

## 1. EXECUTIVE SUMMARY

### What Problem Does This Solve?

FootballVision Pro currently records two separate camera feeds (cam0, cam1) independently. This panorama module **combines both cameras into a single seamless wide-angle view** using GPU-accelerated stitching.

### Why GPU Acceleration?

- **CPU-based stitching**: Too slow (~2-3 FPS) for real-time preview
- **VPI (Vision Programming Interface)**: NVIDIA's optimized library for Jetson
- **Result**: 15-20 FPS real-time stitching using VIC hardware accelerator

### Key Design Decision

**Parallel Service Architecture**: Panorama runs as a completely separate service during testing. It doesn't modify existing recording/preview functionality. When both are needed, **recording takes priority** (panorama is blocked).

### Current Status

**Phase 1: Foundation** ✅ (Complete on 2025-11-04)
- Module structure created
- Documentation initiated
- Configuration framework ready

**Next Steps**: Implement frame synchronizer and config manager (Phase 2)

---

## 2. WHAT THIS MODULE DOES

### Use Cases

**Use Case 1: Real-Time Panorama Preview**
```
User opens Dashboard → Enables "Panorama Preview" →
Both cameras stream → VPI stitches in real-time →
Single wide HLS stream at /hls/panorama.m3u8
```

**Use Case 2: Post-Processing Recorded Matches**
```
User records match with both cameras → Recording stops →
User requests "Create Panorama" → System processes offline →
Output: panorama_archive.mp4 (3840x1315, 4K-friendly)
```

**Use Case 3: Camera Calibration** (One-Time Setup)
```
User runs calibration → System captures 15-20 frame pairs →
Calculates homography matrix → Stores in panorama_config.json →
Future stitching uses this calibration (10x faster)
```

### What It Doesn't Do

- ❌ Replace existing dual-camera recording (both modes coexist)
- ❌ Modify existing preview/recording services
- ❌ Run simultaneously with recording (recording has priority)
- ❌ Work without camera overlap (requires 20-30% overlapping FOV)

---

## 3. SYSTEM REQUIREMENTS

### Hardware

- **Device**: NVIDIA Jetson Orin Nano (tested platform)
- **Cameras**: 2× IMX477 sensors with overlapping field of view
- **Memory**: 8GB RAM (panorama uses ~500MB for buffers)
- **Storage**: Standard (no additional requirements)

### Software

**Pre-installed**:
- ✅ VPI 3.2.4 (NVIDIA Vision Programming Interface)
- ✅ OpenCV 4.8.0 (for fallback feature detection)
- ✅ GStreamer 1.20.3 with NVIDIA plugins
- ✅ Python 3.10+

**VPI Backends Required**:
- ✅ VIC (Video Image Compositor) - Hardware perspective warp
- ✅ CUDA - Feature detection, blending
- ✅ CPU - Homography calculation (calibration only)

**Check Installation**:
```bash
# Verify VPI
python3 -c "import vpi; print('VPI:', vpi.__version__)"
# Expected: VPI: 3.2.4

# Check VPI backends
python3 -c "import vpi; print('VIC available:', vpi.Backend.VIC in vpi.Backend)"
# Expected: VIC available: True
```

### Network Requirements

- Same as existing system (no additional requirements)

---

## 4. ARCHITECTURE OVERVIEW

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ PANORAMA STITCHING ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Real-Time Preview Mode:                                        │
│  ┌──────────┐                                                   │
│  │  cam0    │ → nvarguscamerasrc → nvvidconv → appsink         │
│  └──────────┘                          ↓                        │
│                                  FrameSynchronizer              │
│                                  (timestamp matching)           │
│                                         ↓                        │
│  ┌──────────┐                    VPIPanoramaStitcher           │
│  │  cam1    │ → nvarguscamerasrc → nvvidconv → appsink         │
│  └──────────┘                          ↓                        │
│                                  (VIC perspective warp)         │
│                                  (CUDA blending)                │
│                                         ↓                        │
│                                    appsrc → x264enc             │
│                                         ↓                        │
│                              hlssink2 → /hls/panorama.m3u8     │
│                                                                 │
│  Post-Processing Mode:                                          │
│  cam0_archive.mp4 ──┐                                          │
│                     ├→ VPI Stitcher → panorama_archive.mp4    │
│  cam1_archive.mp4 ──┘   (frame-by-frame)                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Service Independence

```
┌────────────────────────────────────────────────────────────────┐
│ EXISTING SERVICES (Untouched)                                  │
├────────────────────────────────────────────────────────────────┤
│  recording_service.py    → Records cam0, cam1 independently    │
│  preview_service.py      → Previews cam0, cam1 independently   │
│  post_processing_service.py → Merges/encodes cam0, cam1        │
└────────────────────────────────────────────────────────────────┘
                               ↑
                               │ (No modifications)
                               ↓
┌────────────────────────────────────────────────────────────────┐
│ NEW PANORAMA SERVICE (Parallel)                                │
├────────────────────────────────────────────────────────────────┤
│  panorama_service.py     → Stitches cam0 + cam1               │
│  calibration_service.py  → One-time camera alignment          │
│  vpi_stitcher.py         → GPU stitching engine               │
└────────────────────────────────────────────────────────────────┘
```

**Key Principle**: If recording is active, panorama service refuses to start (returns error). This ensures zero interference.

---

## 5. IMPLEMENTATION STATUS

### Implementation Phases

| Phase | Component | Status | Date Completed |
|-------|-----------|--------|----------------|
| 1 | Foundation & Documentation | ✅ Complete | 2025-11-04 |
| 2 | Frame Synchronizer | 🔄 In Progress | - |
| 3 | Config Manager | 🔄 In Progress | - |
| 4 | VPI Stitcher (Core Engine) | ⏳ Pending | - |
| 5 | Calibration Service | ⏳ Pending | - |
| 6 | Panorama Service | ⏳ Pending | - |
| 7 | API Integration | ⏳ Pending | - |
| 8 | Testing & Validation | ⏳ Pending | - |
| 9 | Production Deployment | ⏳ Pending | - |

### Feature Completion Checklist

**Core Functionality**:
- [ ] Frame synchronization (timestamp-based matching)
- [ ] VPI stitching engine (VIC + CUDA)
- [ ] Camera calibration tool
- [ ] Real-time preview stitching
- [ ] Post-processing stitching
- [ ] HLS stream output (/hls/panorama.m3u8)

**API Endpoints**:
- [ ] `POST /api/v1/panorama/preview` - Start preview
- [ ] `DELETE /api/v1/panorama/preview` - Stop preview
- [ ] `POST /api/v1/panorama/calibration/start` - Begin calibration
- [ ] `POST /api/v1/panorama/calibration/capture` - Capture frame
- [ ] `POST /api/v1/panorama/calibration/calculate` - Calculate homography
- [ ] `POST /api/v1/panorama/process/{match_id}` - Post-process recording
- [ ] `GET /api/v1/panorama/status` - Get service status

**Configuration**:
- [ ] panorama_config.json structure
- [ ] Calibration data storage
- [ ] Feature flags (enable/disable)
- [ ] Performance presets

**Testing**:
- [ ] Unit tests for all components
- [ ] Integration tests
- [ ] Performance benchmarks
- [ ] Camera overlap validation

**Documentation**:
- [x] Master guide (this document)
- [ ] API reference
- [ ] Configuration guide
- [ ] Troubleshooting guide
- [ ] Deployment checklist

---

## 6. FILE STRUCTURE

### Complete File Tree

```
footballvision-pro/
├── src/
│   ├── panorama/                              ← NEW MODULE
│   │   ├── __init__.py                       [✅ Phase 1]
│   │   ├── README.md                         [⏳ Phase 2]
│   │   ├── config_manager.py                 [🔄 Phase 2]
│   │   ├── frame_synchronizer.py             [🔄 Phase 2]
│   │   ├── vpi_stitcher.py                   [⏳ Phase 3]
│   │   ├── calibration_service.py            [⏳ Phase 4]
│   │   ├── panorama_service.py               [⏳ Phase 5]
│   │   ├── pipeline_builders.py              [⏳ Phase 5]
│   │   ├── utils.py                          [⏳ Phase 5]
│   │   └── tests/                            [⏳ Phase 7]
│   │       ├── __init__.py                   [✅ Phase 1]
│   │       ├── test_vpi_stitcher.py
│   │       ├── test_synchronizer.py
│   │       └── test_calibration.py
│   │
│   ├── platform/
│   │   ├── simple_api_v3.py                  [🔄 Phase 6 - Add router]
│   │   └── panorama_router.py                [⏳ Phase 6]
│   │
│   └── video-pipeline/                        ← EXISTING (Unchanged)
│       ├── recording_service.py
│       ├── preview_service.py
│       └── post_processing_service.py
│
├── config/
│   ├── camera_config.json                     ← EXISTING
│   └── panorama_config.json                   [🔄 Phase 2]
│
└── docs/
    ├── PANORAMA_MASTER_GUIDE.md              [✅ Phase 1 - THIS FILE]
    ├── PANORAMA_API.md                       [⏳ Phase 8]
    ├── PANORAMA_CONFIGURATION.md             [⏳ Phase 8]
    └── PANORAMA_TROUBLESHOOTING.md           [⏳ Phase 8]
```

### File Responsibilities

**config_manager.py** (138 lines estimated)
- Load/save panorama_config.json
- Validate configuration
- Check calibration status
- Provide calibration data to stitcher

**frame_synchronizer.py** (96 lines estimated)
- Buffer frames from both cameras
- Match frames by timestamp (±33ms tolerance)
- Handle dropped frames
- Report sync quality metrics

**vpi_stitcher.py** (245 lines estimated)
- Core VPI stitching engine
- VIC hardware perspective warp
- CUDA blending in overlap region
- Zero-copy NVMM operations (future optimization)
- Performance: 15-20 FPS @ 1440×960

**calibration_service.py** (189 lines estimated)
- Capture synchronized frame pairs
- VPI Harris corner detection
- Feature matching
- Homography calculation with RANSAC
- Calibration quality validation

**panorama_service.py** (312 lines estimated)
- Main service (follows RecordingService pattern)
- Manage preview pipelines
- Handle post-processing requests
- State persistence
- Thread-safe operations

**pipeline_builders.py** (178 lines estimated)
- Build GStreamer pipelines for panorama
- Dual appsink for frame capture
- Appsrc for stitched output
- HLS sink configuration

**panorama_router.py** (156 lines estimated)
- FastAPI router for panorama endpoints
- Request/response models
- Error handling
- Integration with panorama_service

---

## 7. CORE COMPONENTS

### 7.1 Frame Synchronizer

**Purpose**: Match frames from cam0 and cam1 based on timestamps

**Algorithm**:
```python
# Pseudo-code
for each new frame:
    1. Add to camera buffer (ring buffer, size=4)
    2. Find oldest frame from each buffer
    3. Calculate timestamp difference
    4. If diff < 33ms: Return pair
    5. If diff > 33ms: Drop older frame, retry
```

**Performance Metrics**:
- `sync_success_rate`: % of frames successfully paired (target: >95%)
- `avg_drift_ms`: Average timestamp difference (target: <16ms)
- `dropped_frames`: Count of frames dropped due to sync failure

**Configuration**:
```json
{
  "frame_synchronizer": {
    "buffer_size": 4,
    "max_drift_ms": 33,
    "drop_threshold": 3
  }
}
```

### 7.2 VPI Stitcher

**Purpose**: GPU-accelerated image stitching using NVIDIA VPI

**VPI Backend Selection**:
```python
# Backend priority
backend = vpi.Backend.VIC | vpi.Backend.CUDA

# VIC: Hardware perspective warp (fastest)
# CUDA: Feature detection, blending (fast)
# CPU: Fallback only
```

**Stitching Pipeline**:
```
1. Load calibration homography matrix
2. Warp cam1 to align with cam0 (VPI VIC backend)
3. Identify overlap region (e.g., x=2200 to x=2880)
4. Alpha blend overlap (VPI CUDA backend)
5. Concatenate non-overlapping regions
6. Output: 3840×1315 stitched frame
```

**Performance Targets**:
- Real-time (preview): 15-20 FPS @ 1440×960
- Post-processing: 5-8 FPS @ 2880×1752
- Latency: <200ms glass-to-glass

**Key Functions**:
```python
class VPIPanoramaStitcher:
    def __init__(self, calibration_data: Dict):
        """Initialize with homography matrix"""

    def stitch_frames(self, frame_left: np.ndarray, frame_right: np.ndarray) -> np.ndarray:
        """Stitch two frames (NumPy arrays)"""

    def stitch_vpi_images(self, vpi_left: vpi.Image, vpi_right: vpi.Image) -> vpi.Image:
        """Stitch VPI images (zero-copy, fastest)"""
```

### 7.3 Calibration Service

**Purpose**: One-time camera alignment to calculate homography matrix

**Calibration Workflow**:
```
1. User starts calibration mode
   → Dual appsink pipelines capture synchronized frames

2. User captures 15-20 frame pairs
   → Press SPACE to capture
   → Captures displayed in UI for validation

3. System calculates homography
   → VPI Harris corner detection on each frame
   → Feature matching between cameras
   → RANSAC to calculate homography matrix
   → Reprojection error validation

4. Calibration saved to panorama_config.json
   → Homography matrix
   → Overlap region
   → Blend width
   → Quality score (0-1)
```

**Quality Validation**:
- Reprojection error < 5 pixels: Excellent
- Reprojection error 5-10 pixels: Good
- Reprojection error > 10 pixels: Poor (recalibrate)

**Calibration Data Structure**:
```json
{
  "calibration": {
    "homography_cam1_to_cam0": [
      [0.998, -0.002, 45.3],
      [0.001, 0.999, 2.1],
      [0.0, 0.0, 1.0]
    ],
    "overlap_region": {
      "start_x": 2200,
      "end_x": 2880,
      "width": 680
    },
    "blend_width": 150,
    "calibration_date": "2025-11-04T20:00:00Z",
    "quality_score": 0.96,
    "reprojection_error": 3.2
  }
}
```

### 7.4 Panorama Service

**Purpose**: Main service managing panorama preview and post-processing

**Service Pattern** (follows existing RecordingService):
```python
class PanoramaService:
    def __init__(self):
        self.gst_manager = GStreamerManager()  # Reuse existing
        self.stitcher = None  # Lazy-loaded
        self.synchronizer = FrameSynchronizer()
        self.preview_active = False
        self.state_lock = Lock()

    def start_preview(self) -> Dict:
        """Start real-time panorama preview"""
        # 1. Check if recording active (priority check)
        # 2. Acquire pipeline lock (PANORAMA_PREVIEW mode)
        # 3. Load calibration
        # 4. Start dual appsink pipelines
        # 5. Start stitching thread
        # 6. Start appsrc→HLS output pipeline
        # 7. Return HLS URL

    def stop_preview(self) -> Dict:
        """Stop panorama preview"""
        # 1. Stop stitching thread
        # 2. Stop pipelines
        # 3. Release lock

    def process_recording(self, match_id: str) -> Dict:
        """Post-process recorded match"""
        # 1. Load cam0_archive.mp4, cam1_archive.mp4
        # 2. Stitch frame-by-frame
        # 3. Encode to panorama_archive.mp4
        # 4. Return result
```

**State Persistence**:
```json
// /tmp/footballvision_panorama_state.json
{
  "preview_active": false,
  "last_preview_start": "2025-11-04T19:30:00Z",
  "last_preview_stop": "2025-11-04T19:45:00Z",
  "calibrated": true,
  "total_uptime_seconds": 3600
}
```

---

## 8. API REFERENCE

### Base URL
```
http://localhost:8000/api/v1/panorama
```

### Endpoints

#### 8.1 Preview Management

**Start Panorama Preview**
```http
POST /api/v1/panorama/preview

Response 200:
{
  "success": true,
  "message": "Panorama preview started",
  "hls_url": "/hls/panorama.m3u8",
  "resolution": "3840x1315",
  "fps_target": 15
}

Response 409 (Recording Active):
{
  "success": false,
  "message": "Cannot start panorama: recording is active",
  "error_code": "RECORDING_ACTIVE"
}

Response 503 (Not Calibrated):
{
  "success": false,
  "message": "Panorama not calibrated",
  "error_code": "NOT_CALIBRATED"
}
```

**Stop Panorama Preview**
```http
DELETE /api/v1/panorama/preview

Response 200:
{
  "success": true,
  "message": "Panorama preview stopped"
}
```

**Get Panorama Status**
```http
GET /api/v1/panorama/status

Response 200:
{
  "preview_active": false,
  "calibrated": true,
  "calibration_date": "2025-11-04T20:00:00Z",
  "quality_score": 0.96,
  "performance": {
    "current_fps": 0,
    "avg_sync_drift_ms": 0,
    "dropped_frames": 0
  }
}
```

#### 8.2 Calibration Management

**Start Calibration**
```http
POST /api/v1/panorama/calibration/start

Response 200:
{
  "success": true,
  "message": "Calibration mode started",
  "instruction": "Press SPACE to capture frame pairs, ESC when done"
}
```

**Capture Frame Pair**
```http
POST /api/v1/panorama/calibration/capture

Response 200:
{
  "success": true,
  "captured_count": 5,
  "target_count": 15,
  "message": "Frame pair 5/15 captured"
}
```

**Calculate Homography**
```http
POST /api/v1/panorama/calibration/calculate

Response 200:
{
  "success": true,
  "message": "Calibration complete",
  "quality_score": 0.96,
  "reprojection_error": 3.2,
  "recommendation": "Excellent calibration"
}

Response 400 (Insufficient Frames):
{
  "success": false,
  "message": "Need at least 10 frame pairs, only 5 captured"
}
```

**Clear Calibration**
```http
DELETE /api/v1/panorama/calibration

Response 200:
{
  "success": true,
  "message": "Calibration data cleared"
}
```

#### 8.3 Post-Processing

**Process Recording**
```http
POST /api/v1/panorama/process/{match_id}

Response 200:
{
  "success": true,
  "message": "Processing started",
  "match_id": "match_20251104_001",
  "estimated_duration_minutes": 180
}

Response 404:
{
  "success": false,
  "message": "Match not found: match_20251104_001"
}
```

**Get Processing Status**
```http
GET /api/v1/panorama/process/{match_id}/status

Response 200:
{
  "processing": true,
  "progress": 45,
  "estimated_remaining_minutes": 99,
  "current_fps": 6.2
}
```

---

## 9. CONFIGURATION

### 9.1 panorama_config.json Structure

```json
{
  "version": "1.0.0",
  "enabled": true,
  "calibration": {
    "homography_cam1_to_cam0": [
      [0.998, -0.002, 45.3],
      [0.001, 0.999, 2.1],
      [0.0, 0.0, 1.0]
    ],
    "overlap_region": {
      "start_x": 2200,
      "end_x": 2880,
      "width": 680
    },
    "blend_width": 150,
    "calibration_date": "2025-11-04T20:00:00Z",
    "quality_score": 0.96,
    "reprojection_error": 3.2
  },
  "output": {
    "width": 3840,
    "height": 1315,
    "format": "NV12",
    "bitrate_kbps": 22000
  },
  "performance": {
    "preview_fps_target": 15,
    "preview_resolution": {
      "width": 1440,
      "height": 960
    },
    "use_vic_backend": true,
    "buffer_size": 4
  },
  "frame_synchronizer": {
    "buffer_size": 4,
    "max_drift_ms": 33,
    "drop_threshold": 3
  },
  "feature_flags": {
    "api_enabled": true,
    "preview_enabled": true,
    "post_processing_enabled": true,
    "calibration_enabled": true
  }
}
```

### 9.2 Configuration Management

**Load Configuration**:
```python
from panorama.config_manager import PanoramaConfigManager

config_mgr = PanoramaConfigManager()
config = config_mgr.load_config()

if config_mgr.is_calibrated():
    calibration = config_mgr.get_calibration_data()
else:
    print("Panorama not calibrated")
```

**Save Configuration**:
```python
config['enabled'] = False
config_mgr.save_config(config)
```

---

## 10. CALIBRATION PROCESS

### 10.1 When to Calibrate

**Required Calibration**:
- ✅ First-time setup
- ✅ After camera remounting
- ✅ After camera angle adjustment
- ✅ If stitching quality degrades

**No Re-calibration Needed**:
- ❌ After software update
- ❌ After system reboot
- ❌ Normal usage

### 10.2 Step-by-Step Calibration Guide

**Step 1: Prepare Environment**
```bash
# Ensure both cameras working
curl http://localhost:8000/api/v1/status

# Ensure no recording active
curl http://localhost:8000/api/v1/recording
# Should show: "recording": false
```

**Step 2: Start Calibration**
```bash
curl -X POST http://localhost:8000/api/v1/panorama/calibration/start
```

**Step 3: Capture Frame Pairs**
- Point cameras at scene with rich features (e.g., football field with lines, goals)
- Ensure good lighting
- Capture 15-20 frame pairs:
  ```bash
  # Capture frame pair
  curl -X POST http://localhost:8000/api/v1/panorama/calibration/capture
  # Repeat 15-20 times
  ```

**Step 4: Calculate Homography**
```bash
curl -X POST http://localhost:8000/api/v1/panorama/calibration/calculate
```

**Step 5: Validate Quality**
```bash
curl http://localhost:8000/api/v1/panorama/status
# Check: quality_score (target: >0.90)
#        reprojection_error (target: <5 pixels)
```

**Step 6: Test Stitching**
```bash
# Start preview to test
curl -X POST http://localhost:8000/api/v1/panorama/preview

# View in browser
open http://localhost:8080/  # Dashboard
# Check panorama stream quality
```

### 10.3 Calibration Troubleshooting

**Poor Quality Score (<0.80)**:
- More frame pairs needed (capture 20-25)
- Better feature-rich scene needed
- Check camera focus
- Ensure cameras aren't moving during capture

**High Reprojection Error (>10 pixels)**:
- Cameras may have moved between captures
- Insufficient overlap between cameras
- Clear calibration and retry

---

## 11. TESTING STRATEGY

### 11.1 Unit Tests

**Location**: `src/panorama/tests/`

**Test Coverage**:
- [ ] Frame synchronization (buffer management, timestamp matching)
- [ ] VPI stitching (perspective warp, blending)
- [ ] Calibration (homography calculation, validation)
- [ ] Config manager (load, save, validation)

**Run Unit Tests**:
```bash
cd /home/mislav/footballvision-pro
python3 -m pytest src/panorama/tests/ -v
```

### 11.2 Integration Tests

**Scenarios**:
1. **Priority Enforcement**: Start recording → Try panorama → Expect rejection
2. **Calibration Workflow**: Start → Capture → Calculate → Validate
3. **Real-Time Preview**: Start → Verify HLS → Check FPS → Stop
4. **Post-Processing**: Record match → Process → Verify output

### 11.3 Performance Benchmarks

**Targets**:
- Real-time stitching: 15-20 FPS @ 1440×960
- Post-processing: 5-8 FPS @ 2880×1752
- Frame sync success: >95%
- Average sync drift: <16ms
- CPU usage: <70% during preview
- Memory usage: <2GB total

**Benchmark Tool**:
```bash
python3 -m panorama.tests.benchmark --duration 60
# Runs for 60 seconds, reports performance metrics
```

---

## 12. PERFORMANCE BENCHMARKS

### 12.1 Expected Performance

**Real-Time Preview (1440×960)**:
- FPS: 15-20
- Latency: <200ms
- CPU: 60-70%
- GPU (VIC): 40-50%
- Memory: 1.8-2.0GB total

**Post-Processing (2880×1752)**:
- FPS: 5-8
- Processing time: ~1.5-2× video duration
- Example: 60-minute match → 90-120 minutes

**Frame Synchronization**:
- Success rate: >95%
- Average drift: 8-16ms
- Dropped frames: <2%

### 12.2 Performance Monitoring

**Prometheus Metrics** (exposed at `/metrics`):
```
# Panorama preview status
footballvision_panorama_preview_active{} 1

# Stitching FPS
footballvision_panorama_fps{} 17.3

# Frame sync quality
footballvision_panorama_sync_drift_ms{} 12.4
footballvision_panorama_dropped_frames_total{} 15

# Processing jobs
footballvision_panorama_processing_jobs{} 0
```

---

## 13. TROUBLESHOOTING

### 13.1 Common Issues

**Issue: "Panorama not calibrated"**
```
Error: API returns 503 "Panorama not calibrated"
Cause: Calibration data missing in panorama_config.json
Fix: Run calibration process (see Section 10)
```

**Issue: "Cannot start panorama: recording is active"**
```
Error: API returns 409 "Recording is active"
Cause: Recording service has priority, blocking panorama
Fix: Stop recording first, then start panorama
```

**Issue: "Poor stitching quality (visible seams)"**
```
Cause: Calibration is outdated or poor quality
Fix:
1. Check calibration quality: GET /api/v1/panorama/status
2. If quality_score < 0.80: Re-calibrate
3. Ensure cameras haven't moved since calibration
```

**Issue: "Low FPS (< 10 FPS)"**
```
Cause: CPU/GPU overload or poor synchronization
Fix:
1. Check sync metrics: avg_drift_ms should be < 20ms
2. Reduce preview resolution in config
3. Check system load: tegrastats
4. Ensure VIC backend is enabled
```

**Issue: "Frame sync failures (>10% dropped)"**
```
Cause: Cameras not synchronized properly
Fix:
1. Check if hardware frame sync available
2. Increase buffer_size in config (default: 4)
3. Increase max_drift_ms tolerance (default: 33)
```

### 13.2 Debug Mode

**Enable Debug Logging**:
```python
# In panorama_service.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

**View Detailed Logs**:
```bash
sudo journalctl -u footballvision-api-enhanced -f | grep panorama
```

---

## 14. DEPLOYMENT GUIDE

### 14.1 Pre-Deployment Checklist

**System Validation**:
- [ ] VPI 3.2.4 installed and working
- [ ] Both cameras functional (check /dev/video0, /dev/video1)
- [ ] Camera overlap confirmed (>20%)
- [ ] Existing recording/preview services working
- [ ] Sufficient disk space (>10GB free)
- [ ] Memory available (>2GB free)

**Code Validation**:
- [ ] All unit tests passing
- [ ] Integration tests passing
- [ ] Performance benchmarks meet targets
- [ ] API endpoints tested
- [ ] Documentation complete

### 14.2 Deployment Steps

**Step 1: Update Code**
```bash
cd /home/mislav/footballvision-pro
git pull origin main
```

**Step 2: Install Dependencies** (if any new)
```bash
pip3 install -r requirements.txt
```

**Step 3: Create Configuration**
```bash
# Copy template
cp config/panorama_config.json.template config/panorama_config.json

# Edit as needed
nano config/panorama_config.json
```

**Step 4: Run Calibration**
```bash
# Start API server (if not running)
sudo systemctl restart footballvision-api-enhanced

# Run calibration
curl -X POST http://localhost:8000/api/v1/panorama/calibration/start
# ... capture frames ...
curl -X POST http://localhost:8000/api/v1/panorama/calibration/calculate
```

**Step 5: Test Preview**
```bash
# Start panorama preview
curl -X POST http://localhost:8000/api/v1/panorama/preview

# Verify HLS stream
ls -la /dev/shm/hls/panorama.m3u8

# View in browser
open http://vid.nk-otok.hr/
```

**Step 6: Monitor Performance**
```bash
# Watch system stats
tegrastats

# Check API metrics
curl http://localhost:8000/metrics | grep panorama
```

### 14.3 Rollback Procedure

**If Issues Occur**:

**Option 1: Disable Panorama** (soft disable)
```bash
# Edit config
python3 -c "
import json
with open('config/panorama_config.json', 'r+') as f:
    config = json.load(f)
    config['enabled'] = False
    f.seek(0)
    json.dump(config, f, indent=2)
"

# Restart API
sudo systemctl restart footballvision-api-enhanced
```

**Option 2: Remove Panorama Module** (hard rollback)
```bash
# Stop API
sudo systemctl stop footballvision-api-enhanced

# Remove panorama module
rm -rf src/panorama/

# Remove panorama router import from simple_api_v3.py
# (Manual edit or git checkout)

# Restart API
sudo systemctl start footballvision-api-enhanced
```

**Validation After Rollback**:
```bash
# Verify existing endpoints still work
curl http://localhost:8000/api/v1/recording
curl http://localhost:8000/api/v1/preview

# Verify panorama endpoints gone
curl http://localhost:8000/api/v1/panorama/preview
# Should return 404 or 503
```

---

## 15. HANDOVER CHECKLIST

### 15.1 For Outgoing Developer

**Before Handover**:
- [ ] All code committed to GitHub
- [ ] This master guide updated with latest status
- [ ] All configuration files in repository
- [ ] Known issues documented in Section 13
- [ ] TODOs clearly marked in code with `# TODO:` comments
- [ ] Performance benchmarks recorded
- [ ] Test results documented

**Handover Meeting Agenda**:
1. Demo current functionality (preview, calibration, post-processing)
2. Walk through this master guide (30 minutes)
3. Review architecture diagram (Section 4)
4. Show current implementation status (Section 5)
5. Discuss known issues and blockers
6. Review next steps (Section 15.2)

### 15.2 For Incoming Developer

**Day 1: Environment Setup**
```bash
# 1. Clone repository
git clone git@github.com:Wandeon/metcam.git footballvision-pro
cd footballvision-pro

# 2. Read master guide (THIS FILE)
less docs/PANORAMA_MASTER_GUIDE.md

# 3. Check VPI installation
python3 -c "import vpi; print('VPI:', vpi.__version__)"

# 4. Check existing system works
curl http://localhost:8000/api/v1/health

# 5. Review current status
curl http://localhost:8000/api/v1/panorama/status
```

**Day 2: Code Review**
- Read all files in `src/panorama/` (start with `__init__.py`)
- Run existing unit tests: `pytest src/panorama/tests/`
- Review API endpoints in `panorama_router.py`

**Day 3: Testing**
- Capture test frames from both cameras
- Validate camera overlap
- Test calibration process
- Test preview stitching

**Week 1 Goal**: Understand entire system, can start/stop preview

### 15.3 Critical Knowledge Transfer

**Calibration is Key**:
- Without calibration, stitching won't work
- Calibration is camera-position-specific
- Always validate quality_score >0.90

**Recording Priority**:
- Recording ALWAYS blocks panorama
- This is intentional (safety mechanism)
- Never modify this behavior without discussion

**VPI Backends**:
- VIC = Hardware accelerator (fastest)
- CUDA = GPU (fast)
- CPU = Software (slowest, avoid)
- Always use VIC when available

**Frame Synchronization**:
- Cameras aren't hardware-synced
- Software sync via timestamps
- Some frame drops are normal (<5%)

---

## 16. FUTURE ENHANCEMENTS

### 16.1 Phase 2 Features (Post-MVP)

**Real-Time Recording**:
- Record panorama during live match (not just post-processing)
- Output 3 files: cam0, cam1, panorama

**UI Integration**:
- Dashboard toggle: "Enable Panorama Preview"
- Calibration UI with visual feedback
- Side-by-side view (individual + panorama)

**Hardware Frame Sync**:
- Check if IMX477 supports frame sync
- Implement hardware trigger for both cameras
- Eliminate sync drift

**Zero-Copy NVMM**:
- Direct NVMM surface stitching
- Eliminate CPU memory copies
- Potential 2-3× FPS improvement

### 16.2 Performance Optimizations

**Caching**:
- Cache warped images for static cameras
- Re-use warp matrices

**Dynamic Resolution**:
- Auto-adjust resolution based on CPU load
- Start high, drop if FPS falls below target

**Multi-Threading**:
- Separate threads for capture, stitch, encode
- Pipeline parallelism

**GPU Blending**:
- Implement custom CUDA kernel for blending
- Potential 20-30% speed improvement

### 16.3 Advanced Features

**3+ Camera Support**:
- Extend to 3 or 4 cameras
- Multiple homography matrices
- Complex overlap blending

**Adaptive Calibration**:
- Auto-detect calibration drift
- Suggest re-calibration
- Online calibration refinement

**Exposure Blending**:
- HDR-style blending in overlap region
- Compensate for exposure differences

---

## 17. DEVELOPMENT HISTORY

### Timeline

**2025-11-04** - Project Initiation
- User requested panorama stitching feature
- Evaluated options: RidgeRun ($5000) vs Free (OpenCV vs VPI)
- Decision: VPI for GPU acceleration, $0 cost
- Created master guide (this document)
- Created module structure

**2025-11-04** - Phase 1: Foundation ✅
- Created `src/panorama/` module
- Wrote comprehensive documentation
- Defined architecture and API
- Set up testing framework
- **Status**: Foundation complete, ready for Phase 2

**[Future Entries]**
- Add dates and notes as implementation progresses

### Key Decisions

**Decision 1: VPI vs OpenCV**
- **Date**: 2025-11-04
- **Context**: Need GPU acceleration, RidgeRun too expensive
- **Choice**: VPI (NVIDIA's library for Jetson)
- **Rationale**: Native GPU support, zero cost, optimized for platform

**Decision 2: Parallel Service Architecture**
- **Date**: 2025-11-04
- **Context**: Don't break existing recording system
- **Choice**: Separate panorama service, recording has priority
- **Rationale**: Safety first, test independently, easy rollback

**Decision 3: 4K-Friendly Output (3840×1315)**
- **Date**: 2025-11-04
- **Context**: Full width (5184×1752) may have compatibility issues
- **Choice**: Downscale to 3840×1315
- **Rationale**: Better player compatibility, maintains aspect ratio

---

## 📞 SUPPORT & CONTACTS

**Repository**: https://github.com/Wandeon/metcam

**Key Files**:
- Master Guide (this file): `docs/PANORAMA_MASTER_GUIDE.md`
- Module Code: `src/panorama/`
- Configuration: `config/panorama_config.json`

**For Questions**:
1. Check Section 13 (Troubleshooting)
2. Check GitHub Issues
3. Review recent commits for context

---

## ✅ HANDOVER VERIFICATION

Before considering handover complete, verify:

**Documentation**:
- [x] Master guide complete (this file)
- [ ] API reference complete
- [ ] Configuration guide complete
- [ ] Troubleshooting guide complete

**Code**:
- [x] Module structure created
- [ ] All core components implemented
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing

**Testing**:
- [ ] Camera overlap validated
- [ ] Calibration tested and working
- [ ] Preview stitching tested
- [ ] Post-processing tested
- [ ] Performance benchmarks meet targets

**Deployment**:
- [ ] Deployed to production
- [ ] Monitoring in place
- [ ] Rollback procedure tested

**Knowledge Transfer**:
- [ ] Handover meeting completed
- [ ] Incoming developer can run system
- [ ] Incoming developer understands architecture
- [ ] All questions answered

---

**END OF MASTER GUIDE**

*This document is the single source of truth for the panorama stitching module. Keep it updated as implementation progresses.*

**Last Updated**: 2025-11-04
**Version**: 1.0.0
**Status**: Foundation Complete (Phase 1 ✅)

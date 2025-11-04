# FootballVision Pro - Panorama Stitching Implementation Plan

## Overview

Combine cam0 and cam1 into a single wide panoramic view for football field coverage. This provides a seamless wide-angle view instead of two separate camera feeds.

## Current Setup

- **Cameras**: 2× IMX477 sensors (3840×2160 @ 30fps)
- **Current Output**: 2880×1752 per camera (after crop)
- **Separation**: Unknown physical distance/overlap between cameras
- **Platform**: NVIDIA Jetson Orin Nano with OpenCV 4.8.0

## Implementation Approach

We'll use **OpenCV's Stitcher API** for panorama creation, with three operational modes:

### Mode 1: Real-Time Stitching (Preview)
- Stitch frames in real-time during preview
- Lower resolution for performance (960×540 per camera)
- ~10-15 FPS stitched output
- Used for: Camera alignment, composition preview

### Mode 2: Post-Processing Stitching (Recording)
- Record both cameras separately at full quality
- Stitch during post-processing (slower, higher quality)
- Full resolution panorama output
- Used for: Final match recordings

### Mode 3: Calibration Mode
- Capture synchronized frame pairs
- Calculate homography matrices
- Store calibration data for faster stitching
- Run once per camera setup change

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ FootballVision Pro - Panorama Stitching Architecture           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  OPTION A: Real-Time Stitching (Preview Mode)                  │
│  ┌─────────────┐                                                │
│  │   Camera 0  │ → nvarguscamerasrc @ 960×540                   │
│  └─────────────┘     ↓ nvvidconv → appsink                     │
│                      ↓                                          │
│  ┌─────────────┐    ↓ Python Thread                            │
│  │   Camera 1  │ → ├→ OpenCV Stitcher                          │
│  └─────────────┘    ↓ (GPU accelerated)                        │
│                      ↓ appsrc → x264enc → HLS                   │
│                      → /dev/shm/hls/panorama.m3u8              │
│                                                                 │
│  OPTION B: Post-Processing Stitching (After Recording)         │
│  ┌─────────────┐                                                │
│  │   Camera 0  │ → Record @ 2880×1752 → segments/cam0_*.mp4   │
│  └─────────────┘                                                │
│                                                                 │
│  ┌─────────────┐                                                │
│  │   Camera 1  │ → Record @ 2880×1752 → segments/cam1_*.mp4   │
│  └─────────────┘                                                │
│                                                                 │
│  After Stop:                                                    │
│    1. Extract frames from both cameras (ffmpeg)                │
│    2. Stitch frame pairs (OpenCV Stitcher)                     │
│    3. Encode to video (ffmpeg)                                 │
│    → panorama_archive.mp4                                      │
│                                                                 │
│  OPTION C: Calibration Mode                                    │
│  - Capture 10-20 synchronized frame pairs                      │
│  - Calculate homography matrices (one-time)                    │
│  - Store in: config/panorama_calibration.json                 │
│  - Use calibration for faster stitching                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Calibration Tool (Essential First Step)

**File**: `src/video-pipeline/panorama_calibration.py`

**Purpose**: Capture synchronized frames and calculate stitching parameters

**Features**:
- Capture 10-20 frame pairs from both cameras
- Detect keypoints using SIFT/ORB
- Match features between cameras
- Calculate homography transformation matrix
- Store calibration in JSON:
  ```json
  {
    "homography_matrix": [[...], [...], [...]],
    "overlap_region": {"left": 100, "right": 200},
    "blend_width": 50,
    "timestamp": "2025-11-04T20:00:00Z"
  }
  ```

**Usage**:
```bash
python3 panorama_calibration.py --capture
# Displays live preview, press SPACE to capture, ESC when done
# Saves to: config/panorama_calibration.json
```

### Phase 2: Panorama Stitching Service

**File**: `src/video-pipeline/panorama_stitching_service.py`

**Purpose**: Core stitching logic using OpenCV

**Key Functions**:
```python
class PanoramaStitcher:
    def __init__(self, calibration_file=None):
        """Initialize with optional calibration data"""
        self.stitcher = cv2.Stitcher.create(cv2.STITCHER_PANORAMA)
        self.homography = None  # Load from calibration if available

    def stitch_frames(self, frame_left, frame_right):
        """Stitch two frames into panorama"""
        # If calibrated, use homography for fast stitching
        # Otherwise, use full feature detection (slower)

    def stitch_videos(self, video_left_path, video_right_path, output_path):
        """Post-process two videos into panorama"""
        # Extract frames, stitch, re-encode
```

**Performance Targets**:
- Real-time (960×540): 10-15 FPS
- Post-processing (2880×1752): ~2-3 FPS (acceptable for offline)

### Phase 3: Real-Time Preview (GStreamer + Python)

**Integration Approach**:
```python
# Dual appsink → Python stitcher → appsrc → HLS
cam0_pipe = "nvarguscamerasrc sensor-id=0 ! ... ! appsink name=sink0"
cam1_pipe = "nvarguscamerasrc sensor-id=1 ! ... ! appsink name=sink1"

# Python thread pulls from both sinks
# Stitches frames
# Pushes to appsrc → x264enc → hlssink2
```

**Challenge**: Synchronization between cameras
- Use timestamps to match frames
- Buffer management for frame alignment
- Handle dropped frames gracefully

### Phase 4: Post-Processing Mode

**Integration with `post_processing_service.py`**:

Add panorama option:
```python
def process_recording(self, match_id: str, create_panorama: bool = False):
    # ... existing merge + re-encode logic ...

    if create_panorama:
        # Stitch cam0_archive.mp4 + cam1_archive.mp4
        # Output: panorama_archive.mp4
        panorama_result = self.stitch_videos(
            cam0_archive, cam1_archive, panorama_output
        )
```

### Phase 5: API Endpoints

**New Endpoints** (add to `simple_api_v3.py`):

```python
# Start panorama preview
POST /api/v1/preview/panorama
Response: {"success": true, "hls_url": "/hls/panorama.m3u8"}

# Get panorama calibration status
GET /api/v1/panorama/calibration
Response: {
  "calibrated": true,
  "calibration_date": "2025-11-04T20:00:00Z",
  "quality_score": 0.95
}

# Trigger calibration
POST /api/v1/panorama/calibrate
Body: {"num_frames": 15}
Response: {"success": true, "message": "Calibration complete"}
```

### Phase 6: UI Integration

**Add to Dashboard** (`Dashboard.tsx`):

```tsx
// New toggle for panorama mode
<div className="panorama-mode">
  <input
    type="checkbox"
    checked={panoramaMode}
    onChange={(e) => setPanoramaMode(e.target.checked)}
  />
  <label>
    Enable Panorama Stitching
    <span className="text-sm">
      {calibrated ? "✓ Calibrated" : "⚠ Needs calibration"}
    </span>
  </label>
</div>

// Calibration button
{!calibrated && (
  <button onClick={runCalibration}>
    Run Panorama Calibration
  </button>
)}
```

**Add to Preview** (new panorama player):
- Display stitched preview when enabled
- Show both individual + stitched views side-by-side

## Technical Considerations

### Camera Overlap

**Critical**: Cameras must have overlapping field of view!

Current setup: 2880×1752 per camera after crop
- If cameras are side-by-side: Need ~20-30% horizontal overlap
- If insufficient overlap: Stitching will fail or produce artifacts

**Test Overlap**:
1. Capture frame from each camera
2. Check if there's visible overlap (same objects in both frames)
3. If no overlap: Adjust camera angles inward

### Synchronization

**Challenge**: Cameras capture frames independently
- Solution 1: Use hardware sync (if supported by IMX477)
- Solution 2: Timestamp-based matching (±33ms tolerance @ 30fps)
- Solution 3: Buffer frames and match by content similarity

### Performance

**Real-Time Stitching CPU Usage**:
- Feature detection: SIFT (~500ms per frame pair @ full res)
- Homography estimation: ~50ms
- Warping + blending: ~100ms

**GPU Acceleration**:
- OpenCV can use CUDA for feature detection
- Check if CUDA-enabled OpenCV is installed:
  ```bash
  python3 -c "import cv2; print(cv2.cuda.getCudaEnabledDeviceCount())"
  ```

**Optimization Strategy**:
- Use calibration to skip feature detection (10× faster)
- Lower resolution for real-time (960×540 vs 2880×1752)
- Use ORB instead of SIFT (faster, similar quality)

### Output Resolution

**Stitched Panorama Size**:
- Input: 2× 2880×1752 frames
- Overlap: ~20% (576 pixels)
- Output width: 2880 + 2880 - 576 = **5184 pixels**
- Output height: 1752 pixels
- **Final**: ~5184×1752 (ultra-wide 3:1 aspect ratio)

This is larger than 4K (3840×2160)!
- May need to downscale for compatibility
- Consider 3840×1315 output (maintain aspect ratio)

### Encoding Challenges

**Bitrate Calculation**:
- 5184×1752 @ 30fps with same quality as individual cameras
- Pixels: 5184×1752 = 9.08 megapixels (vs 5.04 per camera)
- Bitrate: ~22-25 Mbps for good quality

**Compatibility**:
- Most players support up to 4K (3840×2160)
- 5184×1752 may cause compatibility issues
- **Recommendation**: Downscale to 3840×1315

## Implementation Order (Recommended)

### Week 1: Foundation
1. ✅ Create calibration tool
2. ✅ Capture test frames
3. ✅ Verify camera overlap exists
4. ✅ Generate calibration data

### Week 2: Core Stitching
5. ✅ Implement PanoramaStitcher class
6. ✅ Test offline stitching with captured frames
7. ✅ Optimize performance (calibration-based stitching)

### Week 3: Post-Processing Integration
8. ✅ Integrate with post_processing_service.py
9. ✅ Add panorama option to recording flow
10. ✅ Test full recording → stitch → archive workflow

### Week 4: Real-Time Preview
11. ✅ Implement dual-camera appsink/appsrc pipeline
12. ✅ Add panorama preview mode
13. ✅ Test real-time stitching performance

### Week 5: API & UI
14. ✅ Add API endpoints
15. ✅ Add UI controls
16. ✅ End-to-end testing

## Alternative: Simple Side-by-Side (Quick Win)

If stitching proves complex or cameras lack overlap, implement **side-by-side mode**:

```python
# Simply concatenate frames horizontally
panorama = np.hstack([frame_left, frame_right])
# Output: 5760×1752 (no blending, visible seam)
```

**Pros**:
- Extremely fast (no feature detection)
- Always works (no overlap needed)
- Easy to implement

**Cons**:
- Visible seam between cameras
- No blending
- Not a true panorama

This can be a fallback or "Quick Mode" option.

## Hardware Requirements Check

Before implementation, verify:

```bash
# 1. Check if cameras have overlapping FOV
# Capture test frame from each camera
# Visually inspect for overlap

# 2. Check CUDA support for GPU acceleration
python3 -c "import cv2; print('CUDA devices:', cv2.cuda.getCudaEnabledDeviceCount())"

# 3. Check available memory for stitching
free -h
# Need: ~2GB free for real-time stitching buffer

# 4. Test OpenCV stitcher
python3 -c "
import cv2
stitcher = cv2.Stitcher.create(cv2.STITCHER_PANORAMA)
print('Stitcher created successfully:', stitcher)
"
```

## Expected Results

**Successful Implementation**:
- ✅ Seamless panorama combining both cameras
- ✅ ~5184×1752 output (or 3840×1315 downscaled)
- ✅ Real-time preview at 10-15 FPS
- ✅ Post-processed archive at full quality
- ✅ Configurable via Dashboard UI

**Performance**:
- Real-time: Acceptable for preview/alignment
- Post-processing: ~2-3× longer than individual camera processing
- Disk usage: Similar to individual cameras (higher resolution, similar bitrate)

## Next Steps

1. **Immediate**: Check camera overlap
   - Capture frame from each camera
   - Visually inspect for overlapping content
   - Measure overlap percentage

2. **If overlap exists** (>15%):
   - Proceed with OpenCV Stitcher implementation
   - Start with calibration tool

3. **If no overlap**:
   - Consider side-by-side mode as alternative
   - Or adjust camera mounting angles

**Ready to proceed?** Let me know if you want to:
- A) Check camera overlap first
- B) Start with calibration tool implementation
- C) Implement simple side-by-side mode first (quick win)

---

**Document Version**: 1.0
**Created**: 2025-11-04
**Author**: Claude Code

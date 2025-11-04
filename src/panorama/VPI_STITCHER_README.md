# VPIStitcher - GPU-Accelerated Panorama Stitching

## Overview

The `VPIStitcher` class provides GPU-accelerated panorama stitching for FootballVision Pro using NVIDIA VPI 3.2.4 on Jetson Orin Nano. It combines dual IMX477 camera feeds into a seamless wide-angle panoramic view with hardware-accelerated processing.

## Key Features

- **Hardware Acceleration**: Uses VIC backend for perspective warp operations
- **GPU Processing**: CUDA backend for image blending and compositing
- **Dual Mode Operation**:
  - **Calibrated Mode**: Fast stitching with pre-computed homography (15-20 FPS @ 1440×960)
  - **Uncalibrated Mode**: Feature detection per frame (5-8 FPS @ 2880×1752)
- **Zero-Copy Operations**: VPI wraps numpy arrays for efficient memory usage
- **Performance Tracking**: Built-in statistics for monitoring FPS and timing
- **Flexible Output**: Configurable output resolution and blend width

## Architecture

```
┌─────────────┐     ┌─────────────┐
│  Camera 0   │     │  Camera 1   │
│  (Left)     │     │  (Right)    │
└──────┬──────┘     └──────┬──────┘
       │                   │
       │  BGR Frames       │  BGR Frames
       │  (H×W×3)         │  (H×W×3)
       └───────┬───────────┘
               ▼
       ┌───────────────────┐
       │   VPIStitcher     │
       │                   │
       │ 1. VPI Conversion │ (numpy → VPI)
       │ 2. Perspective    │ (VIC Backend)
       │    Warp           │
       │ 3. Alpha Blending │ (CUDA Backend)
       │                   │
       └────────┬──────────┘
                ▼
        ┌───────────────┐
        │   Panorama    │
        │ (3840×1315×3) │
        └───────────────┘
```

## Performance Targets

| Mode | Resolution | Target FPS | Backend |
|------|-----------|------------|---------|
| Preview | 1440×960 | 15-20 FPS | VIC + CUDA |
| Full Quality | 2880×1752 | 5-8 FPS | VIC + CUDA |
| Post-Processing | 3840×1315 | 5-8 FPS | VIC + CUDA |

## Installation

### Prerequisites

```bash
# NVIDIA VPI 3.2.4 for Jetson Orin Nano
sudo apt-get update
sudo apt-get install -y nvidia-vpi3-dev python3-vpi3

# Python dependencies
pip3 install numpy
```

### Verification

```python
import vpi
print(f"VPI Version: {vpi.__version__}")
print(f"Available backends: {vpi.Backend}")
```

## Usage

### Basic Calibrated Stitching

```python
import numpy as np
from vpi_stitcher import VPIStitcher

# Pre-computed homography from calibration
homography = np.array([
    [0.95, 0.05, 50],
    [-0.02, 0.98, 10],
    [0.0, 0.0, 1.0]
], dtype=np.float32)

# Initialize stitcher
stitcher = VPIStitcher(
    output_width=3840,
    output_height=1315,
    use_vic=True,      # Hardware acceleration
    use_cuda=True,     # GPU blending
    homography=homography,
    blend_width=200
)

# Stitch frames
frame_cam0 = ... # BGR frame from left camera
frame_cam1 = ... # BGR frame from right camera

panorama, metadata = stitcher.stitch_frames(frame_cam0, frame_cam1)

print(f"Stitched panorama: {panorama.shape}")
print(f"FPS: {metadata['fps']:.2f}")
print(f"Stitch time: {metadata['stitch_time_ms']:.2f} ms")

# Clean up
stitcher.cleanup()
```

### Uncalibrated Mode

```python
# Start without homography
stitcher = VPIStitcher(
    output_width=3840,
    output_height=1315,
    homography=None  # Uncalibrated mode
)

# Later, after computing homography via calibration
computed_homography = compute_homography(...)  # From calibration service
stitcher.update_homography(computed_homography)
```

### Performance Monitoring

```python
stitcher = VPIStitcher(
    output_width=1440,
    output_height=960,
    homography=homography
)

# Process frames
for frame_cam0, frame_cam1 in frame_pairs:
    panorama, metadata = stitcher.stitch_frames(frame_cam0, frame_cam1)

    # Monitor performance
    stats = stitcher.get_stats()
    print(f"Avg FPS: {stats['fps']:.2f}")
    print(f"Avg stitch time: {stats['avg_stitch_time_ms']:.2f} ms")
    print(f"Warp time: {stats['warp_time_ms']:.2f} ms")
    print(f"Blend time: {stats['blend_time_ms']:.2f} ms")

# Reset statistics if needed
stitcher.reset_stats()
```

## API Reference

### VPIStitcher Class

#### Constructor

```python
VPIStitcher(
    output_width: int = 3840,
    output_height: int = 1315,
    use_vic: bool = True,
    use_cuda: bool = True,
    homography: Optional[np.ndarray] = None,
    blend_width: int = 200
)
```

**Parameters:**
- `output_width`: Output panorama width in pixels (default: 3840)
- `output_height`: Output panorama height in pixels (default: 1315)
- `use_vic`: Enable VIC backend for hardware-accelerated warp (default: True)
- `use_cuda`: Enable CUDA backend for GPU blending (default: True)
- `homography`: Pre-computed 3×3 homography matrix for calibrated mode (default: None)
- `blend_width`: Width of blending region in pixels (default: 200)

#### Methods

##### stitch_frames()

```python
stitch_frames(
    frame_cam0: np.ndarray,
    frame_cam1: np.ndarray
) -> Tuple[np.ndarray, Dict]
```

Stitch two camera frames into a panorama.

**Parameters:**
- `frame_cam0`: Left camera frame (H, W, 3) in BGR format
- `frame_cam1`: Right camera frame (H, W, 3) in BGR format

**Returns:**
- Tuple of (panorama, metadata)
  - `panorama`: Stitched panorama image (output_height, output_width, 3) BGR
  - `metadata`: Dictionary containing:
    - `timestamp`: Unix timestamp
    - `stitch_time_ms`: Total stitching time in milliseconds
    - `fps`: Instantaneous FPS
    - `calibrated_mode`: Boolean indicating mode
    - `output_shape`: Tuple of output dimensions
    - `blend_width`: Blending region width
    - `timings`: Breakdown of processing times

**Raises:**
- `ValueError`: If frames have incompatible shapes or invalid format
- `RuntimeError`: If VPI operations fail

##### update_homography()

```python
update_homography(homography: np.ndarray) -> None
```

Update the homography matrix for calibrated stitching.

**Parameters:**
- `homography`: New 3×3 homography transformation matrix

**Raises:**
- `ValueError`: If homography has invalid shape

##### get_stats()

```python
get_stats() -> Dict
```

Get current stitching statistics.

**Returns:**
- Dictionary containing:
  - `frames_stitched`: Total number of frames processed
  - `avg_stitch_time_ms`: Average stitching time
  - `fps`: Current FPS
  - `last_stitch_time_ms`: Most recent frame time
  - `warp_time_ms`: Perspective warp time
  - `blend_time_ms`: Blending time
  - `conversion_time_ms`: Format conversion time

##### reset_stats()

```python
reset_stats() -> None
```

Reset performance statistics to zero.

##### cleanup()

```python
cleanup() -> None
```

Clean up VPI resources and free GPU memory. Should be called when stitcher is no longer needed.

### StitchingStats Class

Internal dataclass for tracking performance metrics.

```python
@dataclass
class StitchingStats:
    frames_stitched: int = 0
    total_stitch_time_ms: float = 0.0
    avg_stitch_time_ms: float = 0.0
    fps: float = 0.0
    last_stitch_time_ms: float = 0.0
    warp_time_ms: float = 0.0
    blend_time_ms: float = 0.0
    conversion_time_ms: float = 0.0
```

## VPI Backend Selection

### VIC Backend (Hardware)

- **Purpose**: Perspective warp operations
- **Hardware**: Jetson Orin Nano Vision Image Compositor
- **Performance**: Fastest, lowest CPU/GPU usage
- **Limitations**: Fixed-function hardware, specific operations only

### CUDA Backend (GPU)

- **Purpose**: Image blending and compositing
- **Hardware**: Jetson Orin Nano GPU (1024 CUDA cores)
- **Performance**: Fast, programmable
- **Flexibility**: Supports complex operations

### CPU Backend (Fallback)

- **Purpose**: Software fallback when GPU unavailable
- **Performance**: Slowest, highest CPU usage
- **Use case**: Development/testing without GPU

## Performance Optimization Tips

### 1. Use Calibrated Mode

Pre-compute homography matrix during calibration phase to avoid per-frame feature detection.

```python
# Slow (uncalibrated)
stitcher = VPIStitcher(homography=None)  # 5-8 FPS

# Fast (calibrated)
stitcher = VPIStitcher(homography=pre_computed)  # 15-20 FPS
```

### 2. Adjust Resolution for Use Case

```python
# Preview: Lower resolution, higher FPS
preview_stitcher = VPIStitcher(output_width=1440, output_height=960)

# Recording: Full resolution, acceptable FPS
recording_stitcher = VPIStitcher(output_width=3840, output_height=1315)
```

### 3. Optimize Blend Width

Wider blends are smoother but slower:

```python
# Fast, visible seam
stitcher = VPIStitcher(blend_width=100)

# Balanced
stitcher = VPIStitcher(blend_width=200)

# Smooth, slower
stitcher = VPIStitcher(blend_width=400)
```

### 4. Monitor Performance

```python
stats = stitcher.get_stats()
if stats['fps'] < 15.0:
    logger.warning(f"Performance degraded: {stats['fps']:.2f} FPS")
    # Consider reducing resolution or blend width
```

## Error Handling

```python
try:
    panorama, metadata = stitcher.stitch_frames(frame_cam0, frame_cam1)
except ValueError as e:
    logger.error(f"Invalid input: {e}")
    # Handle frame shape mismatch or format error
except RuntimeError as e:
    logger.error(f"VPI operation failed: {e}")
    # Handle GPU/hardware errors
finally:
    stitcher.cleanup()
```

## Integration with FootballVision Pro

### With GStreamer Pipeline

```python
# Get frames from GStreamer pipelines
from gstreamer_manager import GStreamerManager

gst_manager = GStreamerManager()

# Extract frames from dual cameras
frame_cam0 = extract_frame_from_pipeline(gst_manager, "cam0")
frame_cam1 = extract_frame_from_pipeline(gst_manager, "cam1")

# Stitch
panorama, metadata = stitcher.stitch_frames(frame_cam0, frame_cam1)
```

### With Calibration Service

```python
from calibration_service import CalibrationService

# Perform calibration
calib_service = CalibrationService()
homography = calib_service.compute_homography(frame_pairs)

# Use calibrated stitcher
stitcher = VPIStitcher(
    output_width=3840,
    output_height=1315,
    homography=homography
)
```

## Testing

Run unit tests:

```bash
cd /home/mislav/footballvision-pro
python3 -m unittest src.panorama.tests.test_vpi_stitcher -v
```

Run examples:

```bash
cd /home/mislav/footballvision-pro/src/panorama
python3 example_usage.py
```

## Troubleshooting

### VPI Import Error

```
ImportError: No module named 'vpi'
```

**Solution**: Install VPI Python bindings
```bash
sudo apt-get install python3-vpi3
```

### VIC Backend Not Available

```
RuntimeError: VIC backend not available
```

**Solution**: Use CUDA backend as fallback
```python
stitcher = VPIStitcher(use_vic=False, use_cuda=True)
```

### Out of Memory

```
RuntimeError: Failed to allocate VPI image
```

**Solution**: Reduce resolution or free GPU memory
```python
stitcher.cleanup()  # Free resources
# Or reduce output resolution
stitcher = VPIStitcher(output_width=1920, output_height=1080)
```

### Low FPS

**Check statistics**:
```python
stats = stitcher.get_stats()
print(f"Warp: {stats['warp_time_ms']:.2f}ms")
print(f"Blend: {stats['blend_time_ms']:.2f}ms")
```

**Solutions**:
- Reduce blend width
- Lower output resolution
- Ensure calibrated mode is enabled
- Check GPU temperature/throttling

## File Structure

```
src/panorama/
├── vpi_stitcher.py           # Main VPIStitcher implementation (464 lines)
├── example_usage.py           # Usage examples and demos
├── VPI_STITCHER_README.md    # This documentation
├── __init__.py               # Module exports
└── tests/
    └── test_vpi_stitcher.py  # Unit tests
```

## Future Enhancements

- [ ] NVMM zero-copy integration for direct GStreamer interop
- [ ] Multi-resolution pyramid blending for better seam transitions
- [ ] Exposure compensation before blending
- [ ] GPU-accelerated feature detection for uncalibrated mode
- [ ] Batch processing support for multiple frame pairs
- [ ] Dynamic blend width based on scene content

## References

- [NVIDIA VPI Documentation](https://docs.nvidia.com/vpi/)
- [VPI Python API Reference](https://docs.nvidia.com/vpi/python_api.html)
- [Jetson Orin Nano Developer Guide](https://developer.nvidia.com/embedded/learn/jetson-orin-nano-devkit-user-guide)

## License

Part of FootballVision Pro - Copyright 2025

## Version

- **VPIStitcher**: v1.0.0
- **VPI**: 3.2.4
- **Created**: 2025-11-04

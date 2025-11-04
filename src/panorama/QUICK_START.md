# VPIStitcher Quick Start Guide

## Installation

```bash
# Install VPI
sudo apt-get install nvidia-vpi3-dev python3-vpi3

# Install dependencies
pip3 install numpy
```

## Basic Usage

### 1. Simple Stitching (Calibrated Mode)

```python
import numpy as np
from src.panorama.vpi_stitcher import VPIStitcher

# Your pre-computed homography matrix
homography = np.array([
    [0.95, 0.05, 50],
    [-0.02, 0.98, 10],
    [0.0, 0.0, 1.0]
], dtype=np.float32)

# Create stitcher
stitcher = VPIStitcher(
    output_width=3840,
    output_height=1315,
    homography=homography
)

# Get frames from your cameras (BGR format, H×W×3)
frame_cam0 = ...  # Left camera
frame_cam1 = ...  # Right camera

# Stitch!
panorama, metadata = stitcher.stitch_frames(frame_cam0, frame_cam1)

print(f"FPS: {metadata['fps']:.2f}")
print(f"Output: {panorama.shape}")

# Cleanup when done
stitcher.cleanup()
```

### 2. Preview Mode (Lower Resolution, Higher FPS)

```python
preview_stitcher = VPIStitcher(
    output_width=1440,
    output_height=960,
    homography=homography,
    blend_width=150
)

# Target: 15-20 FPS
panorama, metadata = preview_stitcher.stitch_frames(frame0, frame1)
```

### 3. Full Quality Mode (Recording)

```python
recording_stitcher = VPIStitcher(
    output_width=3840,
    output_height=1315,
    homography=homography,
    blend_width=300
)

# Target: 5-8 FPS
panorama, metadata = recording_stitcher.stitch_frames(frame0, frame1)
```

### 4. Performance Monitoring

```python
# Process frames
for frame0, frame1 in frame_pairs:
    panorama, metadata = stitcher.stitch_frames(frame0, frame1)

# Get statistics
stats = stitcher.get_stats()
print(f"Frames: {stats['frames_stitched']}")
print(f"Avg FPS: {stats['fps']:.2f}")
print(f"Avg time: {stats['avg_stitch_time_ms']:.2f} ms")
print(f"Warp time: {stats['warp_time_ms']:.2f} ms")
print(f"Blend time: {stats['blend_time_ms']:.2f} ms")
```

## Common Patterns

### Update Homography After Calibration

```python
# Start uncalibrated
stitcher = VPIStitcher(homography=None)

# Later, after calibration
new_homography = compute_calibration(...)
stitcher.update_homography(new_homography)

# Now runs in fast calibrated mode
```

### Error Handling

```python
try:
    panorama, metadata = stitcher.stitch_frames(frame0, frame1)
except ValueError as e:
    print(f"Invalid input: {e}")
except RuntimeError as e:
    print(f"VPI error: {e}")
finally:
    stitcher.cleanup()
```

### Context Manager Pattern

```python
class StitcherContext:
    def __init__(self, homography):
        self.stitcher = VPIStitcher(homography=homography)
    
    def __enter__(self):
        return self.stitcher
    
    def __exit__(self, *args):
        self.stitcher.cleanup()

# Usage
with StitcherContext(homography) as stitcher:
    panorama, metadata = stitcher.stitch_frames(frame0, frame1)
# Automatic cleanup
```

## Configuration Examples

### Preview Configuration
```python
PREVIEW_CONFIG = {
    'output_width': 1440,
    'output_height': 960,
    'use_vic': True,
    'use_cuda': True,
    'blend_width': 150
}
preview_stitcher = VPIStitcher(**PREVIEW_CONFIG, homography=H)
```

### Recording Configuration
```python
RECORDING_CONFIG = {
    'output_width': 3840,
    'output_height': 1315,
    'use_vic': True,
    'use_cuda': True,
    'blend_width': 300
}
recording_stitcher = VPIStitcher(**RECORDING_CONFIG, homography=H)
```

## Metadata Structure

```python
{
    'timestamp': 1699123456.789,
    'stitch_time_ms': 52.34,
    'fps': 19.11,
    'calibrated_mode': True,
    'output_shape': (1315, 3840, 3),
    'blend_width': 200,
    'timings': {
        'conversion_ms': 5.12,
        'warp_ms': 23.45,
        'blend_ms': 18.67
    }
}
```

## Statistics Dictionary

```python
{
    'frames_stitched': 100,
    'avg_stitch_time_ms': 51.23,
    'fps': 19.52,
    'last_stitch_time_ms': 49.87,
    'warp_time_ms': 22.13,
    'blend_time_ms': 17.92,
    'conversion_time_ms': 4.98
}
```

## Performance Tips

1. **Use calibrated mode** (pre-computed homography) for best FPS
2. **Lower resolution** for preview, full resolution for recording
3. **Adjust blend width**: Lower = faster, higher = smoother
4. **Monitor stats**: Check if performance degrades over time
5. **Clean up**: Call `cleanup()` to free GPU memory

## Troubleshooting

### Low FPS
```python
stats = stitcher.get_stats()
if stats['fps'] < 15:
    # Reduce resolution
    stitcher = VPIStitcher(output_width=1280, output_height=720)
    # Or reduce blend width
    stitcher = VPIStitcher(blend_width=100)
```

### VPI Not Available
```python
try:
    import vpi
except ImportError:
    print("Install: sudo apt-get install python3-vpi3")
```

### Out of Memory
```python
# Clean up old stitcher
old_stitcher.cleanup()

# Create new with lower resolution
stitcher = VPIStitcher(output_width=1920, output_height=1080)
```

## Testing

```bash
# Run unit tests
python3 -m unittest src.panorama.tests.test_vpi_stitcher -v

# Run examples
python3 src/panorama/example_usage.py
```

## Files Reference

- **Implementation**: `/home/mislav/footballvision-pro/src/panorama/vpi_stitcher.py`
- **Tests**: `/home/mislav/footballvision-pro/src/panorama/tests/test_vpi_stitcher.py`
- **Examples**: `/home/mislav/footballvision-pro/src/panorama/example_usage.py`
- **Full Docs**: `/home/mislav/footballvision-pro/src/panorama/VPI_STITCHER_README.md`

## Need Help?

1. Check full documentation: `VPI_STITCHER_README.md`
2. Run examples: `python3 example_usage.py`
3. Review test cases: `test_vpi_stitcher.py`
4. Check implementation: `vpi_stitcher.py` (well-commented)

---

**Version**: 1.0.0  
**Date**: 2025-11-04  
**Status**: Production Ready

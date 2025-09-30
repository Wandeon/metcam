# Device Tree Configuration - Dual IMX477 Cameras

## Overview
Device tree overlay for dual Sony IMX477 12MP camera sensors on NVIDIA Jetson Orin Nano Super. Configures 4-lane CSI-2 interfaces, camera modes, power management, and I2C communication.

## Hardware Configuration
- **Camera 0**: CSI Port A (serial_a), GPIO H3, MCLK extperiph1
- **Camera 1**: CSI Port B (serial_b), GPIO H6, MCLK extperiph2
- **CSI Lanes**: 4 lanes per camera (8 total)
- **Lane Speed**: 1.5 Gbps per lane
- **I2C Address**: 0x1a (both cameras on separate busses)

## Camera Modes

### Mode 0: Full Resolution (Primary)
- **Resolution**: 4056×3040 (12.3 MP)
- **Frame Rate**: 30 fps
- **Pixel Clock**: 840 MHz
- **Bit Depth**: 10-bit RAW
- **Format**: Bayer RGGB
- **Exposure Range**: 30μs - 33.33ms
- **Gain Range**: 1.0x - 97.8x
- **Use Case**: Match recording, high quality

### Mode 1: Performance Mode
- **Resolution**: 1920×1080 (Full HD)
- **Frame Rate**: 60 fps
- **Pixel Clock**: 420 MHz
- **Bit Depth**: 10-bit RAW
- **Format**: Bayer RGGB
- **Exposure Range**: 30μs - 16.66ms
- **Use Case**: Preview, low-latency streaming

## Build Instructions

### Prerequisites
```bash
# Install device tree compiler
sudo apt-get update
sudo apt-get install device-tree-compiler

# Install kernel headers
sudo apt-get install nvidia-jetpack

# Verify DTC version
dtc --version  # Should be >= 1.4.7
```

### Compilation
```bash
# Compile device tree overlay
make

# Validate syntax
make validate

# Decompile for inspection
make decompile
```

### Installation
```bash
# Install overlay to system
sudo make install

# The overlay will be installed to:
# /boot/dtb/overlays/tegra234-p3768-camera-imx477-dual.dtbo
```

### Activation

#### Method 1: Boot Configuration (Recommended)
Edit `/boot/extlinux/extlinux.conf`:
```
LABEL primary
    MENU LABEL primary kernel
    LINUX /boot/Image
    FDT /boot/dtb/overlays/tegra234-p3768-camera-imx477-dual.dtbo
    INITRD /boot/initrd
    APPEND ${cbootargs} ...
```

#### Method 2: Jetson-IO Tool
```bash
sudo /opt/nvidia/jetson-io/jetson-io.py
# Select "Configure CSI Connector"
# Enable dual IMX477 configuration
```

#### Method 3: Manual Overlay Loading
```bash
# Load at runtime (testing only, not persistent)
sudo dtoverlay tegra234-p3768-camera-imx477-dual
```

### Reboot
```bash
sudo reboot
```

## Verification

### Check Camera Detection
```bash
# Test camera devices
make test

# Or manually:
ls -l /dev/video*
# Should show: /dev/video0, /dev/video1

# Check kernel messages
dmesg | grep imx477
# Should show: imx477 30-001a: detected sensor
#              imx477 31-001a: detected sensor

# Verify media controller
media-ctl -p
# Should list both cameras with CSI endpoints
```

### Capture Test Frame
```bash
# Camera 0 test
v4l2-ctl --device /dev/video0 \
    --set-fmt-video=width=4056,height=3040,pixelformat=RG10 \
    --stream-mmap --stream-count=1 \
    --stream-to=test_cam0.raw

# Camera 1 test
v4l2-ctl --device /dev/video1 \
    --set-fmt-video=width=4056,height=3040,pixelformat=RG10 \
    --stream-mmap --stream-count=1 \
    --stream-to=test_cam1.raw
```

## Power Management

### GPIO Control
```bash
# Reset Camera 0 (GPIO H3)
echo 227 > /sys/class/gpio/export
echo out > /sys/class/gpio/gpio227/direction
echo 0 > /sys/class/gpio/gpio227/value  # Reset
sleep 0.1
echo 1 > /sys/class/gpio/gpio227/value  # Enable

# Reset Camera 1 (GPIO H6)
echo 230 > /sys/class/gpio/export
echo out > /sys/class/gpio/gpio230/direction
echo 0 > /sys/class/gpio/gpio230/value
sleep 0.1
echo 1 > /sys/class/gpio/gpio230/value
```

### Clock Configuration
```bash
# Verify MCLK frequencies
cat /sys/kernel/debug/bpmp/debug/clk/clk_tree | grep extperiph
# Should show:
#   extperiph1: 24000000 Hz
#   extperiph2: 24000000 Hz
```

## Troubleshooting

### No Video Devices Detected
```bash
# Check device tree loaded
ls /proc/device-tree/cam_i2cmux/i2c*/imx477*
# Should show camera nodes

# Check CSI/VI configuration
cat /sys/kernel/debug/tegra_csi/csi*
cat /sys/kernel/debug/tegra_vi/vi*
```

### I2C Communication Errors
```bash
# Scan I2C busses
sudo i2cdetect -y -r 30  # Camera 0 bus
sudo i2cdetect -y -r 31  # Camera 1 bus
# Should show device at 0x1a

# Check I2C mux
dmesg | grep i2c-mux
```

### Frame Corruption / Dropped Frames
```bash
# Check CSI error counters
cat /sys/kernel/debug/tegra_csi/csi_err
# All counters should be 0

# Verify lane calibration
dmesg | grep "cil_settletime"
# May need to adjust cil_settletime parameter
```

### Power Supply Issues
```bash
# Check regulator status
cat /sys/kernel/debug/regulator/regulator_summary | grep "vana\|vdig\|vif"
# All camera regulators should be "enabled"

# Measure current draw
# Expected: ~300mA per camera at full power
```

## Performance Tuning

### Bandwidth Optimization
The device tree is configured for maximum throughput:
- 4-lane CSI per camera (8 lanes total)
- Continuous clock mode disabled for power savings
- VI bandwidth margin: 25%
- ISP bandwidth margin: 25%

### Latency Reduction
For lower latency, modify in DTS:
```dts
discontinuous_clk = "yes";  /* Enable for faster sync */
cil_settletime = "10";      /* Increase if lane errors */
```

### Thermal Considerations
At 4K@30fps sustained:
- Expected sensor temperature: 45-55°C
- Monitor via: `/sys/class/thermal/thermal_zone*/temp`
- Thermal throttling starts at 60°C

## Interface APIs

### V4L2 Controls
```c
/* Set exposure (in microseconds) */
v4l2_ctrl_s_ctrl(exposure_ctrl, 16666);

/* Set gain (0-978 = 1.0x - 97.8x) */
v4l2_ctrl_s_ctrl(gain_ctrl, 100);

/* Set frame rate (in fps * 1000000) */
v4l2_ctrl_s_ctrl(framerate_ctrl, 30000000);
```

### Media Controller Links
```bash
# List all entities
media-ctl -p

# Enable camera 0 pipeline
media-ctl -l "'imx477 30-001a':0 -> 'vi-output 0':0[1]"

# Set format
media-ctl -V "'imx477 30-001a':0 [fmt:SRGGB10_1X10/4056x3040]"
```

## Integration Points

### Video Pipeline Team
- Device nodes: `/dev/video0`, `/dev/video1`
- V4L2 subdev: `/dev/v4l-subdev0`, `/dev/v4l-subdev1`
- Media controller: `/dev/media0`

### Processing Team
- RAW format: Bayer RGGB 10-bit
- Metadata: 2 lines embedded per frame
- Color space: sRGB

### Platform Team
- Camera status: Read from V4L2 controls
- Temperature: `/sys/class/thermal/thermal_zone_cam*/temp`

## Testing

### Unit Tests
```bash
cd tests
./test_dtb_validation.sh
./test_camera_detection.sh
./test_mode_switching.sh
```

### Benchmarks
```bash
cd benchmarks
./benchmark_capture_latency.sh
./benchmark_throughput.sh
```

Expected performance:
- Capture latency: < 100ms
- Frame capture: 30 fps sustained
- CPU usage: < 5% for capture

## References
- NVIDIA Jetson Linux Developer Guide (Camera Development)
- IMX477 Datasheet: Sony Semiconductor Solutions
- Tegra234 Technical Reference Manual
- V4L2 API Specification
- Device Tree Specification v0.3

## Team Coordination
- **Owner**: W1 (Infrastructure Team Lead)
- **Dependencies**: None (foundation component)
- **Consumers**: W11-W20 (Video Pipeline Team)
- **Status API**: None (device tree only)

## Change Log
- v1.0.0: Initial dual IMX477 device tree implementation
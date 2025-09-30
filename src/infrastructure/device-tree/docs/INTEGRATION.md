# Device Tree Integration Guide

## For Video Pipeline Team (W11-W20)

### Camera Device Access
```c
// Open camera devices
int cam0_fd = open("/dev/video0", O_RDWR);
int cam1_fd = open("/dev/video1", O_RDWR);

// Camera 0: Left camera (serial_a, port 0)
// Camera 1: Right camera (serial_b, port 2)
```

### V4L2 Format Configuration
```c
struct v4l2_format fmt = {
    .type = V4L2_BUF_TYPE_VIDEO_CAPTURE,
    .fmt.pix = {
        .width = 4056,
        .height = 3040,
        .pixelformat = V4L2_PIX_FMT_SRGGB10,
        .field = V4L2_FIELD_NONE,
        .bytesperline = 4056 * 10 / 8,  // 10-bit packed
        .sizeimage = 4056 * 3040 * 10 / 8,
        .colorspace = V4L2_COLORSPACE_SRGB,
    }
};
ioctl(cam0_fd, VIDIOC_S_FMT, &fmt);
```

### Available Pixel Formats
- `V4L2_PIX_FMT_SRGGB10` - 10-bit Bayer RGGB (native)
- `V4L2_PIX_FMT_SRGGB8` - 8-bit Bayer (converted)
- Metadata embedded in first 2 lines

### Control Interface
```c
// Set exposure (microseconds)
struct v4l2_control ctrl = {
    .id = V4L2_CID_EXPOSURE,
    .value = 16666  // 16.66ms for 30fps
};
ioctl(cam0_fd, VIDIOC_S_CTRL, &ctrl);

// Set analog gain (0-978)
ctrl.id = V4L2_CID_GAIN;
ctrl.value = 100;  // 10.0x gain
ioctl(cam0_fd, VIDIOC_S_CTRL, &ctrl);
```

### Media Controller Setup
```bash
# Link camera to VI output
media-ctl -l "'imx477 30-001a':0 -> 'vi-output 0':0[1]"

# Set pipeline format
media-ctl -V "'imx477 30-001a':0 [fmt:SRGGB10_1X10/4056x3040 field:none]"
```

## For Processing Team (W21-W30)

### Raw Data Format
- **Bit Depth**: 10-bit per pixel
- **Packing**: Mipi CSI-2 RAW10 format
- **Byte Order**: Little-endian
- **Line Stride**: Aligned to 64 bytes

### Bayer Pattern
```
R G R G R G ...
G B G B G B ...
R G R G R G ...
...
```
- First pixel (0,0): Red
- Pattern: RGGB

### Metadata Extraction
```c
// First 2 lines contain embedded metadata
struct imx477_metadata {
    uint16_t frame_count;
    uint16_t exposure_hi;
    uint16_t exposure_lo;
    uint16_t gain;
    uint16_t temperature;
    // ... see IMX477 datasheet
} __attribute__((packed));

// Extract from frame buffer
struct imx477_metadata *meta = (struct imx477_metadata *)frame_buffer;
uint32_t exposure_us = (meta->exposure_hi << 16) | meta->exposure_lo;
```

### Debayering Considerations
- Use CUDA-accelerated debayer for performance
- Malvar-He-Cutler algorithm recommended
- White balance coefficients in metadata

## For Platform Team (W31-W40)

### Camera Status Query
```bash
# Check camera availability
v4l2-ctl --device=/dev/video0 --all

# Query supported formats
v4l2-ctl --device=/dev/video0 --list-formats-ext

# Get current settings
v4l2-ctl --device=/dev/video0 --get-fmt-video
```

### Camera Identification
```c
struct v4l2_capability cap;
ioctl(fd, VIDIOC_QUERYCAP, &cap);
// cap.card = "imx477 30-001a"  (Camera 0)
// cap.card = "imx477 31-001a"  (Camera 1)
```

### Temperature Monitoring
```bash
# Sensor junction temperature (estimated)
cat /sys/class/thermal/thermal_zone_cam0/temp
cat /sys/class/thermal/thermal_zone_cam1/temp
```

## GPIO Control

### Camera Reset (Emergency Recovery)
```c
// Camera 0: GPIO 227 (H3)
// Camera 1: GPIO 230 (H6)

int reset_camera(int gpio_num) {
    char path[64];
    snprintf(path, sizeof(path), "/sys/class/gpio/gpio%d/value", gpio_num);

    // Assert reset
    int fd = open(path, O_WRONLY);
    write(fd, "0", 1);
    usleep(100000);  // 100ms

    // Release reset
    write(fd, "1", 1);
    close(fd);

    return 0;
}
```

## Clock Management

### MCLK Configuration
- Camera 0: `extperiph1` @ 24 MHz
- Camera 1: `extperiph2` @ 24 MHz

```bash
# Verify clock rates
cat /sys/kernel/debug/bpmp/debug/clk/clk_tree | grep extperiph
```

### Dynamic Clock Control
```c
// Not recommended - cameras expect fixed 24MHz
// For power savings, use camera standby mode instead
```

## Power Sequencing

### Startup Sequence
1. Enable I2C bus
2. Set reset GPIO low
3. Enable power rails (VANA, VDIG, VIF)
4. Wait 10ms
5. Enable MCLK
6. Wait 5ms
7. Set reset GPIO high
8. Wait 10ms
9. Camera ready for I2C communication

### Shutdown Sequence
1. Stop streaming
2. Set reset GPIO low
3. Disable MCLK
4. Disable power rails
5. Disable I2C bus

## Error Handling

### Common Issues

#### CSI Errors
```bash
# Check error counters
cat /sys/kernel/debug/tegra_csi/csi_err

# Common errors:
# - ppfsm_timeout: Clock issue
# - crc_error: Signal integrity problem
# - multi_bit_error: Bad cable or interference
```

#### I2C Timeout
```c
// Retry logic
int retry_i2c_read(int fd, uint16_t reg, uint8_t *data) {
    for (int i = 0; i < 3; i++) {
        if (i2c_read(fd, reg, data) == 0)
            return 0;
        usleep(10000);  // 10ms retry delay
    }
    return -1;
}
```

#### Frame Corruption
- Check CSI error counters
- Verify power supply stability
- May need to adjust `cil_settletime` in device tree

## Performance Characteristics

### Bandwidth Usage
- 4K@30fps per camera: ~370 MB/s
- Total CSI bandwidth: ~740 MB/s
- Peak VI DMA: ~1.2 GB/s (with margin)

### Latency Budget
- Sensor readout: 33.3ms (30fps)
- CSI transfer: <1ms
- VI processing: <2ms
- DMA transfer: <1ms
- **Total capture latency**: ~35ms

### CPU Overhead
- V4L2 capture: ~2% CPU per camera
- DMA setup: <1% CPU
- Minimal overhead with zero-copy pipeline

## Testing Checklist

- [ ] Both cameras detected at boot
- [ ] No CSI errors under sustained capture
- [ ] Frame rate stable at 30fps
- [ ] Exposure and gain controls working
- [ ] Synchronized capture from both cameras
- [ ] No memory leaks during long captures
- [ ] Recovery from cable disconnect
- [ ] Temperature within limits (<60°C)

## Support

For device tree issues:
- Check kernel log: `dmesg | grep imx477`
- Verify device tree: `ls /proc/device-tree/cam_i2cmux/`
- Contact: W1 (Infrastructure Team Lead)
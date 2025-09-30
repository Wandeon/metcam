# JetPack 6.0 Custom Image Configuration

## Overview
Custom JetPack 6.0 system image optimized for FootballVision Pro. Includes camera drivers, CUDA/TensorRT, system optimizations, and minimal unnecessary packages.

## Features
- JetPack 6.0 (L4T R36.2.0) base
- IMX477 camera drivers (4-lane CSI)
- CUDA 12.2 + cuDNN 8.9 + TensorRT 8.6
- CPU isolation for real-time video processing
- NVMe storage optimization
- Network stack tuning
- Minimal system footprint

## Build Requirements

### Host System
- Ubuntu 20.04 or 22.04 x86_64
- 50GB free disk space
- 16GB RAM minimum
- Internet connection
- Root access

### Dependencies
```bash
sudo apt-get update
sudo apt-get install -y \
    qemu-user-static \
    binfmt-support \
    debootstrap \
    parted \
    kpartx \
    wget \
    tar \
    python3 \
    python3-yaml \
    gzip \
    rsync
```

## Building the Image

### Quick Start
```bash
cd src/infrastructure/jetson-image
sudo ./src/build-image.sh
```

This will:
1. Download JetPack 6.0 base (if not cached)
2. Extract filesystem
3. Install packages and NVIDIA components
4. Apply optimizations
5. Create flashable image
6. Compress final image

Build time: ~2-3 hours on typical hardware.

### Advanced Options
```bash
# Build with custom config
sudo ./src/build-image.sh --config my-config.yaml

# Skip package updates (faster rebuilds)
sudo ./src/build-image.sh --skip-update

# Keep work directory for inspection
sudo ./src/build-image.sh --no-cleanup
```

## Image Contents

### System Configuration
- **Hostname**: `footballvision-{{SERIAL}}`
- **User**: `vision` (UID 1000, auto-login enabled)
- **Timezone**: UTC
- **Locale**: en_US.UTF-8

### Kernel Optimizations
```
CPU Isolation: CPUs 1-5 reserved for video
IRQ Affinity: All IRQs on CPU 0
No-HZ Full: CPUs 1-5 tickless
Huge Pages: Disabled (better for video)
Low Latency: Max C-state limited
```

### NVIDIA Components
- CUDA 12.2 (toolkit + libraries)
- cuDNN 8.9
- TensorRT 8.6
- VPI 3.0
- Multimedia API
- Argus Camera Library
- nvpmodel: MAXN mode (25W)

### Storage Configuration
- **Root**: 16GB ext4 (noatime, commit=60s)
- **Data**: Remaining space on NVMe (noatime, writeback mode)
- **I/O Scheduler**: none (for NVMe)
- **Queue Depth**: 1024

### Network Configuration
- WiFi power management: disabled
- Upload bandwidth limit: 300Mbps
- TCP buffers: 256MB
- IPv6: disabled

### Disabled Services
- Bluetooth
- CUPS printing
- Avahi
- ModemManager
- GUI desktop components

## Flashing the Image

### Using NVIDIA SDK Manager (Recommended)
```bash
# Extract image
gunzip footballvision-jetson-1.0.0.img.gz

# Connect Jetson in recovery mode
# Press and hold RECOVERY button, press RESET, release both

# Flash using SDK Manager
sdkmanager --flash-image footballvision-jetson-1.0.0.img \
    --target jetson-orin-nano-super
```

### Using Custom Flash Script
```bash
# Flash to Jetson via USB
sudo ./scripts/flash-jetson.sh footballvision-jetson-1.0.0.img.gz

# Or flash to SD card/NVMe directly
sudo ./scripts/flash-jetson.sh footballvision-jetson-1.0.0.img.gz /dev/sdX
```

### Recovery Mode
1. Power off Jetson
2. Connect USB-C cable to host
3. Press and hold RECOVERY button
4. Press RESET button briefly
5. Release RECOVERY button
6. Jetson appears as USB device

## Post-Flash Configuration

### First Boot
System will:
1. Expand root partition to fill storage
2. Run optimization scripts
3. Set up CUDA cache
4. Configure NVMe
5. Benchmark system
6. Reboot

Expected first boot time: ~5 minutes

### Manual Optimization
```bash
# Run optimization scripts
sudo /opt/footballvision/scripts/optimize-nvme.sh
sudo /opt/footballvision/scripts/setup-cuda-cache.sh
sudo /opt/footballvision/scripts/configure-cameras.sh

# Benchmark performance
sudo /opt/footballvision/scripts/benchmark-system.sh
```

### Device Tree Installation
```bash
# Install camera device tree overlay
cd /opt/footballvision/device-tree
sudo make install
sudo reboot
```

## Validation

### System Check
```bash
# CUDA
nvcc --version
python3 -c "import pycuda.driver as cuda; cuda.init(); print(f'GPUs: {cuda.Device.count()}')"

# Cameras
ls -l /dev/video*
v4l2-ctl --list-devices

# Storage
nvme list
sudo fio --filename=/mnt/recordings/test --direct=1 --rw=write --bs=1M --size=1G --name=test

# Network
ip addr
iperf3 -c iperf.he.net

# Temperature
cat /sys/class/thermal/thermal_zone*/temp
```

### Expected Performance
- **Boot time**: < 30 seconds
- **CUDA available**: < 10 seconds after boot
- **Camera detection**: < 5 seconds after boot
- **NVMe write**: > 400 MB/s sustained
- **Idle CPU**: < 10%
- **Idle memory**: < 2 GB

## Customization

### Modifying Packages
Edit `src/image-config.yaml`:
```yaml
packages:
  custom:
    - your-package-here
```

Rebuild:
```bash
sudo ./src/build-image.sh
```

### Adding Post-Install Scripts
1. Create script in `scripts/`
2. Add to `image-config.yaml`:
```yaml
post_install:
  scripts:
    - name: "my-script"
      path: "/opt/footballvision/scripts/my-script.sh"
```

### Changing nvpmodel
```yaml
nvidia:
  nvpmodel:
    default_mode: "15W"  # Lower power
```

## Troubleshooting

### Build Fails
```bash
# Check logs
cat build/build.log

# Clean and retry
sudo rm -rf build/
sudo ./src/build-image.sh
```

### Flash Fails
```bash
# Verify recovery mode
lsusb | grep -i nvidia
# Should show: "0955:7023 NVIDIA Corp"

# Check USB connection
dmesg | tail
```

### Cameras Not Detected
```bash
# Check device tree
ls /proc/device-tree/cam_i2cmux/

# Check kernel log
dmesg | grep imx477

# Reinstall device tree
cd /opt/footballvision/device-tree
sudo make install
sudo reboot
```

### Poor NVMe Performance
```bash
# Re-run optimization
sudo /opt/footballvision/scripts/optimize-nvme.sh

# Check SMART status
sudo nvme smart-log /dev/nvme0

# Benchmark
sudo fio --filename=/dev/nvme0n1 --direct=1 --rw=write --bs=1M --size=1G --name=bench
```

### High CPU Usage
```bash
# Check CPU affinity
cat /proc/cmdline | grep isolcpus

# Verify nvpmodel
sudo nvpmodel -q

# Check processes
htop
```

## Performance Tuning

### Maximum Performance
```bash
# Enable jetson-clocks
sudo jetson_clocks --show
sudo jetson_clocks

# Set nvpmodel to MAXN
sudo nvpmodel -m 0

# Verify
sudo tegrastats
```

### Power Saving (Test Mode)
```bash
# Lower power mode
sudo nvpmodel -m 1  # 15W mode

# Disable jetson-clocks
sudo jetson_clocks --restore
```

## Security Considerations

### SSH Access
- Password authentication disabled
- Key-based authentication only
- Root login disabled
- Default port: 22

Add SSH key:
```bash
ssh-copy-id vision@footballvision-XXXX.local
```

### Firewall
UFW enabled with rules:
- SSH (22/tcp)
- HTTP (80/tcp)
- HTTPS (443/tcp)
- RTSP (8554/tcp)

Add custom rule:
```bash
sudo ufw allow 8080/tcp
```

### Updates
Automatic updates disabled for stability. Manual updates:
```bash
sudo apt-get update
sudo apt-get upgrade

# For NVIDIA components
sudo apt-mark hold nvidia-* cuda-* cudnn* tensorrt*
```

## Integration Points

### For Video Pipeline Team
- Cameras available: `/dev/video0`, `/dev/video1`
- GStreamer plugins installed
- NVMM buffers configured
- V4L2 utilities available

### For Processing Team
- CUDA/cuDNN/TensorRT ready
- GPU memory: 6GB allocated to CUDA
- VPI library available
- OpenCV with CUDA support

### For Platform Team
- FastAPI dependencies installed
- Systemd services configured
- Monitoring exporters enabled
- Network optimized for uploads

## Testing

### Unit Tests
```bash
cd tests
./test_cuda_available.sh
./test_cameras.sh
./test_storage.sh
./test_network.sh
```

### Integration Tests
```bash
# Full system validation
sudo ./tests/test_integration.sh

# Expected: All tests pass in < 5 minutes
```

## References
- [JetPack 6.0 Release Notes](https://developer.nvidia.com/jetpack-sdk-60)
- [Jetson Linux Developer Guide](https://docs.nvidia.com/jetson/archives/r36.2/)
- [CUDA 12.2 Documentation](https://docs.nvidia.com/cuda/archive/12.2.0/)
- [TensorRT 8.6 Documentation](https://docs.nvidia.com/deeplearning/tensorrt/archives/tensorrt-86/)

## Team Coordination
- **Owner**: W2 (Infrastructure Team)
- **Dependencies**: W1 (Device Tree)
- **Consumers**: All teams
- **Status**: Foundation component

## Change Log
- v1.0.0: Initial JetPack 6.0 custom image
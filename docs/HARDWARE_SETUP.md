# FootballVision Pro v3 - Hardware Setup Guide

Complete guide for setting up the hardware components for FootballVision Pro v3.

---

## Table of Contents

- [Hardware Requirements](#hardware-requirements)
- [Camera Installation](#camera-installation)
- [Jetson Orin Nano Setup](#jetson-orin-nano-setup)
- [Storage Configuration](#storage-configuration)
- [Network Configuration](#network-configuration)
- [Power Management](#power-management)
- [Hardware Troubleshooting](#hardware-troubleshooting)

---

## Hardware Requirements

### Main Computing Unit

**NVIDIA Jetson Orin Nano Super**
- Model: Jetson Orin Nano Super 8GB (recommended)
- JetPack: Version 6.1 or higher
- Operating System: Ubuntu 22.04 (included with JetPack)
- CPU: 6-core Arm Cortex-A78AE v8.2 64-bit (4 performance cores @ 1.728 GHz + 2 efficiency cores @ 729 MHz)
- GPU: 1024-core NVIDIA Ampere architecture GPU
- **Note:** System is optimized for Jetson Orin Nano Super. Performance cores provide maximum encoding performance.

### Cameras

**2x Sony IMX477 Camera Modules**
- Resolution: 12.3MP (4056 x 3040)
- Sensor size: 1/2.3"
- Maximum framerate: 4K@30fps
- Interface: MIPI CSI-2
- Connection: 15-pin ribbon cable to Jetson CSI ports

**Important:** The FootballVision Pro system requires exactly 2 cameras for stereo recording.

### Storage

**Primary Storage (OS and Application):**
- Minimum: 32GB microSD card or NVMe SSD
- Recommended: 128GB+ NVMe SSD for better performance

**Recording Storage:**
- External USB 3.0+ drive (optional but recommended for long-term recordings)
- Size depends on recording needs:
  - 1 hour recording @ 12Mbps (both cameras) ≈ 10.8 GB
  - 10 hours ≈ 108 GB
  - 100 hours ≈ 1.08 TB

### Power Supply

- **Input:** 5V DC, 4A (20W) via USB-C or barrel jack
- **Recommended:** Official NVIDIA power adapter or equivalent quality
- **Important:** Underpowered supply can cause camera initialization failures

### Network

- Ethernet (recommended) or WiFi
- For live streaming/remote access: 100Mbps+ connection
- For local-only use: Any network connection sufficient

### Additional Hardware (Optional)

- Active cooling fan (recommended for sustained recording)
- Heatsink or thermal solution
- Case/enclosure with camera mounting points
- Tripod or mounting hardware for cameras

---

## Camera Installation

### Physical Connection

#### Step 1: Identify CSI Ports

The Jetson Orin Nano has **2 CSI camera ports**:
- **CAM0:** Camera Port 0 (closest to the heat sink)
- **CAM1:** Camera Port 1

#### Step 2: Connect Cameras

1. **Power off the Jetson** completely
   ```bash
   sudo shutdown -h now
   ```

2. **Connect Camera 1 to CAM0:**
   - Gently lift the CSI port latch
   - Insert the camera ribbon cable with contacts facing inward (toward the heat sink)
   - Ensure cable is fully inserted
   - Press down the latch to secure

3. **Connect Camera 2 to CAM1:**
   - Repeat the process for the second CSI port
   - Ensure both cables are securely locked

4. **Verify connections:**
   - Cables should be firmly seated
   - Latches fully closed
   - No visible gaps between cable and connector

#### Step 3: Camera Mounting

For football field recording:
- Mount cameras side-by-side with appropriate spacing
- Align cameras to cover both goal areas
- Ensure stable mounting to prevent vibration
- Consider weather protection for outdoor use

### Camera Detection

After powering on the Jetson:

1. **Check camera devices:**
   ```bash
   ls -la /dev/video*
   ```

   Expected output (may vary):
   ```
   /dev/video0
   /dev/video1
   /dev/video2
   /dev/video3
   ...
   ```

   **Note:** Multiple video devices per camera is normal. FootballVision Pro uses `/dev/video0` and `/dev/video1` by default.

2. **Verify camera access permissions:**
   ```bash
   ls -la /dev/video0
   ```

   Should show `crw-rw----+ 1 root video ...`

3. **Ensure user is in video group:**
   ```bash
   groups | grep video
   ```

   If not in video group:
   ```bash
   sudo usermod -aG video $USER
   # Log out and back in for changes to take effect
   ```

### Camera Daemon

The `nvargus-daemon` service is critical for camera operation:

```bash
# Check daemon status
sudo systemctl status nvargus-daemon

# Restart if needed
sudo systemctl restart nvargus-daemon

# Enable at boot
sudo systemctl enable nvargus-daemon
```

**Important:** If cameras fail to initialize, restarting nvargus-daemon usually resolves the issue.

---

## Jetson Orin Nano Setup

### Initial Setup

1. **Flash JetPack 6.1+ to Jetson:**
   - Use NVIDIA SDK Manager from a host Ubuntu PC
   - Or use pre-flashed SD card image from NVIDIA
   - Follow NVIDIA's official flashing guide

2. **Initial boot:**
   - Connect display, keyboard, mouse
   - Complete Ubuntu setup wizard
   - Create user account
   - Connect to network

3. **Update system:**
   ```bash
   sudo apt update
   sudo apt upgrade -y
   sudo reboot
   ```

### Verify JetPack Installation

```bash
# Check JetPack version
dpkg -l | grep nvidia-jetpack

# Expected output similar to:
# ii  nvidia-jetpack  6.1  arm64  NVIDIA JetPack Meta Package
```

### Performance Mode

For optimal recording performance on Jetson Orin Nano Super:

```bash
# View available power modes
sudo nvpmodel -q

# Set to MAXN_SUPER mode (mode 2 on Orin Nano Super)
sudo nvpmodel -m 2

# Lock clocks to maximum
sudo jetson_clocks

# Verify current mode
sudo nvpmodel -q
# Should show: NV Power Mode: MAXN_SUPER
#              2
```

**Performance Modes (Jetson Orin Nano Super):**
- Mode 0: 15W (1497.6 MHz max CPU)
- Mode 1: 25W (1344 MHz max CPU)
- Mode 2: MAXN_SUPER (1.728 GHz max CPU, unlimited power) - **REQUIRED for recording**
- Mode 3: 7W (960 MHz, 4 cores only)

**CRITICAL:** Mode 2 (MAXN_SUPER) is required for reliable 30fps dual-camera recording. The system health monitor (`/home/mislav/footballvision-pro/scripts/system_health_monitor.sh`) automatically enforces this setting every 5 minutes.

**Why Mode 2:**
- Maximizes performance cores to 1.728 GHz
- Provides ~2.01 CPU cores per camera for encoding
- No power limits, preventing thermal throttling under load

### Thermal Management

Monitor temperature during recording:

```bash
# Real-time temperature monitoring
watch -n 1 cat /sys/devices/virtual/thermal/thermal_zone*/temp
```

**Safe operating temperature:** Up to 85°C
**Recommended:** Keep below 75°C with active cooling

If temperatures exceed 80°C:
- Add heatsink or fan
- Improve airflow in enclosure
- Consider lowering power mode during extended recordings

---

## Storage Configuration

### Check Available Storage

```bash
# View all mounted filesystems
df -h

# Check specific recording directory
df -h /mnt/recordings
```

### Configure External Storage (Recommended)

For long-term recordings, use external USB storage:

#### Option 1: Manual Mount

```bash
# Identify external drive
sudo fdisk -l
# Look for your drive, e.g., /dev/sda1

# Create mount point (already exists if installed)
sudo mkdir -p /mnt/recordings

# Mount drive
sudo mount /dev/sda1 /mnt/recordings

# Set ownership
sudo chown -R $USER:$USER /mnt/recordings
```

#### Option 2: Auto-mount at Boot

```bash
# Get drive UUID
sudo blkid /dev/sda1
# Copy the UUID value

# Edit fstab
sudo nano /etc/fstab

# Add line (replace UUID with your drive's UUID):
UUID=your-uuid-here /mnt/recordings ext4 defaults 0 2

# Save and test
sudo mount -a
```

### Storage Performance

For optimal recording:
- **Minimum write speed:** 30 MB/s
- **Recommended:** USB 3.0+ SSD or HDD
- Avoid slow USB 2.0 drives or old SD cards

Test write speed:
```bash
dd if=/dev/zero of=/mnt/recordings/test.tmp bs=1M count=1024 conv=fdatasync
rm /mnt/recordings/test.tmp
```

---

## Network Configuration

### Ethernet Setup (Recommended)

1. **Connect Ethernet cable**

2. **Verify connection:**
   ```bash
   ip addr show eth0
   # or
   ifconfig eth0
   ```

3. **Find IP address:**
   ```bash
   hostname -I
   ```

### WiFi Setup

If using WiFi:

```bash
# List available networks
nmcli device wifi list

# Connect to network
nmcli device wifi connect "SSID" password "PASSWORD"

# Verify connection
nmcli connection show
```

### Static IP (Optional)

For consistent access, configure static IP:

```bash
# Example for Ethernet
sudo nmcli connection modify "Wired connection 1" \
  ipv4.addresses 192.168.1.100/24 \
  ipv4.gateway 192.168.1.1 \
  ipv4.dns "8.8.8.8 8.8.4.4" \
  ipv4.method manual

# Restart connection
sudo nmcli connection down "Wired connection 1"
sudo nmcli connection up "Wired connection 1"
```

### Remote Access

For remote access to web UI:

1. **Find Jetson IP:**
   ```bash
   hostname -I
   ```

2. **Access from another device on same network:**
   ```
   http://<jetson-ip>
   ```

3. **For internet access (advanced):**
   - Configure port forwarding on router
   - Set up dynamic DNS
   - Consider VPN for security

---

## Power Management

### Power Requirements

- **Idle:** ~5-7W
- **Preview streaming:** ~10-15W
- **Recording (both cameras):** ~15-20W
- **Peak:** ~25W

### Power Supply Best Practices

1. **Use quality power adapter:**
   - Official NVIDIA adapter recommended
   - Minimum: 5V/4A (20W)
   - Avoid cheap adapters that can't deliver rated power

2. **Check power throttling:**
   ```bash
   # Monitor power consumption
   tegrastats
   ```

3. **Avoid brownouts:**
   - Symptoms: Random crashes, camera initialization failures
   - Solution: Use higher quality power supply

### Battery Backup (Optional)

For critical recordings, consider UPS:
- USB-C power bank with PD (Power Delivery)
- Minimum capacity: 10,000 mAh for ~2 hours runtime
- Ensure output is 5V/3A minimum

---

## Hardware Troubleshooting

### Camera Not Detected

**Symptoms:**
- `ls /dev/video*` shows no devices
- API logs show "Failed to open camera"

**Solutions:**

1. **Check physical connections:**
   ```bash
   sudo shutdown -h now
   # Reseat camera cables
   # Power back on
   ```

2. **Restart camera daemon:**
   ```bash
   sudo systemctl restart nvargus-daemon
   ```

3. **Check camera detection:**
   ```bash
   # Verify cameras are enumerated
   v4l2-ctl --list-devices
   ```

4. **Power cycle Jetson:**
   ```bash
   sudo reboot
   ```

### Camera Initialization Failures

**Symptoms:**
- "Failed to create CaptureSession" errors in logs
- Cameras detected but won't start

**Solutions:**

1. **Restart nvargus-daemon:**
   ```bash
   sudo systemctl restart nvargus-daemon
   sudo systemctl restart footballvision-api-enhanced
   ```

2. **Check for multiple processes accessing cameras:**
   ```bash
   sudo lsof /dev/video*
   ```

3. **Verify power supply is adequate**

### Performance Issues

**Symptoms:**
- Low framerate (<20fps) during recording
- Stuttering video
- System lag

**Solutions:**

1. **Set maximum performance mode:**
   ```bash
   sudo nvpmodel -m 0
   sudo jetson_clocks
   ```

2. **Check thermal throttling:**
   ```bash
   cat /sys/devices/virtual/thermal/thermal_zone*/temp
   ```
   If >80°C, improve cooling

3. **Verify disk write speed:**
   ```bash
   dd if=/dev/zero of=/mnt/recordings/test.tmp bs=1M count=1024 conv=fdatasync
   ```
   Should be >30MB/s

4. **Check CPU usage:**
   ```bash
   top
   ```
   During recording: 250-350% CPU usage is normal

### Random Crashes

**Common causes:**

1. **Insufficient power:**
   - Use better quality power adapter
   - Check for voltage drops

2. **Overheating:**
   - Add cooling solution
   - Monitor with `tegrastats`

3. **Corrupted filesystem:**
   ```bash
   sudo fsck /dev/mmcblk0p1
   ```

4. **Software issues:**
   - Check logs: `journalctl -u footballvision-api-enhanced`
   - Restart services

### Storage Issues

**Symptoms:**
- "No space left on device" errors
- Recording fails to start

**Solutions:**

1. **Check disk space:**
   ```bash
   df -h /mnt/recordings
   ```

2. **Clean old recordings:**
   ```bash
   # Delete old test recordings
   rm -rf /mnt/recordings/test_*
   ```

3. **Check write permissions:**
   ```bash
   ls -la /mnt/recordings
   # Should be owned by your user
   ```

---

## Hardware Maintenance

### Regular Maintenance

**Weekly:**
- Check camera connections are secure
- Clean camera lenses if dusty
- Verify adequate free storage space

**Monthly:**
- Clean dust from Jetson cooling fins
- Check for system updates: `sudo apt update && sudo apt upgrade`
- Test recording functionality

**As Needed:**
- Replace thermal paste if temperatures increasing
- Update JetPack if major release available
- Backup recordings to external storage

---

## Additional Resources

- **NVIDIA Jetson Documentation:** https://developer.nvidia.com/embedded/jetson-orin-nano-developer-kit
- **JetPack Documentation:** https://docs.nvidia.com/jetson/jetpack/
- **FootballVision Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Deployment Guide:** [../deploy/README.md](../deploy/README.md)

---

**Version:** 3.0
**Last Updated:** 2025-10-24

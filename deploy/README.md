# FootballVision Pro v3 - Deployment Guide

Complete deployment guide for installing FootballVision Pro v3 on NVIDIA Jetson Orin Nano devices with JetPack 6.1+.

## Table of Contents

- [Quick Start](#quick-start)
- [Safe Updates](#safe-updates)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Validation](#validation)
- [Post-Installation](#post-installation)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

---

## Quick Start

**For experienced users on a fresh Jetson Orin Nano:**

```bash
# Clone repository
git clone https://github.com/Wandeon/metcam.git
cd metcam

# Run complete installation (takes ~10 minutes)
chmod +x deploy/install-complete.sh
./deploy/install-complete.sh

# After installation completes:
# 1. Log out and back in (if added to video group)
# 2. Restart camera daemon: sudo systemctl restart nvargus-daemon
# 3. Access UI at http://<your-jetson-ip>
```

---

## Safe Updates

For repeatable production updates on an already installed device, use:

```bash
cd /home/mislav/footballvision-pro
./deploy/deploy-safe.sh
```

What `deploy-safe.sh` does:

1. Preserves local `config/camera_config.json`
2. Fast-forwards `main` from `origin`
3. Re-deploys systemd + Caddy configs
4. Builds and deploys the web dashboard when frontend files changed (or when forced)
5. Restarts API and verifies `/api/v1/health`
6. Runs recording smoke test (start/wait/stop + integrity/transport checks)
7. Rolls back to pre-deploy commit automatically on failure

Useful flags:

- `--no-smoke` (skip recording smoke)
- `--smoke-duration <seconds>`
- `--skip-caddy`
- `--skip-systemd`
- `--skip-frontend`
- `--force-frontend`

---

## Prerequisites

### Hardware Requirements

- **NVIDIA Jetson Orin Nano** (8GB recommended)
- **2x IMX477 cameras** connected via CSI ports
- **32GB+ microSD card** or NVMe SSD
- **Network connection** for installation

### Software Requirements

- **JetPack 6.1+** installed and running
- **Ubuntu 22.04** (comes with JetPack)
- **Internet connection** during installation
- **sudo access**

### Pre-Installation Checks

Verify your hardware before starting:

```bash
# Check JetPack version
dpkg -l | grep nvidia-jetpack

# Check cameras are detected
ls -la /dev/video*
# Should show at least 2 video devices

# Check available disk space (need at least 10GB)
df -h /

# Verify you have sudo access
sudo whoami
```

---

## Installation

### Method 1: Automated Installation (Recommended)

The complete installation script handles everything automatically:

```bash
# Navigate to repository
cd metcam

# Run installation
./deploy/install-complete.sh
```

**What the script does:**

1. ✅ Verifies hardware and JetPack version
2. ✅ Installs all system dependencies (GStreamer, Python, etc.)
3. ✅ Installs Caddy web server
4. ✅ Installs Node.js 20+ if needed
5. ✅ Installs Python dependencies
6. ✅ Creates required directories with correct permissions
7. ✅ Adds user to video group for camera access
8. ✅ Builds and deploys web dashboard
9. ✅ Configures and starts Caddy web server
10. ✅ Installs and starts API service

**Installation time:** Approximately 10-15 minutes depending on network speed.

### Method 2: Manual Installation

If you prefer manual control, see [MANUAL_INSTALL.md](MANUAL_INSTALL.md) for step-by-step instructions.

---

## Validation

After installation, validate your system:

### 1. System Validation

Run the comprehensive validation script:

```bash
./deploy/validate.sh
```

This checks:
- Hardware detection
- Required directories and permissions
- System packages and Python dependencies
- Camera availability
- Services (API, Caddy, nvargus-daemon)
- API endpoints
- GStreamer plugins
- Web UI deployment

**Expected output:** All checks should pass (green ✓). Warnings are acceptable, failures must be addressed.

### 2. Quick Functionality Test

Test preview and recording functionality:

```bash
./deploy/quick-test.sh
```

This performs:
- API status check
- Pipeline state verification
- Preview start/stop test
- HLS segment generation verification
- Recording start/stop test
- Mutual exclusion verification (recording blocks preview)

**Expected output:** All tests should pass. Small test recordings will be created in `/mnt/recordings/`.

### 3. Performance Test

Validate system performance:

```bash
./deploy/performance-test.sh
```

This measures:
- HLS segment generation rate
- CPU usage during preview and recording
- Recording framerate analysis
- System resource availability

**Expected results:**
- Preview: 30fps for both cameras
- Recording: 25-30fps for both cameras at 12Mbps
- CPU usage: 250-350% during recording (2-3 cores)

---

## Post-Installation

### Required Steps

1. **Log out and back in** (if you were added to the video group)
   ```bash
   # Check if you're in video group
   groups | grep video

   # If not, log out and back in
   exit
   ```

2. **Restart camera daemon**
   ```bash
   sudo systemctl restart nvargus-daemon
   ```

3. **Verify services are running**
   ```bash
   sudo systemctl status footballvision-api-enhanced
   sudo systemctl status caddy
   ```

### Access the System

1. **Find your Jetson's IP address**
   ```bash
   hostname -I
   ```

2. **Open web UI in browser**
   ```
   http://<your-jetson-ip>
   ```

3. **Test preview stream**
   - Click "Start Preview" in the web UI
   - You should see live video from both cameras
   - Click "Stop Preview" when done

4. **Test recording**
   - Preview MUST be stopped before recording
   - Click "Start Recording"
   - Enter match details
   - Recording files will be saved to `/mnt/recordings/<match_id>/`

### Useful Commands

```bash
# View API logs (real-time)
journalctl -u footballvision-api-enhanced -f

# View Caddy logs
journalctl -u caddy -f

# Check pipeline state
curl http://localhost:8000/api/v1/pipeline-state

# Check system status
curl http://localhost:8000/api/v1/status

# Restart API service
sudo systemctl restart footballvision-api-enhanced

# Restart Caddy
sudo systemctl restart caddy

# List recordings
ls -lh /mnt/recordings/
```

---

## Troubleshooting

### Common Issues

#### 1. "Failed to create CaptureSession" errors

**Cause:** Camera daemon (nvargus-daemon) in bad state

**Solution:**
```bash
sudo systemctl restart nvargus-daemon
sudo systemctl restart footballvision-api-enhanced
```

#### 2. Web UI shows 502 Bad Gateway

**Cause:** API service not running or crashed

**Solution:**
```bash
# Check service status
sudo systemctl status footballvision-api-enhanced

# View recent logs
journalctl -u footballvision-api-enhanced -n 50

# Restart service
sudo systemctl restart footballvision-api-enhanced
```

#### 3. Cameras not detected

**Cause:** User not in video group or cameras not connected properly

**Solution:**
```bash
# Check cameras
ls -la /dev/video*

# Add to video group if needed
sudo usermod -aG video $USER
# Then log out and back in

# Check physical connections
# Cameras should be firmly connected to CSI ports
```

#### 4. Preview/Recording won't start

**Cause:** Pipeline locked by previous operation

**Solution:**
```bash
# Check pipeline state
curl http://localhost:8000/api/v1/pipeline-state

# If stuck, restart API service
sudo systemctl restart footballvision-api-enhanced
```

#### 5. Low framerate during recording

**Cause:** CPU overwhelmed or both preview and recording running

**Solution:**
- Ensure preview is stopped before starting recording
- Check CPU usage: `top` or `htop`
- Expected CPU usage during recording: 250-350%
- If using barrel correction, disable it for better performance

### Getting Help

1. **Check logs:**
   ```bash
   journalctl -u footballvision-api-enhanced -n 100
   ```

2. **Run validation:**
   ```bash
   ./deploy/validate.sh
   ```

3. **Review documentation:**
   - [TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)
   - [HARDWARE_SETUP.md](../docs/HARDWARE_SETUP.md)

---

## Uninstallation

To remove FootballVision Pro:

```bash
# Stop and disable services
sudo systemctl stop footballvision-api-enhanced
sudo systemctl disable footballvision-api-enhanced
sudo systemctl stop caddy
sudo systemctl disable caddy

# Remove service files
sudo rm /etc/systemd/system/footballvision-api-enhanced.service
sudo systemctl daemon-reload

# Remove Caddy (optional - may be used by other services)
# sudo apt remove caddy

# Remove application directories
sudo rm -rf /var/log/footballvision
sudo rm -rf /var/www/footballvision
sudo rm -rf /var/lock/footballvision

# OPTIONAL: Remove recordings (WARNING: This deletes all recordings!)
# sudo rm -rf /mnt/recordings

# Remove HLS temporary files
sudo rm -rf /dev/shm/hls

# Remove Python dependencies (optional)
# pip3 uninstall -r requirements.txt -y
```

---

## Additional Resources

- **Main README:** [../README.md](../README.md)
- **Hardware Setup:** [../docs/HARDWARE_SETUP.md](../docs/HARDWARE_SETUP.md)
- **Troubleshooting:** [../docs/TROUBLESHOOTING.md](../docs/TROUBLESHOOTING.md)
- **API Documentation:** [../docs/API.md](../docs/API.md)
- **Architecture:** [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)

---

## Support

For issues, questions, or contributions:
- **Issues:** https://github.com/Wandeon/metcam/issues
- **Documentation:** https://github.com/Wandeon/metcam/tree/main/docs

---

**Version:** 3.0
**Last Updated:** 2025-10-24
**Compatibility:** NVIDIA Jetson Orin Nano with JetPack 6.1+

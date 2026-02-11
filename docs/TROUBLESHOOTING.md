# FootballVision Pro v3 - Troubleshooting Guide

Comprehensive troubleshooting guide for common issues and their solutions.

---

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Installation Issues](#installation-issues)
- [Camera Issues](#camera-issues)
- [Streaming and Recording Issues](#streaming-and-recording-issues)
- [Web UI Issues](#web-ui-issues)
- [Performance Issues](#performance-issues)
- [Service Issues](#service-issues)
- [Network Issues](#network-issues)
- [Advanced Debugging](#advanced-debugging)

---

## Quick Diagnostics

When encountering any issue, start here:

### 1. Run Validation Script

```bash
cd /home/mislav/footballvision-pro
./deploy/validate.sh
```

This will check all system components and highlight specific failures.

### 2. Check Service Status

```bash
# API service
sudo systemctl status footballvision-api-enhanced

# Web server
sudo systemctl status caddy

# Camera daemon
sudo systemctl status nvargus-daemon
```

### 3. View Recent Logs

```bash
# API logs (last 50 lines)
journalctl -u footballvision-api-enhanced -n 50

# API logs (follow in real-time)
journalctl -u footballvision-api-enhanced -f
```

### 4. Check Pipeline State

```bash
curl http://localhost:8000/api/v1/pipeline-state
```

---

## Installation Issues

### Issue: Installation Script Fails

**Symptom:** `install-complete.sh` exits with errors

**Common causes:**

1. **Network connectivity issues**
   ```bash
   # Test connectivity
   ping -c 3 google.com

   # If fails, check network:
   ip addr show
   nmcli device status
   ```

2. **Insufficient permissions**
   ```bash
   # Ensure not running as root
   whoami  # Should NOT be root

   # Verify sudo works
   sudo whoami  # Should print "root"
   ```

3. **Insufficient disk space**
   ```bash
   df -h /
   # Need at least 10GB free
   ```

**Solution:**
- Address the specific error shown in script output
- Re-run script after fixing underlying issue
- Script is idempotent (safe to run multiple times)

### Issue: Node.js Installation Fails

**Symptom:** Node.js version check fails or npm not found

**Solution:**
```bash
# Manual Node.js installation
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Verify
node -v  # Should show v20.x.x
npm -v
```

### Issue: Python Dependencies Fail to Install

**Symptom:** `pip3 install -r requirements.txt` fails

**Common causes:**

1. **Missing build dependencies**
   ```bash
   sudo apt install -y python3-dev python3-pip build-essential
   ```

2. **PyGObject missing**
   ```bash
   # Install system package (NOT via pip)
   sudo apt install -y python3-gi gir1.2-gstreamer-1.0
   ```

3. **Pip version too old**
   ```bash
   pip3 install --upgrade pip
   ```

---

## Camera Issues

### Issue: Cameras Not Detected

**Symptom:** `ls /dev/video*` shows no devices

**Diagnostic steps:**

1. **Check physical connections**
   ```bash
   # Power off completely
   sudo shutdown -h now

   # Reseat both camera ribbon cables
   # Ensure contacts face correct direction
   # Latches fully closed

   # Power back on
   ```

2. **Verify cameras are enumerated**
   ```bash
   v4l2-ctl --list-devices
   ```

3. **Check camera daemon**
   ```bash
   sudo systemctl status nvargus-daemon

   # If not running:
   sudo systemctl restart nvargus-daemon
   ```

4. **Check kernel logs**
   ```bash
   sudo dmesg | grep -i camera
   sudo dmesg | grep -i vi5
   ```

**Solutions:**

- **Physical:** Reseat camera cables
- **Software:** Restart nvargus-daemon
- **Power:** Ensure adequate power supply (5V/4A minimum)
- **Last resort:** Full reboot

### Issue: "Failed to create CaptureSession"

**Symptom:** API logs show camera initialization errors

**Most common solution:**
```bash
sudo systemctl restart nvargus-daemon
sudo systemctl restart footballvision-api-enhanced
```

**If problem persists:**

1. **Check for stale processes**
   ```bash
   # List processes using cameras
   sudo lsof /dev/video*

   # Kill stale processes if any
   sudo kill -9 <PID>
   ```

2. **Full camera reset**
   ```bash
   sudo systemctl stop footballvision-api-enhanced
   sudo systemctl restart nvargus-daemon
   sleep 3
   sudo systemctl start footballvision-api-enhanced
   ```

3. **Power cycle Jetson**
   ```bash
   sudo reboot
   ```

### Issue: User Permission Denied for Cameras

**Symptom:** "Permission denied" when accessing /dev/video*

**Solution:**
```bash
# Check if in video group
groups | grep video

# If not, add user to video group
sudo usermod -aG video $USER

# MUST log out and back in for change to take effect
exit
# (Then log back in)

# Verify
groups | grep video
ls -la /dev/video0
```

### Issue: Only One Camera Detected

**Symptom:** Only one /dev/video* device appears

**Diagnostic:**
```bash
# Check both CSI ports
v4l2-ctl --list-devices

# Expected: Two camera entries
```

**Solutions:**

1. **Check second camera connection**
   - Power off
   - Reseat second camera cable
   - Verify latch is closed

2. **Try cameras individually**
   - Test CAM0 port alone
   - Test CAM1 port alone
   - Helps identify faulty camera vs. port

3. **Check for hardware damage**
   - Inspect ribbon cables for tears
   - Check CSI connectors for bent pins

---

## Streaming and Recording Issues

### Issue: Preview Won't Start

**Symptom:** "Start Preview" button fails, no HLS stream

**Diagnostic:**
```bash
# Check pipeline state
curl http://localhost:8000/api/v1/pipeline-state

# Check API logs
journalctl -u footballvision-api-enhanced -n 50
```

**Solutions:**

1. **Pipeline locked by previous operation**
   ```bash
   # Stop preview
   curl -X DELETE http://localhost:8000/api/v1/preview

   # Stop recording
   curl -X DELETE "http://localhost:8000/api/v1/recording?force=true"

   # Check state again
   curl http://localhost:8000/api/v1/pipeline-state
   ```

2. **Force release lock**
   ```bash
   sudo rm /var/lock/footballvision/pipeline_state.json
   sudo systemctl restart footballvision-api-enhanced
   ```

3. **Camera initialization failed**
   - See [Camera Issues](#issue-failed-to-create-capturesession)

### Issue: Recording Won't Start

**Symptom:** "Start Recording" fails or returns error

**Most common cause:** Preview is still running

**Solution:**
```bash
# Stop preview first
curl -X DELETE http://localhost:8000/api/v1/preview

# Wait 2 seconds
sleep 2

# Try recording again
```

**Other causes:**

1. **Disk space full**
   ```bash
   df -h /mnt/recordings
   # If <1GB free, clean up old recordings
   ```

2. **Directory permissions**
   ```bash
   ls -la /mnt/recordings
   # Should be writable by your user

   # Fix if needed:
   sudo chown -R $USER:$USER /mnt/recordings
   ```

3. **Pipeline mutex**
   - See preview won't start solutions above

### Issue: HLS Segments Not Generating

**Symptom:** Preview starts but no .m3u8 or .ts files in /dev/shm/hls/

**Diagnostic:**
```bash
# Check directory exists
ls -la /dev/shm/hls/

# Monitor in real-time
watch -n 1 ls -lh /dev/shm/hls/

# Check API logs for GStreamer errors
journalctl -u footballvision-api-enhanced -f
```

**Solutions:**

1. **Directory permissions**
   ```bash
   sudo rm -rf /dev/shm/hls
   sudo mkdir -p /dev/shm/hls
   sudo chown -R $USER:$USER /dev/shm/hls
   sudo systemctl restart footballvision-api-enhanced
   ```

2. **GStreamer pipeline error**
   - Check API logs for specific error
   - May need to restart nvargus-daemon

### Issue: Recording Files Empty or Corrupted

**Symptom:** .mp4 files exist but won't play or are 0 bytes

**Diagnostic:**
```bash
# Check file size
ls -lh /mnt/recordings/<match_id>/

# Try to get info
ffprobe /mnt/recordings/<match_id>/cam1_*.mp4
```

**Common causes:**

1. **Recording stopped prematurely**
   - Check API logs for crash
   - Ensure recording ran for intended duration

2. **Disk write errors**
   ```bash
   # Check disk health
   sudo dmesg | grep -i "error\|fail" | grep -i mmc

   # Test write speed
   dd if=/dev/zero of=/mnt/recordings/test.tmp bs=1M count=1024 conv=fdatasync
   rm /mnt/recordings/test.tmp
   # Should be >30MB/s
   ```

3. **Pipeline crash during recording**
   - Check for segfaults in logs
   - May need to restart nvargus-daemon

---

## Web UI Issues

### Issue: 502 Bad Gateway

**Symptom:** Web UI shows "502 Bad Gateway" error

**Cause:** API service not running or crashed

**Solution:**
```bash
# Check API service
sudo systemctl status footballvision-api-enhanced

# If not running:
sudo systemctl restart footballvision-api-enhanced

# Check if it stays running
sleep 5
sudo systemctl status footballvision-api-enhanced

# If keeps crashing, check logs:
journalctl -u footballvision-api-enhanced -n 100
```

### Issue: Web UI Not Loading

**Symptom:** Browser shows "Connection refused" or timeout

**Diagnostic:**
```bash
# Check Caddy is running
sudo systemctl status caddy

# Test locally
curl http://localhost/

# Check if files exist
ls -la /var/www/footballvision/
```

**Solutions:**

1. **Caddy not running**
   ```bash
   sudo systemctl restart caddy
   sudo systemctl enable caddy
   ```

2. **Firewall blocking**
   ```bash
   # Check if port 80 is accessible
   sudo netstat -tlnp | grep :80

   # If firewall is active:
   sudo ufw allow 80/tcp
   ```

3. **Wrong IP address**
   ```bash
   # Get correct IP
   hostname -I

   # Access via http://<correct-ip>
   ```

### Issue: Preview Video Not Playing in Browser

**Symptom:** UI shows preview active but video player shows error

**Diagnostic:**
```bash
# Check HLS files exist
ls -la /dev/shm/hls/

# Test HLS URL directly
curl http://localhost/hls/cam1_preview.m3u8
```

**Solutions:**

1. **HLS files not generated**
   - See [HLS Segments Not Generating](#issue-hls-segments-not-generating)

2. **Browser caching issue**
   - Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac)
   - Clear browser cache
   - Try different browser

3. **CORS issue**
   - Check browser console for errors
   - Verify Caddyfile has CORS headers:
     ```caddy
     header {
         Access-Control-Allow-Origin *
     }
     ```

---

## Performance Issues

### Issue: False Power Mode or CPU Throttling Alerts

**Symptom:** System logs show alerts like:
- "Wrong power mode: MAXN_SUPER (should be 2)"
- "CPU throttling detected: .96GHz (expected 1.728GHz)"

Even though the system is actually in the correct power mode.

**Cause:** This was a bug in the system health monitor that has been fixed. The monitor was:
1. Comparing power mode NAME (string "MAXN_SUPER") with mode NUMBER (integer 2)
2. Including efficiency cores (CPUs 4-5 at 729 MHz) in CPU frequency average

**Fixed in:** System health monitor script now correctly:
- Extracts numeric mode ID from `nvpmodel -q` output
- Only monitors performance cores (CPUs 0-3) which run at 1.728 GHz
- Reports accurate "Performance CPU throttling" alerts

**To verify fix is applied:**
```bash
# Check monitoring script has been updated
grep "tail -1" /home/mislav/footballvision-pro/scripts/system_health_monitor.sh
# Should show: local current_mode=$(nvpmodel -q | tail -1)

# Check CPU monitoring only checks cores 0-3
grep "for cpu in" /home/mislav/footballvision-pro/scripts/system_health_monitor.sh
# Should show: for cpu in 0 1 2 3; do
```

**If you still see these alerts after the fix:**
- They are now genuine warnings
- Check actual power mode: `sudo nvpmodel -q`
- Check actual CPU frequencies: `cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq`

### Issue: Power Mode Not Persisting (Jetson Orin Nano Super)

**Symptom:** After reboot, system is not in Mode 2 (MAXN_SUPER)

**Background:** Jetson Orin Nano Super has specific power modes:
- Mode 0: 15W (1497.6 MHz max CPU)
- Mode 1: 25W (1344 MHz max CPU)
- Mode 2: MAXN_SUPER (1.728 GHz max CPU, unlimited power) - **REQUIRED**
- Mode 3: 7W (960 MHz, 4 cores only)

**Solution:**

1. **Set to Mode 2:**
   ```bash
   sudo nvpmodel -m 2
   sudo jetson_clocks
   ```

2. **Make persistent across reboots:**
   ```bash
   # Check current stored mode
   cat /var/lib/nvpmodel/status
   # Should show: pmode:0002

   # If not, set it:
   sudo nvpmodel -m 2
   ```

3. **Verify it persists:**
   ```bash
   sudo reboot
   # After reboot:
   sudo nvpmodel -q
   # Should show: NV Power Mode: MAXN_SUPER
   #              2
   ```

**Automatic enforcement:** The system health monitor (`/home/mislav/footballvision-pro/scripts/system_health_monitor.sh`) runs every 5 minutes and automatically corrects the power mode if it changes. This ensures Mode 2 is maintained even if something tries to change it.

**Why Mode 2 is critical:**
- Maximizes performance cores to 1.728 GHz
- Provides ~2.01 CPU cores per camera for encoding
- No power limits, preventing thermal throttling under sustained load
- Required for reliable 30fps dual-camera recording

### Issue: Low Framerate During Recording

**Symptom:** Recording achieves <20fps instead of 25-30fps

**Diagnostic:**
```bash
# Check CPU usage
top

# During recording, API process should show 250-350% CPU

# Check thermal throttling
cat /sys/devices/virtual/thermal/thermal_zone*/temp
# Should be <85°C
```

**Solutions:**

1. **Set maximum performance mode (Mode 2 for Orin Nano Super)**
   ```bash
   sudo nvpmodel -m 2
   sudo jetson_clocks
   ```

2. **Ensure preview is stopped**
   ```bash
   curl -X DELETE http://localhost:8000/api/v1/preview
   sleep 2
   # Then start recording
   ```

3. **Disable barrel correction** (if enabled)
   - Barrel correction adds significant CPU overhead
   - Test recording without it first

4. **Check thermal throttling**
   ```bash
   # Monitor temperature
   watch -n 1 cat /sys/devices/virtual/thermal/thermal_zone*/temp

   # If >80°C:
   # - Add cooling fan
   # - Improve airflow
   # - Clean dust from heatsink
   ```

5. **Slow storage device**
   ```bash
   # Test write speed
   dd if=/dev/zero of=/mnt/recordings/test.tmp bs=1M count=1024 conv=fdatasync
   rm /mnt/recordings/test.tmp

   # Should be >30MB/s
   # If slower, use faster storage (USB 3.0 SSD)
   ```

### Issue: System Lag or Unresponsive

**Symptom:** SSH or UI becomes slow/unresponsive

**Diagnostic:**
```bash
# Check CPU
top

# Check memory
free -h

# Check swap usage
cat /proc/swaps
```

**Solutions:**

1. **Memory exhausted**
   ```bash
   # Check what's using memory
   ps aux --sort=-%mem | head -n 10

   # If API using >2GB, may have memory leak
   sudo systemctl restart footballvision-api-enhanced
   ```

2. **Too many old HLS segments**
   ```bash
   # Clean up HLS directory
   sudo rm -f /dev/shm/hls/*.ts
   ```

3. **Disk I/O bottleneck**
   ```bash
   # Check I/O wait
   top
   # Look for high %wa (wait)

   # If high, slow storage is bottleneck
   ```

### Issue: Stuttering or Dropped Frames

**Symptom:** Video playback shows stuttering or frame drops

**Cause:** CPU can't keep up with encoding or slow storage

**Solutions:**

1. **Lower bitrate**
   - Try 8Mbps instead of 12Mbps for recording
   - Try 2Mbps instead of 3Mbps for preview

2. **Ensure maximum performance mode (Mode 2 for Orin Nano Super)**
   ```bash
   sudo nvpmodel -m 2
   sudo jetson_clocks
   ```

3. **Use faster storage for recordings**
   - USB 3.0 SSD instead of HDD or SD card

---

## Service Issues

### Issue: API Service Won't Start

**Symptom:** `systemctl start footballvision-api-enhanced` fails

**Diagnostic:**
```bash
# Check status
sudo systemctl status footballvision-api-enhanced

# View logs
journalctl -u footballvision-api-enhanced -n 50

# Try manual start
cd /home/mislav/footballvision-pro
python3 -m src.platform.simple_api_v3
```

**Common causes:**

1. **Python dependencies missing**
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Cameras not available**
   - See [Camera Issues](#camera-issues)

3. **Port 8000 already in use**
   ```bash
   sudo lsof -i :8000
   # Kill process using port if needed
   ```

4. **Service file incorrect**
   ```bash
   # Check service file
   cat /etc/systemd/system/footballvision-api-enhanced.service

   # Reload if changed
   sudo systemctl daemon-reload
   ```

### Issue: API Service Keeps Crashing

**Symptom:** Service starts but crashes after a few seconds

**Diagnostic:**
```bash
# Watch logs in real-time
journalctl -u footballvision-api-enhanced -f

# Look for:
# - Segmentation fault (camera/GStreamer issue)
# - Python exceptions (code bug)
# - "Failed to create CaptureSession" (camera daemon)
```

**Solutions:**

1. **Camera daemon crash**
   ```bash
   sudo systemctl restart nvargus-daemon
   sleep 3
   sudo systemctl restart footballvision-api-enhanced
   ```

2. **Code error**
   - Check logs for Python exception traceback
   - May indicate corrupted installation

3. **Assertion failure in GStreamer**
   ```bash
   # Often fixed by restarting camera daemon
   sudo systemctl restart nvargus-daemon
   sudo systemctl restart footballvision-api-enhanced
   ```

### Issue: Caddy Service Won't Start

**Symptom:** `systemctl start caddy` fails

**Diagnostic:**
```bash
# Check status
sudo systemctl status caddy

# View logs
journalctl -u caddy -n 50

# Test config
sudo caddy validate --config /etc/caddy/Caddyfile
```

**Solutions:**

1. **Config syntax error**
   ```bash
   # Validate Caddyfile
   sudo caddy validate --config /etc/caddy/Caddyfile

   # Fix errors shown
   ```

2. **Port 80 already in use**
   ```bash
   sudo lsof -i :80

   # Stop conflicting service (e.g., apache2)
   sudo systemctl stop apache2
   ```

3. **Reinstall Caddy config**
   ```bash
   sudo cp /home/mislav/footballvision-pro/deploy/config/Caddyfile /etc/caddy/Caddyfile
   sudo systemctl restart caddy
   ```

---

## Network Issues

### Issue: Can't Access Web UI from Remote Computer

**Symptom:** Browser shows "Connection refused" from remote device

**Diagnostic:**
```bash
# On Jetson, find IP
hostname -I

# On Jetson, test locally
curl http://localhost/

# On remote computer, test connectivity
ping <jetson-ip>
```

**Solutions:**

1. **Firewall blocking**
   ```bash
   # Check if firewall is active
   sudo ufw status

   # Allow HTTP
   sudo ufw allow 80/tcp
   ```

2. **Wrong IP address**
   - Ensure using correct IP from `hostname -I`
   - If IP changed, use new IP

3. **Network segmentation**
   - Ensure remote device on same network
   - Check router settings for client isolation

### Issue: Slow HLS Streaming

**Symptom:** Preview video loads slowly or buffers frequently

**Causes:**

1. **Normal HLS latency**
   - HLS has 5-8 second inherent latency
   - This is expected behavior

2. **Network congestion**
   - Use Ethernet instead of WiFi if possible
   - Ensure good signal strength if using WiFi

3. **CPU overwhelmed**
   - Check CPU usage during preview
   - May need to lower bitrate

---

## Advanced Debugging

### Enable Debug Logging

For deeper investigation:

```bash
# Edit service file
sudo systemctl edit footballvision-api-enhanced

# Add:
[Service]
Environment="GST_DEBUG=3"

# Save and restart
sudo systemctl daemon-reload
sudo systemctl restart footballvision-api-enhanced

# View detailed GStreamer logs
journalctl -u footballvision-api-enhanced -f
```

**GST_DEBUG levels:**
- 0: None
- 1: ERROR
- 2: WARNING
- 3: INFO (recommended for debugging)
- 4: DEBUG
- 5: LOG (very verbose)

### Analyze GStreamer Pipeline

```bash
# Test camera manually with GStreamer
gst-launch-1.0 nvv4l2camerasrc device=/dev/video0 ! 'video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1' ! nvvidconv ! 'video/x-raw,format=I420' ! fakesink

# If this fails, camera/GStreamer issue, not application
```

### Check System Resources

```bash
# Real-time system stats (NVIDIA-specific)
tegrastats

# Monitor disk I/O
sudo iotop

# Monitor GPU (if nvtop installed)
nvtop

# Check for OOM (out of memory) kills
sudo dmesg | grep -i "out of memory"
```

### Core Dumps

If API crashes with segfault:

```bash
# Enable core dumps
ulimit -c unlimited

# Set core dump location
echo '/tmp/core.%e.%p' | sudo tee /proc/sys/kernel/core_pattern

# After crash, analyze with gdb
gdb python3 /tmp/core.*
# Type "bt" for backtrace
```

### Reset to Clean State

If all else fails:

```bash
# Stop all services
sudo systemctl stop footballvision-api-enhanced caddy

# Clean all temporary files
sudo rm -rf /dev/shm/hls/*
sudo rm -f /var/lock/footballvision/pipeline_state.json

# Restart camera daemon
sudo systemctl restart nvargus-daemon
sleep 3

# Restart services
sudo systemctl start footballvision-api-enhanced caddy

# Verify
sudo systemctl status footballvision-api-enhanced caddy
```

---

## Getting More Help

If issues persist:

1. **Gather diagnostic information:**
   ```bash
   # Run validation
   ./deploy/validate.sh > validation.log 2>&1

   # Collect logs
   journalctl -u footballvision-api-enhanced -n 200 > api.log
   journalctl -u caddy -n 100 > caddy.log
   journalctl -u nvargus-daemon -n 100 > nvargus.log

   # System info
   uname -a > sysinfo.txt
   dpkg -l | grep nvidia >> sysinfo.txt
   ```

2. **Check documentation:**
   - [Hardware Setup](HARDWARE_SETUP.md)
   - [Deployment Guide](../deploy/README.md)
   - [Architecture](ARCHITECTURE.md)

3. **File an issue:**
   - Include validation.log, api.log, and sysinfo.txt
   - Describe what you were doing when the issue occurred
   - Include steps to reproduce

---

**Version:** 3.0
**Last Updated:** 2025-10-24

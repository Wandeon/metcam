# FootballVision Pro v3 - Post-Installation Checklist

Use this checklist to verify your installation is complete and functioning correctly.

---

## 📋 Installation Completion

### Step 1: Installation Script
- [ ] Ran `./deploy/install-complete.sh` successfully
- [ ] Script completed without fatal errors
- [ ] All 10 installation steps passed

### Step 2: User Permissions
- [ ] Added to video group (check with `groups | grep video`)
- [ ] Logged out and back in (required for group changes to take effect)

### Step 3: Services Running
- [ ] API service is active: `sudo systemctl status footballvision-api-enhanced`
- [ ] Caddy service is active: `sudo systemctl status caddy`
- [ ] nvargus-daemon is active: `sudo systemctl status nvargus-daemon`

---

## ✅ System Validation

### Run Validation Script
```bash
./deploy/validate.sh
```

Check that all items pass:
- [ ] Hardware detection (Jetson device verified)
- [ ] Required directories exist and are writable
- [ ] System packages installed (python3-gi, GStreamer, Caddy, etc.)
- [ ] Python dependencies available (fastapi, uvicorn, pydantic, etc.)
- [ ] Cameras detected (at least 2 /dev/video* devices)
- [ ] User is in video group
- [ ] nvargus-daemon is running
- [ ] API service is running and enabled
- [ ] Caddy web server is running and enabled
- [ ] API endpoints responding
- [ ] Web UI files deployed
- [ ] Web UI accessible via Caddy
- [ ] GStreamer plugins available (nvv4l2camerasrc, nvvidconv, x264enc, splitmuxsink)
- [ ] Node.js 20+ installed

---

## 🧪 Functionality Testing

### Run Quick Test
```bash
./deploy/quick-test.sh
```

Verify all tests pass:
- [ ] API status endpoint responding
- [ ] Pipeline state is idle
- [ ] Preview starts successfully
- [ ] HLS segments generate in /dev/shm/hls/
- [ ] Preview stops successfully
- [ ] Pipeline returns to idle after preview
- [ ] Recording starts successfully
- [ ] Recording files created in /mnt/recordings/
- [ ] Pipeline returns to idle after recording
- [ ] Mutual exclusion works (preview blocked during recording)

---

## 🚀 Performance Validation

### Run Performance Test (Optional but Recommended)
```bash
./deploy/performance-test.sh
```

Check performance metrics:
- [ ] Preview generates HLS segments at expected rate (~5 segments in 10 seconds)
- [ ] CPU usage is reasonable during preview (<150%)
- [ ] Recording completes successfully at 12Mbps
- [ ] Recording achieves 25-30fps (check ffprobe analysis)
- [ ] System is not using swap during operation
- [ ] Sufficient disk space available for recordings

---

## 🌐 Web UI Access

### Browser Access
- [ ] Found Jetson IP address: `hostname -I`
- [ ] Web UI loads in browser at `http://<jetson-ip>`
- [ ] Dashboard displays correctly
- [ ] Camera 1 and Camera 2 sections visible
- [ ] Control buttons functional (Start Preview, etc.)

### Preview Functionality
- [ ] Click "Start Preview" button
- [ ] Wait 5-10 seconds for stream to start
- [ ] HLS preview player loads and shows video
- [ ] Both camera streams are visible
- [ ] Click "Stop Preview" button
- [ ] Streams stop cleanly

### Recording Functionality
- [ ] Ensure preview is stopped
- [ ] Click "Start Recording" button
- [ ] Enter match details (match ID, duration, etc.)
- [ ] Recording starts (status indicator shows recording)
- [ ] Let recording run for at least 10 seconds
- [ ] Click "Stop Recording" or let it complete
- [ ] Recording files appear in /mnt/recordings/

---

## 📁 Directory Structure

### Verify Directory Permissions
```bash
ls -la /var/log/footballvision
ls -la /var/www/footballvision
ls -la /mnt/recordings
ls -la /var/lock/footballvision
ls -la /dev/shm/hls
```

Check:
- [ ] /var/log/footballvision/ owned by your user
- [ ] /var/www/footballvision/ contains index.html and assets/
- [ ] /mnt/recordings/ is writable by your user
- [ ] /var/lock/footballvision/ has 777 permissions
- [ ] /dev/shm/hls/ exists (may be empty when idle)

---

## 🔧 Configuration Files

### Verify Configurations
```bash
cat /etc/systemd/system/footballvision-api-enhanced.service
cat /etc/caddy/Caddyfile
```

Check:
- [ ] Service file points to correct repository path
- [ ] Service file runs as correct user
- [ ] Caddyfile routes are configured correctly
- [ ] Caddyfile serves HLS from /dev/shm
- [ ] Caddyfile proxies /api/* to localhost:8000

---

## 📊 Monitoring and Logs

### API Logs
```bash
journalctl -u footballvision-api-enhanced -f
```

Verify:
- [ ] No continuous error messages
- [ ] API starts up cleanly
- [ ] GStreamer pipelines initialize correctly

### Caddy Logs
```bash
journalctl -u caddy -f
```

Verify:
- [ ] Caddy serves static files correctly
- [ ] No 502/503 errors when accessing /api/*
- [ ] HLS requests are served from /dev/shm

---

## 🎯 Final Verification

### End-to-End Test
- [ ] Start with system fully idle
- [ ] Start preview from web UI
- [ ] Verify both cameras show live video
- [ ] Stop preview from web UI
- [ ] Start a 30-second test recording from web UI
- [ ] Wait for recording to complete
- [ ] Download recording files from /mnt/recordings/
- [ ] Play recording files in VLC or similar player
- [ ] Verify video quality is acceptable
- [ ] Verify both cameras recorded correctly
- [ ] Verify framerate is smooth (no major stuttering)

---

## 🔗 WebRTC Relay Verification (go2rtc)

If the system is configured for remote access via VPS-02 reverse proxy:

### Jetson Configuration
- [ ] GstRtspServer packages installed: `dpkg -l | grep gstrtspserver`
- [ ] Systemd override exists: `cat /etc/systemd/system/footballvision-api-enhanced.service.d/webrtc-turn.conf`
- [ ] `WEBRTC_RELAY_URL` set to `wss://vid.nk-otok.hr/go2rtc`
- [ ] `RTSP_BIND_ADDRESS` set to Tailscale IP (`100.78.19.7`)
- [ ] `RTSP_PORT` set to `8554`
- [ ] API status shows relay block: `curl http://localhost:8000/api/v1/preview | python3 -m json.tool`

### VPS-02 Configuration
- [ ] go2rtc container running: `docker ps | grep go2rtc`
- [ ] go2rtc config has cam0/cam1 RTSP streams: `cat /root/go2rtc/go2rtc.yaml`
- [ ] go2rtc API reachable: `curl http://127.0.0.1:1984/api/streams`
- [ ] Caddy routes configured for `/go2rtc/api/ws*` and `/go2rtc/api/webrtc*`

### End-to-End Relay Test
- [ ] Start preview on Jetson
- [ ] Open `https://vid.nk-otok.hr` in browser
- [ ] WebRTC preview shows live video (both cameras)
- [ ] Stop preview — streams stop cleanly
- [ ] Browser DevTools Network tab shows WebSocket to `/go2rtc/api/ws?src=cam0`

---

## 📝 Known Limitations

Be aware of these current system characteristics:

- [ ] Understand: Preview and recording are mutually exclusive (by design)
- [ ] Understand: Recording framerate may be 17-30fps depending on CPU load
- [ ] Understand: Both cameras must be connected before starting API service
- [ ] Understand: nvargus-daemon occasionally needs restart after crashes
- [ ] Understand: HLS preview has ~5-8 second latency (normal for HLS)
- [ ] Understand: WebRTC preview through VPS requires go2rtc relay (GStreamer 1.20 webrtcbin DTLS bug)

---

## ✨ Optional Enhancements

### Power Mode (Optional)
For maximum performance, set Jetson to high-power mode:
```bash
sudo nvpmodel -m 0  # Maximum performance mode
sudo jetson_clocks   # Lock clocks to maximum
```

Verify:
- [ ] Power mode set to maximum (if desired)

### Storage (Optional)
For long recordings, consider adding external storage:
```bash
# Example: Mount external drive to /mnt/recordings
# (Adjust device path as needed)
sudo mount /dev/sda1 /mnt/recordings
```

Verify:
- [ ] External storage mounted (if used)
- [ ] Sufficient space for planned recording duration

### Monitoring (Optional)
Install monitoring tools if desired:
```bash
sudo apt install htop iotop nvtop
```

---

## 🐛 Troubleshooting Reference

If any item fails, refer to:
- **Validation script output:** `./deploy/validate.sh`
- **Troubleshooting guide:** `docs/TROUBLESHOOTING.md`
- **API logs:** `journalctl -u footballvision-api-enhanced -n 100`
- **Hardware guide:** `docs/HARDWARE_SETUP.md`

Common fixes:
```bash
# Restart camera daemon
sudo systemctl restart nvargus-daemon

# Restart API service
sudo systemctl restart footballvision-api-enhanced

# Check pipeline state
curl http://localhost:8000/api/v1/pipeline-state

# Force release pipeline lock
# (Delete lock file and restart service)
sudo rm /var/lock/footballvision/pipeline_state.json
sudo systemctl restart footballvision-api-enhanced
```

---

## ✅ Installation Complete!

Once all items above are checked:

**Congratulations! 🎉** Your FootballVision Pro v3 system is fully operational!

You can now:
- Use the web UI to preview and record matches
- Access recordings from `/mnt/recordings/`
- Download recordings via the web UI at `/recordings/`
- Monitor system performance via logs

**Next Steps:**
- Set up regular backups of `/mnt/recordings/`
- Configure network settings for remote access (optional)
- Familiarize yourself with the API (see `docs/API.md`)
- Plan your recording workflow

---

**Version:** 3.1
**Last Updated:** 2026-02-12

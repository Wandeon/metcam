# GStreamer Pipeline Troubleshooting Guide

This document provides solutions to common GStreamer errors encountered during FootballVision Pro development.

## Table of Contents
- [nvvidconv Crop Errors](#nvvidconv-crop-errors)
- [Preview Stream Issues](#preview-stream-issues)
- [Recording Failures](#recording-failures)
- [Performance Issues](#performance-issues)
- [Camera Access Errors](#camera-access-errors)

---

## nvvidconv Crop Errors

### Error: "no property 'src-crop' in element 'cropper'"

**Full Error:**
```
gstreamer_manager - ERROR - Failed to create pipeline 'preview_cam0': gst_parse_error: no property "src-crop" in element "cropper" (2)
```

**Cause:**
Using incorrect property name. The property `src-crop` does not exist on `nvvidconv`.

**Solution:**
Use individual bounding box properties:
```python
# ❌ WRONG
nvvidconv src-crop=480:272:2880:1616

# ✅ CORRECT
nvvidconv left=480 right=3360 top=272 bottom=1888
```

**Code Fix:**
In `pipeline_builders.py`, ensure coordinate conversion:
```python
left_coord = crop_left
right_coord = SENSOR_WIDTH - crop_right      # NOT crop_right!
top_coord = crop_top
bottom_coord = SENSOR_HEIGHT - crop_bottom   # NOT crop_bottom!
```

**Reference:** See [README.md](./README.md#-critical-nvvidconv-crop-coordinate-system)

---

### Error: "VIC Configuration failed image scale factor exceeds 16"

**Full Error:**
```
/dvs/git/dirty/git-master_linux/nvutils/nvbufsurftransform/nvbufsurftransform.cpp:4786: => VIC Configuration failed image scale factor exceeds 16, use GPU for Transformation
```

**Cause:**
Incorrect crop coordinates causing extreme scaling ratio. This happens when:
- Using crop pixel counts directly as coordinates
- Coordinates result in very small output (e.g., 240×136 instead of 2880×1616)

**Example of Wrong Implementation:**
```python
# ❌ WRONG - passes crop pixel counts directly
nvvidconv left=480 right=480 top=272 bottom=272
# This creates a box from (480, 272) to (480, 272) = 0×0 pixels!
```

**Solution:**
Convert crop pixel counts to bounding box coordinates:

```python
# Config says "remove 480px from left and right"
crop_left = 480
crop_right = 480

# ✅ CORRECT - convert to bounding box
left_coord = crop_left                    # Start X = 480
right_coord = SENSOR_WIDTH - crop_right   # End X = 3840 - 480 = 3360
# Output width = 3360 - 480 = 2880 pixels ✓

# If you see VIC error, verify:
assert right_coord > left_coord, "Invalid crop: right must be > left"
assert bottom_coord > top_coord, "Invalid crop: bottom must be > top"
assert (right_coord - left_coord) >= 16, "Output width too small"
assert (bottom_coord - top_coord) >= 16, "Output height too small"
```

**Verification:**
```bash
# Test the coordinates manually
gst-launch-1.0 nvarguscamerasrc sensor-id=0 num-buffers=10 ! \
  'video/x-raw(memory:NVMM),width=3840,height=2160' ! \
  nvvidconv left=480 right=3360 top=272 bottom=1888 ! \
  'video/x-raw(memory:NVMM),width=2880,height=1616' ! \
  fakesink

# Should complete without errors
```

---

### Error: Crop appears in wrong location

**Symptom:**
Preview/recording shows crop from wrong region of sensor.

**Cause:**
Confusing the coordinate system. Remember:
- `left` = **starting** X coordinate (not "pixels to remove")
- `right` = **ending** X coordinate (not "pixels to remove from right")

**Debug:**
```python
print(f"Crop box: ({left_coord}, {top_coord}) to ({right_coord}, {bottom_coord})")
print(f"Output size: {right_coord - left_coord} × {bottom_coord - top_coord}")

# Expected for default config:
# Crop box: (480, 272) to (3360, 1888)
# Output size: 2880 × 1616
```

---

## Preview Stream Issues

### Preview starts but no HLS files generated

**Symptom:**
API returns `{"success": true}` but `/dev/shm/hls/` has old files or no `.ts` segments.

**Check:**
```bash
# 1. Verify preview is actually running
curl http://localhost:8001/api/v1/preview | jq -r '.preview_active'
# Should return: true

# 2. Check for new HLS files
ls -lrt /dev/shm/hls/*.ts | tail -10
# Timestamps should be recent (within last few seconds)

# 3. Check for GStreamer errors
tail -50 /var/log/footballvision-dev/api/error.log | grep -i error
```

**Common Causes:**
1. **Pipeline crashed silently** - Check logs for GST errors
2. **Camera in use** - Another process may have locked the camera
3. **Permissions issue** - `/dev/shm/hls/` not writable

**Solutions:**
```bash
# Fix permissions
sudo chown -R mislav:mislav /dev/shm/hls/
chmod 755 /dev/shm/hls/

# Check camera availability
ls -l /dev/video*

# Kill conflicting processes
sudo killall nvargus-daemon
sudo systemctl restart nvargus-daemon
```

---

### Preview crashes API service

**Symptom:**
Service becomes unresponsive after starting preview.

**Error in logs:**
```
ERROR:../gst/multifile/gstsplitmuxsink.c:2691:check_completed_gop: assertion failed: (gop != NULL)
```

**Cause:**
This is typically a GStreamer internal error, but service should recover.

**Solution:**
```bash
# Restart the service
sudo systemctl restart footballvision-api-dev

# Check service status
systemctl status footballvision-api-dev

# Monitor for crashes
journalctl -u footballvision-api-dev -f
```

---

## Recording Failures

### Recording won't start: "Pipeline lock held"

**Error:**
```
Failed to acquire recording lock: Lock held by preview/api-preview-all
```

**Cause:**
Preview is running and has locked the cameras.

**Solution:**
```bash
# Check lock status
curl http://localhost:8001/api/v1/pipeline-state

# Stop preview first
curl -X POST http://localhost:8001/api/v1/preview/stop

# Then start recording
curl -X POST http://localhost:8001/api/v1/recording -H "Content-Type: application/json" \
  -d '{"match_id": "test_match"}'
```

**Automatic Handling:**
Recording should automatically stop preview (force=True), but check `pipeline_manager.py` logic.

---

### Segments not created in /mnt/recordings/

**Symptom:**
Recording appears to start but no MP4 files created.

**Check:**
```bash
# 1. Verify mount point
df -h /mnt/recordings
# Should show mounted filesystem

# 2. Check permissions
ls -la /mnt/recordings/
sudo chown -R mislav:mislav /mnt/recordings/

# 3. Check disk space
df -h
# Need at least several GB free

# 4. Check recording service logs
tail -100 /var/log/footballvision-dev/api/error.log | grep -i recording
```

---

## Performance Issues

### High CPU usage (>90%)

**Symptom:**
CPU at 90%+ during preview/recording.

**Check current usage:**
```bash
sudo tegrastats --interval 1000
```

**Expected values:**
```
CPU [60-70%@1344,...]  ← Should be 60-70% for dual preview
VIC 60-90%@435         ← VIC should be working
GR3D_FREQ 0%           ← GPU should be idle
```

**If CPU is >90%:**

1. **VIC not being used** - Check crop implementation
   ```python
   # Verify nvvidconv is doing crop in NVMM
   # Pipeline should show: memory:NVMM before and after crop
   ```

2. **Software fallback** - VIC failed, using CPU
   ```bash
   # Look for this in logs:
   grep -i "GPU for Transformation" /var/log/footballvision-dev/api/error.log
   ```

3. **Too many pipelines** - Check pipeline manager
   ```bash
   curl http://localhost:8001/api/v1/pipeline-state
   # Should show only recording OR preview, never both
   ```

---

### Low framerate / dropped frames

**Check:**
```bash
# Monitor pipeline with GST_DEBUG
GST_DEBUG=hlssink2:5 gst-launch-1.0 [your pipeline]

# Look for warnings about:
# - "can't keep up"
# - "dropping frame"
# - "queue overflow"
```

**Solutions:**
1. Reduce encoder bitrate in `pipeline_builders.py`
2. Increase hlssink2 buffer: `max-files=16` (from 8)
3. Check disk I/O: `iostat -x 1`

---

## Camera Access Errors

### Error: "Cannot identify device '/dev/video0'"

**Symptom:**
Pipeline fails to start with device errors.

**Check:**
```bash
# List video devices
ls -l /dev/video*

# Check nvargus daemon
sudo systemctl status nvargus-daemon

# Restart if needed
sudo systemctl restart nvargus-daemon
```

---

### Error: "Failed to create Argus Camera Provider"

**Symptom:**
Camera initialization fails.

**Solutions:**
```bash
# 1. Reboot nvargus-daemon
sudo systemctl restart nvargus-daemon

# 2. Check camera connections
# Physical inspection of CSI cables

# 3. Verify camera detection
v4l2-ctl --list-devices

# 4. Check dmesg for hardware errors
dmesg | grep -i imx274
```

---

## Debugging Tools

### Enable GStreamer Debug Logging

```bash
# Set debug level (1-5, 5 is most verbose)
export GST_DEBUG=3

# Debug specific element
export GST_DEBUG=nvvidconv:5

# Save to file
export GST_DEBUG_FILE=/tmp/gst-debug.log

# Then run your pipeline or restart service
sudo systemctl restart footballvision-api-dev
```

### Inspect Pipeline Properties

```bash
# Check nvvidconv capabilities
gst-inspect-1.0 nvvidconv

# Check all properties
gst-inspect-1.0 nvvidconv | grep -A3 "left\s*:"

# Test pipeline manually
gst-launch-1.0 -v [your pipeline here]
```

### Monitor System Resources

```bash
# Real-time system stats
sudo tegrastats --interval 1000

# Watch VIC utilization (should be 60-90%)
watch -n 1 'sudo tegrastats --interval 500 | grep VIC'

# CPU per-core usage
htop
```

---

## Quick Reference: Coordinate Conversion

```python
# Given config
config_crop = {
    "left": 480,    # pixels to remove from left
    "right": 480,   # pixels to remove from right
    "top": 272,     # pixels to remove from top
    "bottom": 272   # pixels to remove from bottom
}

# Convert to nvvidconv coordinates
SENSOR_WIDTH = 3840
SENSOR_HEIGHT = 2160

nvvidconv_params = {
    "left": config_crop["left"],                         # 480
    "right": SENSOR_WIDTH - config_crop["right"],        # 3360
    "top": config_crop["top"],                           # 272
    "bottom": SENSOR_HEIGHT - config_crop["bottom"]      # 1888
}

# Verify
output_width = nvvidconv_params["right"] - nvvidconv_params["left"]    # 2880
output_height = nvvidconv_params["bottom"] - nvvidconv_params["top"]   # 1616

assert output_width == SENSOR_WIDTH - config_crop["left"] - config_crop["right"]
assert output_height == SENSOR_HEIGHT - config_crop["top"] - config_crop["bottom"]
```

---

## Getting Help

If you encounter an error not covered here:

1. **Check logs:**
   ```bash
   tail -100 /var/log/footballvision-dev/api/error.log
   journalctl -u footballvision-api-dev -n 100
   ```

2. **Enable debug logging:**
   ```bash
   export GST_DEBUG=3
   sudo systemctl restart footballvision-api-dev
   ```

3. **Test pipeline manually:**
   ```bash
   gst-launch-1.0 -v [pipeline from pipeline_builders.py]
   ```

4. **Document the issue:**
   - Exact error message
   - Steps to reproduce
   - Log excerpts
   - System info: `uname -a`, `jetson_release`

#!/bin/bash
# Start snapshot-based calibration preview for focus adjustment

# Kill existing preview processes
pkill -f "gst-launch.*calibration" || true

sleep 1

# Camera 0 - 10% center crop @ 1fps (for focus calibration)
# sensor-mode=0 forces 4032x3040 @ 21fps mode, then we downsample to 1fps
# Crop to center 10% (403x304 pixels)
gst-launch-1.0 -e \
  nvarguscamerasrc sensor-id=0 sensor-mode=0 ! \
  "video/x-raw(memory:NVMM),width=4032,height=3040,framerate=21/1" ! \
  videorate ! \
  "video/x-raw(memory:NVMM),framerate=1/1" ! \
  nvvidconv ! \
  "video/x-raw,format=I420" ! \
  videocrop left=1814 top=1368 right=1814 bottom=1368 ! \
  jpegenc quality=90 ! \
  multifilesink location=/dev/shm/cam0.jpg max-files=1 &

sleep 1

# Camera 1 - 10% center crop @ 1fps (for focus calibration)
# sensor-mode=0 forces 4032x3040 @ 21fps mode, then we downsample to 1fps
# Crop to center 10% (403x304 pixels)
gst-launch-1.0 -e \
  nvarguscamerasrc sensor-id=1 sensor-mode=0 ! \
  "video/x-raw(memory:NVMM),width=4032,height=3040,framerate=21/1" ! \
  videorate ! \
  "video/x-raw(memory:NVMM),framerate=1/1" ! \
  nvvidconv ! \
  "video/x-raw,format=I420" ! \
  videocrop left=1814 top=1368 right=1814 bottom=1368 ! \
  jpegenc quality=90 ! \
  multifilesink location=/dev/shm/cam1.jpg max-files=1 &

sleep 2

echo "✓ Camera 0 snapshot: /dev/shm/cam0.jpg (full resolution @ 1fps)"
echo "✓ Camera 1 snapshot: /dev/shm/cam1.jpg (full resolution @ 1fps)"
echo "✓ API endpoints: /api/v1/preview/calibration/cam0/snapshot and cam1/snapshot"

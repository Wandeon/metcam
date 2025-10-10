#!/bin/bash
# Simple MJPEG preview - more reliable than HLS
set -euo pipefail

# TCP ports for MJPEG streams
CAM0_PORT=8554
CAM1_PORT=8555

# Check if cameras are in use
if pgrep -f "nvarguscamerasrc.*sensor-id=0" >/dev/null; then
    echo "ERROR: Cameras already in use (recording active?)" >&2
    exit 1
fi

cleanup() {
    pkill -P $$ 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Camera 0 - MJPEG over TCP
gst-launch-1.0 -e \
    nvarguscamerasrc sensor-id=0 sensor-mode=0 \
        wbmode=1 aelock=false \
        exposuretimerange="13000 33333333" \
        gainrange="1 8" saturation=1.1 \
    ! "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1" \
    ! nvvidconv \
    ! "video/x-raw,width=1920,height=1080,format=I420" \
    ! jpegenc quality=80 \
    ! multipartmux boundary="--videoboundary" \
    ! tcpserversink host=0.0.0.0 port=$CAM0_PORT \
    >/dev/null 2>&1 &

sleep 1

# Camera 1 - MJPEG over TCP
gst-launch-1.0 -e \
    nvarguscamerasrc sensor-id=1 sensor-mode=0 \
        wbmode=1 aelock=false \
        exposuretimerange="13000 33333333" \
        gainrange="1 8" saturation=1.1 \
    ! "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1" \
    ! nvvidconv \
    ! "video/x-raw,width=1920,height=1080,format=I420" \
    ! jpegenc quality=80 \
    ! multipartmux boundary="--videoboundary" \
    ! tcpserversink host=0.0.0.0 port=$CAM1_PORT \
    >/dev/null 2>&1 &

sleep 2

# Start HTTP proxy servers
cd /home/mislav/footballvision-pro/scripts
python3 mjpeg_http_server.py 8080 127.0.0.1 $CAM0_PORT >/dev/null 2>&1 &
python3 mjpeg_http_server.py 8081 127.0.0.1 $CAM1_PORT >/dev/null 2>&1 &

echo "MJPEG preview started!"
echo "Camera 0: http://<your-ip>:8080/"
echo "Camera 1: http://<your-ip>:8081/"
echo ""
echo "Open in browser - works with <img src='http://...'> or <video>"
echo "Press Ctrl+C to stop..."

wait

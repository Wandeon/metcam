#!/bin/bash
# Hardware-accelerated 1080p30 preview using nvv4l2h264enc
set -euo pipefail

HLS_DIR="/var/www/hls"
mkdir -p "$HLS_DIR"/{cam0,cam1}

# Clean up old segments
rm -f "$HLS_DIR"/cam0/*.{ts,m3u8} 2>/dev/null || true
rm -f "$HLS_DIR"/cam1/*.{ts,m3u8} 2>/dev/null || true

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

# Camera 0
gst-launch-1.0 -e \
    nvarguscamerasrc sensor-id=0 sensor-mode=0 \
        wbmode=1 aelock=false \
        exposuretimerange="13000 33333333" \
        gainrange="1 8" saturation=1.1 \
    ! "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1" \
    ! nvvidconv \
    ! "video/x-raw(memory:NVMM),width=1920,height=1080,format=I420" \
    ! nvv4l2h264enc \
        bitrate=3000000 \
        preset-level=1 \
        insert-sps-pps=true \
        idrinterval=60 \
        insert-vui=true \
        maxperf-enable=true \
    ! "video/x-h264,stream-format=byte-stream,profile=high" \
    ! h264parse config-interval=-1 \
    ! hlssink2 \
        location="$HLS_DIR/cam0/segment%05d.ts" \
        playlist-location="$HLS_DIR/cam0/playlist.m3u8" \
        max-files=10 \
        target-duration=2 \
        playlist-length=10 \
    >/dev/null 2>&1 &

sleep 1

# Camera 1
gst-launch-1.0 -e \
    nvarguscamerasrc sensor-id=1 sensor-mode=0 \
        wbmode=1 aelock=false \
        exposuretimerange="13000 33333333" \
        gainrange="1 8" saturation=1.1 \
    ! "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1" \
    ! nvvidconv \
    ! "video/x-raw(memory:NVMM),width=1920,height=1080,format=I420" \
    ! nvv4l2h264enc \
        bitrate=3000000 \
        preset-level=1 \
        insert-sps-pps=true \
        idrinterval=60 \
        insert-vui=true \
        maxperf-enable=true \
    ! "video/x-h264,stream-format=byte-stream,profile=high" \
    ! h264parse config-interval=-1 \
    ! hlssink2 \
        location="$HLS_DIR/cam1/segment%05d.ts" \
        playlist-location="$HLS_DIR/cam1/playlist.m3u8" \
        max-files=10 \
        target-duration=2 \
        playlist-length=10 \
    >/dev/null 2>&1 &

echo "Hardware-accelerated preview started!"
echo "Camera 0: http://<your-ip>/hls/cam0/playlist.m3u8"
echo "Camera 1: http://<your-ip>/hls/cam1/playlist.m3u8"
echo ""
echo "Press Ctrl+C to stop..."

wait

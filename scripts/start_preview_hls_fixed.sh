#!/bin/bash
# Fixed HLS preview with proper x264 settings for smooth streaming
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

echo "Starting HLS preview streams..."

# Camera 0 - Optimized for smooth streaming
gst-launch-1.0 -e \
    nvarguscamerasrc sensor-id=0 sensor-mode=0 \
        wbmode=1 aelock=false \
        exposuretimerange="13000 33333333" \
        gainrange="1 8" saturation=1.1 \
    ! "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1" \
    ! nvvidconv \
    ! "video/x-raw,width=1920,height=1080,format=I420" \
    ! queue max-size-buffers=30 leaky=downstream \
    ! videorate drop-only=true \
    ! "video/x-raw,framerate=30/1" \
    ! x264enc \
        bitrate=2500 \
        speed-preset=veryfast \
        tune=zerolatency \
        key-int-max=30 \
        threads=2 \
        sliced-threads=true \
        b-adapt=false \
        bframes=0 \
        aud=false \
        byte-stream=true \
        vbv-buf-capacity=2000 \
        option-string="sync-lookahead=0:rc-lookahead=0:no-mbtree=1" \
    ! "video/x-h264,profile=baseline,stream-format=byte-stream" \
    ! h264parse config-interval=1 \
    ! queue max-size-buffers=30 leaky=downstream \
    ! hlssink2 \
        location="$HLS_DIR/cam0/segment%05d.ts" \
        playlist-location="$HLS_DIR/cam0/playlist.m3u8" \
        max-files=6 \
        target-duration=1 \
        playlist-length=6 \
    >/dev/null 2>&1 &

sleep 2

# Camera 1 - Optimized for smooth streaming
gst-launch-1.0 -e \
    nvarguscamerasrc sensor-id=1 sensor-mode=0 \
        wbmode=1 aelock=false \
        exposuretimerange="13000 33333333" \
        gainrange="1 8" saturation=1.1 \
    ! "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1" \
    ! nvvidconv \
    ! "video/x-raw,width=1920,height=1080,format=I420" \
    ! queue max-size-buffers=30 leaky=downstream \
    ! videorate drop-only=true \
    ! "video/x-raw,framerate=30/1" \
    ! x264enc \
        bitrate=2500 \
        speed-preset=veryfast \
        tune=zerolatency \
        key-int-max=30 \
        threads=2 \
        sliced-threads=true \
        b-adapt=false \
        bframes=0 \
        aud=false \
        byte-stream=true \
        vbv-buf-capacity=2000 \
        option-string="sync-lookahead=0:rc-lookahead=0:no-mbtree=1" \
    ! "video/x-h264,profile=baseline,stream-format=byte-stream" \
    ! h264parse config-interval=1 \
    ! queue max-size-buffers=30 leaky=downstream \
    ! hlssink2 \
        location="$HLS_DIR/cam1/segment%05d.ts" \
        playlist-location="$HLS_DIR/cam1/playlist.m3u8" \
        max-files=6 \
        target-duration=1 \
        playlist-length=6 \
    >/dev/null 2>&1 &

echo "✓ HLS preview started"
echo "  Camera 0: /hls/cam0/playlist.m3u8"
echo "  Camera 1: /hls/cam1/playlist.m3u8"
echo ""
echo "Press Ctrl+C to stop..."

wait

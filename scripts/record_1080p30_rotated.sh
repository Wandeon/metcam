#!/bin/bash
# Production 1080p30 dual-camera recording with ±20° rotation
# Uses native 1080p60 sensor mode for optimal performance
set -euo pipefail

# Configuration
MATCH_ID="${MATCH_ID:-match_$(date +%Y%m%d_%H%M%S)}"
REC_DIR="${REC_DIR:-/mnt/recordings/${MATCH_ID}}"
RECORD_SECONDS="${RECORD_SECONDS:-3600}"  # Default 60 minutes
REC_BITRATE_KBPS="${REC_BITRATE_KBPS:-8000}"
REC_THREADS="${REC_THREADS:-2}"

# Shader paths
SHADER_CCW="/home/mislav/footballvision-pro/src/video-pipeline/shaders/rotate_crop_ccw20.frag"
SHADER_CW="/home/mislav/footballvision-pro/src/video-pipeline/shaders/rotate_crop_cw20.frag"

mkdir -p "$REC_DIR"
LOG_FILE="$REC_DIR/recording.log"
METRICS_FILE="$REC_DIR/performance_metrics.log"

# Read and flatten shaders
shader_ccw=$(cat "$SHADER_CCW" | tr '\n' ' ')
shader_cw=$(cat "$SHADER_CW" | tr '\n' ' ')

echo "========================================"
echo "FootballVision Pro - 1080p30 Recording"
echo "Match ID: $MATCH_ID"
echo "Recording directory: $REC_DIR"
echo "Duration: ${RECORD_SECONDS}s"
echo "Resolution: 1920x1080 @ 30 fps"
echo "Sensor mode: Native 1080p60 (downsampled to 30fps)"
echo "Rotation: Cam0 -20° CCW, Cam1 +20° CW"
echo "Container: Matroska (MKV)"
echo "Encoder: x264 (software, ultrafast preset)"
echo "Test started: $(date)"
echo "========================================"

# Start tegrastats monitoring
tegrastats --interval 1000 --logfile "$REC_DIR/tegrastats.log" &
TEGRASTATS_PID=$!

# Camera 0: -20° CCW rotation
echo "Launching Camera 0 pipeline (CCW -20°)..."
gst-launch-1.0 -e \
    nvarguscamerasrc sensor-id=0 sensor-mode=1 wbmode=1 aelock=false \
      exposuretimerange="13000 33333333" gainrange="1 8" saturation=1.1 \
    ! "video/x-raw(memory:NVMM),width=1920,height=1080,framerate=60/1" \
    ! nvvidconv \
    ! "video/x-raw,format=RGBA,width=1920,height=1080" \
    ! videorate drop-only=true \
    ! "video/x-raw,framerate=30/1" \
    ! queue max-size-buffers=4 \
    ! glupload \
    ! glshader fragment="${shader_ccw}" \
    ! gldownload \
    ! videoconvert \
    ! "video/x-raw,format=I420" \
    ! x264enc bitrate=${REC_BITRATE_KBPS} speed-preset=ultrafast tune=zerolatency \
        key-int-max=30 threads=${REC_THREADS} b-adapt=false sliced-threads=true \
    ! h264parse config-interval=-1 \
    ! matroskamux streamable=true \
    ! filesink location="${REC_DIR}/cam0_rotated.mkv" \
    >>"$LOG_FILE" 2>&1 &

CAM0_PID=$!

sleep 1

# Camera 1: +20° CW rotation
echo "Launching Camera 1 pipeline (CW +20°)..."
gst-launch-1.0 -e \
    nvarguscamerasrc sensor-id=1 sensor-mode=1 wbmode=1 aelock=false \
      exposuretimerange="13000 33333333" gainrange="1 8" saturation=1.1 \
    ! "video/x-raw(memory:NVMM),width=1920,height=1080,framerate=60/1" \
    ! nvvidconv \
    ! "video/x-raw,format=RGBA,width=1920,height=1080" \
    ! videorate drop-only=true \
    ! "video/x-raw,framerate=30/1" \
    ! queue max-size-buffers=4 \
    ! glupload \
    ! glshader fragment="${shader_cw}" \
    ! gldownload \
    ! videoconvert \
    ! "video/x-raw,format=I420" \
    ! x264enc bitrate=${REC_BITRATE_KBPS} speed-preset=ultrafast tune=zerolatency \
        key-int-max=30 threads=${REC_THREADS} b-adapt=false sliced-threads=true \
    ! h264parse config-interval=-1 \
    ! matroskamux streamable=true \
    ! filesink location="${REC_DIR}/cam1_rotated.mkv" \
    >>"$LOG_FILE" 2>&1 &

CAM1_PID=$!

sleep 2

echo ""
echo "Recording active. Duration: ${RECORD_SECONDS}s"
echo "Camera 0 PID: $CAM0_PID"
echo "Camera 1 PID: $CAM1_PID"
echo "Logs: $LOG_FILE"
echo "Metrics: $METRICS_FILE"
echo ""

# Record performance metrics
{
    echo "=== Performance Metrics ==="
    echo "Timestamp: $(date)"
    echo ""
    echo "=== System Info ==="
    echo "Tegrastats logging to: $REC_DIR/tegrastats.log (PID: $TEGRASTATS_PID)"
    echo ""
} > "$METRICS_FILE"

# Wait for recording duration
sleep "$RECORD_SECONDS"

# Stop recording gracefully
echo "Stopping recording..."
kill -INT $CAM0_PID 2>/dev/null || true
sleep 1

# Wait for container finalization
echo "Waiting for container finalization..."
sleep 3

{
    echo "=== Final CPU Usage ==="
    uptime
    echo ""
    echo "=== Recording Files ==="
    ls -lh "$REC_DIR"/*.mkv
} >> "$METRICS_FILE"

echo "Recording stopped at: $(date)"
echo "Files saved to: $REC_DIR"

# Stop second camera
echo "Stopping recording..."
kill -INT $CAM1_PID 2>/dev/null || true
sleep 1

# Wait for container finalization
echo "Waiting for container finalization..."
sleep 3

{
    echo "=== Final CPU Usage ==="
    uptime
    echo ""
    echo "=== Recording Files ==="
    ls -lh "$REC_DIR"/*.mkv
} >> "$METRICS_FILE"

echo "Recording stopped at: $(date)"
echo "Files saved to: $REC_DIR"

# Stop tegrastats
kill $TEGRASTATS_PID 2>/dev/null || true

echo "Recording complete!"

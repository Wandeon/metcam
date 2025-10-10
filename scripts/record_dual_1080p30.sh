#!/bin/bash
set -euo pipefail

# Kill any existing recordings
pkill -f gst-launch || true
sleep 1

# Match ID from argument or timestamp
MATCH_ID="${1:-match_$(date +%Y%m%d_%H%M%S)}"
REC_DIR="/mnt/recordings/${MATCH_ID}"
SEG_DIR="${REC_DIR}/segments"

# Create directories
mkdir -p "$REC_DIR" "$SEG_DIR"

# Set 25W power mode for maximum performance
sudo nvpmodel -m 1 >/dev/null 2>&1 || true
sudo jetson_clocks >/dev/null 2>&1 || true

# Recording settings (1920x1080@30fps, RECORDING ONLY - no preview)
REC_BITRATE_KBPS=45000
REC_GOP_FRAMES=60          # 2s GOP at 30 fps
REC_THREADS=4
SEGMENT_DURATION=$((5*60))  # 5 minutes

# Log file
LOG_FILE="$REC_DIR/recording.log"

echo "========================================" | tee "$LOG_FILE"
echo "FootballVision Pro - Segmented Dual Camera Recording" | tee -a "$LOG_FILE"
echo "Match ID: $MATCH_ID" | tee -a "$LOG_FILE"
echo "Recording to: $SEG_DIR" | tee -a "$LOG_FILE"
echo "Segment duration: 5 minutes" | tee -a "$LOG_FILE"
echo "Mode: RECORDING ONLY (no preview)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Function to cleanup on exit
cleanup() {
    echo "Stopping recording..." | tee -a "$LOG_FILE"
    pkill -f gst-launch || true
    sleep 2
    
    # Count segments
    CAM0_SEGMENTS=$(ls -1 "$SEG_DIR"/cam0_*.mp4 2>/dev/null | wc -l)
    CAM1_SEGMENTS=$(ls -1 "$SEG_DIR"/cam1_*.mp4 2>/dev/null | wc -l)
    
    echo "Recording stopped." | tee -a "$LOG_FILE"
    echo "Camera 0: $CAM0_SEGMENTS segments" | tee -a "$LOG_FILE"
    echo "Camera 1: $CAM1_SEGMENTS segments" | tee -a "$LOG_FILE"
    echo "Files saved to $SEG_DIR" | tee -a "$LOG_FILE"
}
trap cleanup EXIT INT TERM

# ---------- Camera 0 (Left) ----------
echo "Starting Camera 0..." | tee -a "$LOG_FILE"
gst-launch-1.0 -e \
  nvarguscamerasrc sensor-id=0 sensor-mode=1 \
    wbmode=1 \
    aelock=false \
    exposuretimerange="13000 33333333" \
    gainrange="1 10" \
    ispdigitalgainrange="1 1" \
    saturation=1.0 \
\! "video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1" \
\! queue max-size-buffers=30 max-size-time=0 max-size-bytes=0 \
\! nvvidconv \
\! "video/x-raw,format=I420" \
\! x264enc \
    bitrate=${REC_BITRATE_KBPS} \
    speed-preset=ultrafast \
    key-int-max=${REC_GOP_FRAMES} \
    threads=${REC_THREADS} \
\! h264parse config-interval=-1 \
\! splitmuxsink \
    location="${SEG_DIR}/cam0_%05d.mp4" \
    muxer=mp4mux \
    max-size-time=$((SEGMENT_DURATION*1000000000)) \
    max-files=0 \
    async-finalize=true \
2>&1 | tee -a "$LOG_FILE" &

CAM0_PID=$!
sleep 2

# ---------- Camera 1 (Right) ----------
echo "Starting Camera 1..." | tee -a "$LOG_FILE"
gst-launch-1.0 -e \
  nvarguscamerasrc sensor-id=1 sensor-mode=1 \
    wbmode=1 \
    aelock=false \
    exposuretimerange="13000 33333333" \
    gainrange="1 10" \
    ispdigitalgainrange="1 1" \
    saturation=1.0 \
\! "video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1" \
\! queue max-size-buffers=30 max-size-time=0 max-size-bytes=0 \
\! nvvidconv \
\! "video/x-raw,format=I420" \
\! x264enc \
    bitrate=${REC_BITRATE_KBPS} \
    speed-preset=ultrafast \
    key-int-max=${REC_GOP_FRAMES} \
    threads=${REC_THREADS} \
\! h264parse config-interval=-1 \
\! splitmuxsink \
    location="${SEG_DIR}/cam1_%05d.mp4" \
    muxer=mp4mux \
    max-size-time=$((SEGMENT_DURATION*1000000000)) \
    max-files=0 \
    async-finalize=true \
2>&1 | tee -a "$LOG_FILE" &

CAM1_PID=$!

echo "" | tee -a "$LOG_FILE"
echo "Recording started successfully!" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Settings:" | tee -a "$LOG_FILE"
echo "  Resolution: 1920x1080 @ 30 fps" | tee -a "$LOG_FILE"
echo "  Bitrate: ${REC_BITRATE_KBPS} kbps per camera" | tee -a "$LOG_FILE"
echo "  Segment duration: 5 minutes" | tee -a "$LOG_FILE"
echo "  Mode: RECORDING ONLY (no preview)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Press Ctrl+C to stop recording" | tee -a "$LOG_FILE"

# Wait for both processes
wait $CAM0_PID $CAM1_PID

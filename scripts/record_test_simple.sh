#!/bin/bash
set -euo pipefail

# Kill any existing recordings
pkill -f gst-launch || true
sleep 1

# Match ID from argument or timestamp
MATCH_ID="${1:-match_$(date +%Y%m%d_%H%M%S)}"
REC_DIR="/mnt/recordings/${MATCH_ID}"

# Create directories
mkdir -p "$REC_DIR/segments"

# Lock Jetson clocks for performance
sudo nvpmodel -m 1
sudo jetson_clocks

# Recording settings
REC_BITRATE_KBPS=15000
REC_GOP_FRAMES=30
REC_THREADS=2

# Log file
LOG_FILE="$REC_DIR/recording.log"

echo "========================================"  | tee "$LOG_FILE"
echo "FootballVision Pro - Simple Test" | tee -a "$LOG_FILE"
echo "Match ID: $MATCH_ID" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Function to cleanup on exit
cleanup() {
    echo "Stopping recording..." | tee -a "$LOG_FILE"
    pkill -f gst-launch || true
    sleep 2
    echo "Recording stopped. Files saved to $REC_DIR" | tee -a "$LOG_FILE"
}
trap cleanup EXIT INT TERM

# ---------- Camera 0 (Left) - Recording Only ----------
echo "Starting Camera 0 recording..." | tee -a "$LOG_FILE"
gst-launch-1.0 -e \
  nvarguscamerasrc sensor-id=0 \
    wbmode=1 \
    aelock=false \
    exposuretimerange="500 4000" \
    gainrange="1 8" \
    saturation=1.2 \
! "video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1" \
! nvvidconv \
! "video/x-raw,format=I420" \
! x264enc \
    bitrate=${REC_BITRATE_KBPS} \
    speed-preset=ultrafast \
    tune=zerolatency \
    key-int-max=${REC_GOP_FRAMES} \
    threads=${REC_THREADS} \
    sliced-threads=false \
    rc-lookahead=0 \
    bframes=0 \
    cabac=false \
! h264parse config-interval=-1 \
! splitmuxsink \
    location="${REC_DIR}/segments/cam0_%05d.mp4" \
    muxer=mp4mux \
    max-size-time=$((30*1000000000)) \
    max-files=0 \
    async-finalize=true \
2>&1 | tee -a "$LOG_FILE" &

CAM0_PID=$!
sleep 3

echo "" | tee -a "$LOG_FILE"
echo "Recording started successfully!" | tee -a "$LOG_FILE"
echo "PID: $CAM0_PID" | tee -a "$LOG_FILE"
echo "Press Ctrl+C to stop recording" | tee -a "$LOG_FILE"

# Wait for process
wait $CAM0_PID

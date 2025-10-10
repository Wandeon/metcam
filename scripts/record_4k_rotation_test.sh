#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
SHADER_DIR="$REPO_ROOT/src/video-pipeline/shaders"

ROTATE_CCW="$SHADER_DIR/rotate_crop_ccw20.frag"
ROTATE_CW="$SHADER_DIR/rotate_crop_cw20.frag"

if [[ ! -f "$ROTATE_CCW" || ! -f "$ROTATE_CW" ]]; then
  echo "Error: rotation shaders not found in $SHADER_DIR" >&2
  exit 1
fi

# Kill any existing recordings
pkill -f gst-launch || true
sleep 1

# Test recording parameters
MATCH_ID="${1:-4k_rotation_test_1}"
REC_DIR="/mnt/recordings/${MATCH_ID}"
RECORD_SECONDS=${RECORD_SECONDS:-60}

mkdir -p "$REC_DIR"

# Performance mode
sudo nvpmodel -m 1 >/dev/null 2>&1 || true
sudo jetson_clocks >/dev/null 2>&1 || true

# Encoding parameters - using ultrafast preset due to CPU-bound x264
REC_BITRATE_KBPS=90000
REC_GOP_FRAMES=60
REC_THREADS=8

LOG_FILE="$REC_DIR/recording_test.log"
METRICS_FILE="$REC_DIR/performance_metrics.log"

{
  echo "========================================"
  echo "FootballVision Pro - 4K Rotation Test"
  echo "Match ID: $MATCH_ID"
  echo "Recording directory: $REC_DIR"
  echo "Duration: ${RECORD_SECONDS}s"
  echo "Resolution: 3840x2160 @ 30 fps"
  echo "Crop: centre 70% (30% total cropped)"
  echo "Rotation: Cam0 -20° CCW, Cam1 +20° CW"
  echo "Container: Matroska (MKV)"
  echo "Encoder: x264 (software, ultrafast preset)"
  echo "Test started: $(date)"
  echo "========================================"
} | tee "$LOG_FILE"

# Start performance monitoring in background
{
  echo "=== Performance Metrics ==="
  echo "Timestamp: $(date)"
  echo ""
  echo "=== System Info ==="
  tegrastats --interval 1000 --logfile "${REC_DIR}/tegrastats.log" &
  TEGRASTATS_PID=$!
  echo "Tegrastats logging to: ${REC_DIR}/tegrastats.log (PID: $TEGRASTATS_PID)"
} >> "$METRICS_FILE"

cleanup() {
  echo "Stopping recording..." | tee -a "$LOG_FILE"

  # Send EOS to pipelines for proper finalization
  for pid in "${CAM0_PID:-}" "${CAM1_PID:-}"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      # Send EOS signal
      kill -INT "$pid" 2>/dev/null || true
    fi
  done

  # Wait for pipelines to finalize
  echo "Waiting for container finalization..." | tee -a "$LOG_FILE"
  sleep 3

  for pid in "${CAM0_PID:-}" "${CAM1_PID:-}"; do
    if [[ -n "$pid" ]]; then
      wait "$pid" 2>/dev/null || true
    fi
  done

  # Stop performance monitoring
  if [[ -n "${TEGRASTATS_PID:-}" ]] && kill -0 "$TEGRASTATS_PID" 2>/dev/null; then
    kill "$TEGRASTATS_PID" 2>/dev/null || true
  fi

  echo "Recording stopped at: $(date)" | tee -a "$LOG_FILE"
  echo "Files saved to: $REC_DIR" | tee -a "$LOG_FILE"

  # Collect final metrics
  {
    echo ""
    echo "=== Final CPU Usage ==="
    uptime
    echo ""
    echo "=== Recording Files ==="
    ls -lh "$REC_DIR"/*.mkv 2>/dev/null || echo "No MKV files found"
  } >> "$METRICS_FILE"
}
trap cleanup EXIT INT TERM

start_camera() {
  local sensor_id="$1"
  local shader_path="$2"
  local cam_name="$3"
  local shader_src
  shader_src=$(tr '\n' ' ' < "$shader_path")

  # Using matroskamux instead of splitmuxsink for reliable container finalization
  gst-launch-1.0 -e \
    nvarguscamerasrc sensor-id=${sensor_id} sensor-mode=0 wbmode=1 aelock=false \
      exposuretimerange="13000 33333333" gainrange="1 10" ispdigitalgainrange="1 1" saturation=1.1 \
    ! "video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1" \
    ! nvvidconv \
    ! "video/x-raw,format=RGBA,width=3840,height=2160" \
    ! queue max-size-buffers=4 max-size-bytes=0 max-size-time=0 \
    ! glupload \
    ! glshader fragment="${shader_src}" \
    ! gldownload \
    ! "video/x-raw,format=RGBA,width=3840,height=2160" \
    ! videoconvert \
    ! "video/x-raw,format=I420,width=3840,height=2160" \
    ! x264enc bitrate=${REC_BITRATE_KBPS} speed-preset=ultrafast tune=zerolatency key-int-max=${REC_GOP_FRAMES} threads=${REC_THREADS} \
        b-adapt=false sliced-threads=true option-string="nal-hrd=cbr:vbv-maxrate=${REC_BITRATE_KBPS}:vbv-bufsize=${REC_BITRATE_KBPS}:force-cfr=true:repeat-headers=true" \
    ! h264parse config-interval=-1 \
    ! matroskamux streamable=true \
    ! filesink location="${REC_DIR}/${cam_name}.mkv" \
    >>"$LOG_FILE" 2>&1 &

  echo $!
}

echo "Launching Camera 0 pipeline (CCW -20°)..." | tee -a "$LOG_FILE"
CAM0_PID=$(start_camera 0 "$ROTATE_CCW" "cam0_rotated")
sleep 2

echo "Launching Camera 1 pipeline (CW +20°)..." | tee -a "$LOG_FILE"
CAM1_PID=$(start_camera 1 "$ROTATE_CW" "cam1_rotated")

echo "" | tee -a "$LOG_FILE"
echo "Recording active. Duration: ${RECORD_SECONDS}s" | tee -a "$LOG_FILE"
echo "Camera 0 PID: $CAM0_PID" | tee -a "$LOG_FILE"
echo "Camera 1 PID: $CAM1_PID" | tee -a "$LOG_FILE"
echo "Logs: $LOG_FILE" | tee -a "$LOG_FILE"
echo "Metrics: $METRICS_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Record for specified duration
sleep "$RECORD_SECONDS"

cleanup

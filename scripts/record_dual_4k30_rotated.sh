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

pkill -f gst-launch || true
sleep 1

MATCH_ID="${1:-match_$(date +%Y%m%d_%H%M%S)}"
REC_DIR="/mnt/recordings/${MATCH_ID}"
SEG_DIR="${REC_DIR}/segments"

RECORD_SECONDS=${RECORD_SECONDS:-10}
SEGMENT_SECONDS=${SEGMENT_SECONDS:-300}

mkdir -p "$SEG_DIR"

sudo nvpmodel -m 1 >/dev/null 2>&1 || true
sudo jetson_clocks >/dev/null 2>&1 || true

REC_BITRATE_KBPS=90000
REC_GOP_FRAMES=60
REC_THREADS=8
SEGMENT_DURATION=$SEGMENT_SECONDS

LOG_FILE="$REC_DIR/recording_rotated.log"

{
  echo "========================================"
  echo "FootballVision Pro - Rotated 4K Recording"
  echo "Match ID: $MATCH_ID"
  echo "Segments dir: $SEG_DIR"
  echo "Resolution: 3840x2160 @ 30 fps (crop+rotate)"
  echo "Crop: centre 70% (30% total cropped)"
  echo "Rotation: Cam0 -20° CCW, Cam1 +20° CW"
  echo "========================================"
} | tee "$LOG_FILE"

cleanup() {
  echo "Stopping rotated recording..." | tee -a "$LOG_FILE"
  for pid in "$CAM0_PID" "$CAM1_PID"; do
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill -INT "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  sleep 2
  echo "Files saved to $SEG_DIR" | tee -a "$LOG_FILE"
}
trap cleanup EXIT INT TERM

start_camera() {
  local sensor_id="$1"
  local shader_path="$2"
  local suffix="$3"
  local shader_src
  shader_src=$(tr '\n' ' ' < "$shader_path")

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
    ! x264enc bitrate=${REC_BITRATE_KBPS} speed-preset=medium tune=zerolatency key-int-max=${REC_GOP_FRAMES} threads=${REC_THREADS} \
        b-adapt=false sliced-threads=true option-string="nal-hrd=cbr:vbv-maxrate=${REC_BITRATE_KBPS}:vbv-bufsize=${REC_BITRATE_KBPS}:force-cfr=true:repeat-headers=true" \
    ! h264parse config-interval=-1 \
    ! splitmuxsink \
        location="${SEG_DIR}/cam${suffix}_rot_%05d.mp4" \
        muxer=mp4mux \
        max-size-time=$((SEGMENT_DURATION*1000000000)) \
        max-files=0 \
        async-finalize=false \
    >>"$LOG_FILE" 2>&1 &

  echo $!
}

echo "Launching Camera 0 pipeline..." | tee -a "$LOG_FILE"
CAM0_PID=$(start_camera 0 "$ROTATE_CCW" 0)
sleep 2

echo "Launching Camera 1 pipeline..." | tee -a "$LOG_FILE"
CAM1_PID=$(start_camera 1 "$ROTATE_CW" 1)

echo "Rotated 4K recording active." | tee -a "$LOG_FILE"

sleep "$RECORD_SECONDS"

cleanup

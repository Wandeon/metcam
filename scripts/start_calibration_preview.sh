#!/bin/bash
set -euo pipefail

LOG_DIR="/var/log/footballvision"
PIPE_PIDS=()

# Calibration tunables (override via environment variables as needed)
SENSOR_MODE=${SENSOR_MODE:-0}
CAPTURE_FPS=${CAPTURE_FPS:-21}
OUTPUT_FPS=${OUTPUT_FPS:-1}
JPEG_QUALITY=${JPEG_QUALITY:-95}
EXPOSURE_MIN_NS=${EXPOSURE_MIN_NS:-4000000}
EXPOSURE_MAX_NS=${EXPOSURE_MAX_NS:-8333333}
GAIN_MIN=${GAIN_MIN:-1}
GAIN_MAX=${GAIN_MAX:-8}
CROP_SIZE=${CROP_SIZE:-800}

SENSOR_WIDTH=4032
SENSOR_HEIGHT=3040
LEFT=$(( (SENSOR_WIDTH - CROP_SIZE) / 2 ))
RIGHT=$LEFT
TOP=$(( (SENSOR_HEIGHT - CROP_SIZE) / 2 ))
BOTTOM=$TOP

mkdir -p "$LOG_DIR"

cleanup() {
    for pid in "${PIPE_PIDS[@]}"; do
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
}

trap cleanup EXIT INT TERM

if pgrep -f "nvarguscamerasrc.*splitmuxsink" >/dev/null; then
    echo "Cannot start calibration: recording or preview is using the cameras" >&2
    exit 2
fi

pkill -f "gst-launch-1.0.*calibration" >/dev/null 2>&1 || true
sleep 1

start_camera() {
    local sensor_id="$1"
    local target_file="$2"
    local log_file="$LOG_DIR/calibration_cam${sensor_id}.log"

    gst-launch-1.0 -e \
        nvarguscamerasrc \
            sensor-id=${sensor_id} \
            sensor-mode=${SENSOR_MODE} \
            wbmode=1 \
            aelock=false \
            exposuretimerange="${EXPOSURE_MIN_NS} ${EXPOSURE_MAX_NS}" \
            gainrange="${GAIN_MIN} ${GAIN_MAX}" \
            tnr-mode=0 \
        ! "video/x-raw(memory:NVMM),width=${SENSOR_WIDTH},height=${SENSOR_HEIGHT},framerate=${CAPTURE_FPS}/1" \
        ! queue max-size-buffers=4 leaky=2 \
        ! videorate drop-only=true \
        ! "video/x-raw(memory:NVMM),framerate=${OUTPUT_FPS}/1" \
        ! nvvidconv \
        ! "video/x-raw,format=I420" \
        ! videocrop left=${LEFT} right=${RIGHT} top=${TOP} bottom=${BOTTOM} \
        ! jpegenc quality=${JPEG_QUALITY} \
        ! multifilesink location=${target_file} max-files=1 \
        >>"$log_file" 2>&1 &

    PIPE_PIDS+=($!)
}

start_camera 0 /dev/shm/cam0.jpg
sleep 1
start_camera 1 /dev/shm/cam1.jpg
sleep 2

for pid in "${PIPE_PIDS[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "Calibration preview failed to start" >&2
        exit 1
    fi
done

echo "✓ Camera 0 snapshot: /dev/shm/cam0.jpg (center ${CROP_SIZE}x${CROP_SIZE} @ ${OUTPUT_FPS}fps)"
echo "✓ Camera 1 snapshot: /dev/shm/cam1.jpg (center ${CROP_SIZE}x${CROP_SIZE} @ ${OUTPUT_FPS}fps)"
echo "✓ API endpoints: /api/v1/preview/calibration/cam0/snapshot and cam1/snapshot"

wait "${PIPE_PIDS[@]}"

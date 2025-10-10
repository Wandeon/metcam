#!/bin/bash
set -euo pipefail

LOG_DIR="/var/log/footballvision"
PIPE_PIDS=()

# Calibration tunables (override via environment variables as needed)
SENSOR_MODE=${SENSOR_MODE:-1}  # Use mode 1 (1080p60) for consistent framing
JPEG_QUALITY=${JPEG_QUALITY:-95}
EXPOSURE_MIN_NS=${EXPOSURE_MIN_NS:-1000000}
EXPOSURE_MAX_NS=${EXPOSURE_MAX_NS:-683709000}
GAIN_MIN=${GAIN_MIN:-1}
GAIN_MAX=${GAIN_MAX:-8}
CROP_SIZE=${CROP_SIZE:-800}
OUTPUT_FPS=${OUTPUT_FPS:-1}

case "${SENSOR_MODE}" in
    0)
        SENSOR_WIDTH=3840
        SENSOR_HEIGHT=2160
        DEFAULT_CAPTURE_FPS=30
        ;;
    1)
        SENSOR_WIDTH=1920
        SENSOR_HEIGHT=1080
        DEFAULT_CAPTURE_FPS=60
        ;;
    *)
        echo "Unsupported SENSOR_MODE=${SENSOR_MODE}; falling back to mode 1 (1920x1080@60fps)" >&2
        SENSOR_MODE=1
        SENSOR_WIDTH=1920
        SENSOR_HEIGHT=1080
        DEFAULT_CAPTURE_FPS=60
        ;;
 esac

CAPTURE_FPS=${CAPTURE_FPS:-$DEFAULT_CAPTURE_FPS}

if (( CROP_SIZE > SENSOR_WIDTH || CROP_SIZE > SENSOR_HEIGHT )); then
    echo "CROP_SIZE=${CROP_SIZE} exceeds sensor dimensions ${SENSOR_WIDTH}x${SENSOR_HEIGHT}" >&2
    exit 3
fi

# Default crop for cam1 (center)
CAM1_LEFT=$(( (SENSOR_WIDTH - CROP_SIZE) / 2 ))
CAM1_RIGHT=$CAM1_LEFT
CAM1_TOP=$(( (SENSOR_HEIGHT - CROP_SIZE) / 2 ))
CAM1_BOTTOM=$CAM1_TOP

# Adjusted crop for cam0 (needs to be shifted based on sensor characteristics)
# For mode 0 (4K): cam0 appears to need no crop adjustment, use full sensor
# We'll use mode 1 instead which provides consistent framing
CAM0_LEFT=$CAM1_LEFT
CAM0_RIGHT=$CAM1_RIGHT
CAM0_TOP=$CAM1_TOP
CAM0_BOTTOM=$CAM1_BOTTOM

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
    local left="$3"
    local right="$4"
    local top="$5"
    local bottom="$6"
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
        ! videocrop left=${left} right=${right} top=${top} bottom=${bottom} \
        ! jpegenc quality=${JPEG_QUALITY} \
        ! multifilesink location=${target_file} max-files=1 \
        >>"$log_file" 2>&1 &

    PIPE_PIDS+=($!)
}

start_camera 0 /dev/shm/cam0.jpg ${CAM0_LEFT} ${CAM0_RIGHT} ${CAM0_TOP} ${CAM0_BOTTOM}
sleep 1
start_camera 1 /dev/shm/cam1.jpg ${CAM1_LEFT} ${CAM1_RIGHT} ${CAM1_TOP} ${CAM1_BOTTOM}
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

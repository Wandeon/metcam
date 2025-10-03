#!/bin/bash
set -euo pipefail

LOG_DIR="/var/log/footballvision"
PIPE_PIDS=()

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
        nvarguscamerasrc sensor-id=${sensor_id} sensor-mode=0 wbmode=1 aelock=false exposuretimerange="500 4000" gainrange="1 8" \
        ! 'video/x-raw(memory:NVMM),width=4032,height=3040,framerate=21/1' \
        ! videorate \
        ! 'video/x-raw(memory:NVMM),framerate=1/1' \
        ! nvvidconv \
        ! 'video/x-raw,format=I420' \
        ! videocrop left=1814 top=1368 right=1814 bottom=1368 \
        ! jpegenc quality=90 \
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

echo "✓ Camera 0 snapshot: /dev/shm/cam0.jpg (full sensor @ 1fps)"
echo "✓ Camera 1 snapshot: /dev/shm/cam1.jpg (full sensor @ 1fps)"
echo "✓ API endpoints: /api/v1/preview/calibration/cam0/snapshot and cam1/snapshot"

wait "${PIPE_PIDS[@]}"

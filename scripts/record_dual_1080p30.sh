#!/bin/bash
set -euo pipefail

pkill -f gst-launch || true
sleep 1

MATCH_ID="${1:-match_$(date +%Y%m%d_%H%M%S)}"
REC_DIR="/mnt/recordings/${MATCH_ID}"
HLS_DIR="/var/www/hls/${MATCH_ID}"

mkdir -p "$REC_DIR" "$HLS_DIR" "$REC_DIR/segments"

sudo nvpmodel -m 1
sudo jetson_clocks

REC_BITRATE_KBPS=50000
REC_GOP_FRAMES=60

HLS_FPS=10
HLS_BITRATE_KBPS=4000
HLS_GOP_FRAMES=$HLS_FPS
HLS_MAX_FILES=10

LOG_FILE="$REC_DIR/recording.log"
CAM0_PID=""
CAM1_PID=""

{
    echo "========================================"
    echo "FootballVision Pro - Dual Camera Recording"
    echo "Match ID: $MATCH_ID"
    echo "Recording to: $REC_DIR"
    echo "HLS Preview: http://$(hostname -I | awk '{print $1}'):8888/hls/${MATCH_ID}/"
    echo "========================================"
} | tee "$LOG_FILE"

cleanup() {
    echo "Stopping recording..." | tee -a "$LOG_FILE"
    for pid in "$CAM0_PID" "$CAM1_PID"; do
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            kill -INT "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
    sleep 2
    echo "Recording stopped. Files saved to $REC_DIR" | tee -a "$LOG_FILE"
}
trap cleanup EXIT INT TERM

start_camera() {
    local sensor_id="$1"
    local segment_path="$2"
    local hls_path="$3"

    gst-launch-1.0 -e \
        nvarguscamerasrc sensor-id=${sensor_id} sensor-mode=1 wbmode=1 aelock=false exposuretimerange="13000 683709000" gainrange="1 12" ispdigitalgainrange="1 1" saturation=1.0 \
        ! "video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1" \
        ! tee name=t${sensor_id} \
        t${sensor_id}. ! queue max-size-buffers=30 max-size-time=0 max-size-bytes=0 \
            ! nvvidconv \
            ! "video/x-raw,format=I420" \
            ! x264enc bitrate=${REC_BITRATE_KBPS} speed-preset=fast key-int-max=${REC_GOP_FRAMES} threads=4 b-adapt=1 bframes=2 cabac=true byte-stream=false \
            ! h264parse config-interval=-1 \
            ! splitmuxsink location="${segment_path}/cam${sensor_id}_%05d.mp4" muxer=mp4mux max-size-time=$((5*60*1000000000)) max-files=0 async-finalize=true \
        t${sensor_id}. ! queue max-size-buffers=10 leaky=2 \
            ! nvvidconv \
            ! "video/x-raw,format=I420" \
            ! x264enc bitrate=${HLS_BITRATE_KBPS} speed-preset=ultrafast tune=zerolatency key-int-max=${HLS_GOP_FRAMES} threads=2 cabac=true byte-stream=true \
            ! h264parse config-interval=-1 \
            ! mpegtsmux \
            ! hlssink location="${hls_path}/cam${sensor_id}_%05d.ts" playlist-location="${hls_path}/cam${sensor_id}.m3u8" max-files=${HLS_MAX_FILES} target-duration=2 playlist-length=3 \
        >>"$LOG_FILE" 2>&1 &

    echo $!
}

printf "Starting Camera 0...\n" | tee -a "$LOG_FILE"
CAM0_PID=$(start_camera 0 "$REC_DIR/segments" "$HLS_DIR")
sleep 2

printf "Starting Camera 1...\n" | tee -a "$LOG_FILE"
CAM1_PID=$(start_camera 1 "$REC_DIR/segments" "$HLS_DIR")

{
    echo ""
    echo "Recording started successfully!"
    echo ""
    echo "View live streams at:"
    echo "  Camera 0: http://$(hostname -I | awk '{print $1}'):8888/hls/${MATCH_ID}/cam0.m3u8"
    echo "  Camera 1: http://$(hostname -I | awk '{print $1}'):8888/hls/${MATCH_ID}/cam1.m3u8"
    echo ""
    echo "Press Ctrl+C to stop recording"
} | tee -a "$LOG_FILE"

wait "$CAM0_PID" "$CAM1_PID"

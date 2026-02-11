#!/bin/bash
# FootballVision Pro - Quick Functionality Test
# Smoke tests for preview, recording, mutex behavior, and health endpoints.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

API_URL="http://localhost:8000/api/v1"
PREVIEW_TRANSPORT="${PREVIEW_TRANSPORT:-hls}" # hls | webrtc

cleanup() {
    curl -s -X DELETE "$API_URL/preview" >/dev/null 2>&1 || true
    curl -s -X DELETE "$API_URL/recording?force=true" >/dev/null 2>&1 || true
}

trap cleanup EXIT

json_get_bool() {
    local key="$1"
    python3 -c '
import json
import sys

key = sys.argv[1]
obj = json.loads(sys.stdin.read())
value = obj
for part in key.split("."):
    if isinstance(value, dict) and part in value:
        value = value[part]
    else:
        print("false")
        sys.exit(0)
print("true" if bool(value) else "false")
' "$key"
}

json_get_str() {
    local key="$1"
    python3 -c '
import json
import sys

key = sys.argv[1]
obj = json.loads(sys.stdin.read())
value = obj
for part in key.split("."):
    if isinstance(value, dict) and part in value:
        value = value[part]
    else:
        print("")
        sys.exit(0)
print("" if value is None else str(value))
' "$key"
}

echo "============================================================"
echo " FootballVision Pro - Quick Functionality Test"
echo "============================================================"
echo

log_info "Test 1: API and pipeline state endpoints"
STATUS=$(curl -s "$API_URL/status")
if echo "$STATUS" | python3 -c 'import json,sys; d=json.load(sys.stdin); print("ok" if isinstance(d, dict) and "recording" in d and "preview" in d else "bad")' | grep -q "ok"; then
    log_success "Status endpoint responding"
else
    log_error "Status endpoint returned unexpected shape: $STATUS"
fi

PIPELINE_STATE=$(curl -s "$API_URL/pipeline-state")
CURRENT_MODE=$(echo "$PIPELINE_STATE" | json_get_str "mode")
log_info "Current pipeline mode: $CURRENT_MODE"

if [ "$CURRENT_MODE" != "idle" ]; then
    log_warning "Pipeline not idle, forcing cleanup before tests"
    curl -s -X DELETE "$API_URL/preview" >/dev/null 2>&1 || true
    curl -s -X DELETE "$API_URL/recording?force=true" >/dev/null 2>&1 || true
    sleep 2
fi

log_info "Test 2: Preview start/stop"
PREVIEW_START=$(curl -s -X POST "$API_URL/preview" -H "Content-Type: application/json" -d "{\"transport\":\"$PREVIEW_TRANSPORT\"}")
if [ "$(echo "$PREVIEW_START" | json_get_bool "success")" = "true" ]; then
    log_success "Preview started (transport=$PREVIEW_TRANSPORT)"
else
    log_error "Preview start failed: $PREVIEW_START"
fi

if [ "$PREVIEW_TRANSPORT" = "hls" ]; then
    log_info "Waiting for HLS artifacts (up to 20s)"
    for _ in $(seq 1 20); do
        if [ -f /dev/shm/hls/cam0.m3u8 ] && [ -f /dev/shm/hls/cam1.m3u8 ]; then
            break
        fi
        sleep 1
    done
    if [ -f /dev/shm/hls/cam0.m3u8 ] && [ -f /dev/shm/hls/cam1.m3u8 ]; then
        log_success "HLS playlists generated"
    else
        log_error "Missing HLS playlists in /dev/shm/hls/"
    fi
else
    log_info "Skipping HLS artifact check for transport=$PREVIEW_TRANSPORT"
fi

PREVIEW_STATUS=$(curl -s "$API_URL/preview")
if [ "$(echo "$PREVIEW_STATUS" | json_get_bool "preview_active")" = "true" ]; then
    log_success "Preview status reports active"
else
    log_error "Preview status did not report active: $PREVIEW_STATUS"
fi

PREVIEW_STOP=$(curl -s -X DELETE "$API_URL/preview")
if [ "$(echo "$PREVIEW_STOP" | json_get_bool "success")" = "true" ]; then
    log_success "Preview stopped"
else
    log_error "Preview stop failed: $PREVIEW_STOP"
fi

sleep 2
PIPELINE_STATE=$(curl -s "$API_URL/pipeline-state")
CURRENT_MODE=$(echo "$PIPELINE_STATE" | json_get_str "mode")
if [ "$CURRENT_MODE" = "idle" ]; then
    log_success "Pipeline returned to idle after preview"
else
    log_error "Pipeline did not return to idle after preview: $PIPELINE_STATE"
fi

log_info "Test 3: Recording start/health/stop"
MATCH_ID="quicktest_$(date +%s)"
RECORDING_START=$(curl -s -X POST "$API_URL/recording" -H "Content-Type: application/json" -d "{\"match_id\":\"$MATCH_ID\",\"force\":false,\"process_after_recording\":false}")
if [ "$(echo "$RECORDING_START" | json_get_bool "success")" = "true" ]; then
    log_success "Recording started (match_id=$MATCH_ID)"
else
    log_error "Recording start failed: $RECORDING_START"
fi

log_info "Recording for 12 seconds (past protection window)"
sleep 12

RECORDING_STATUS=$(curl -s "$API_URL/recording")
if [ "$(echo "$RECORDING_STATUS" | json_get_bool "recording")" = "true" ]; then
    log_success "Recording status active"
else
    log_error "Recording status not active: $RECORDING_STATUS"
fi

RECORDING_HEALTH=$(curl -s "$API_URL/recording-health")
if [ "$(echo "$RECORDING_HEALTH" | json_get_bool "healthy")" = "true" ]; then
    log_success "Recording health endpoint reports healthy"
else
    log_warning "Recording health reported issues: $RECORDING_HEALTH"
fi

RECORDING_STOP=$(curl -s -X DELETE "$API_URL/recording?force=false")
if [ "$(echo "$RECORDING_STOP" | json_get_bool "success")" = "true" ]; then
    GRACEFUL_STOP=$(echo "$RECORDING_STOP" | json_get_bool "graceful_stop")
    log_success "Recording stopped (graceful_stop=$GRACEFUL_STOP)"
else
    log_error "Recording stop failed: $RECORDING_STOP"
fi

sleep 2
PIPELINE_STATE=$(curl -s "$API_URL/pipeline-state")
CURRENT_MODE=$(echo "$PIPELINE_STATE" | json_get_str "mode")
if [ "$CURRENT_MODE" = "idle" ]; then
    log_success "Pipeline returned to idle after recording"
else
    log_error "Pipeline did not return to idle after recording: $PIPELINE_STATE"
fi

SEGMENTS_DIR="/mnt/recordings/$MATCH_ID/segments"
if [ -d "$SEGMENTS_DIR" ]; then
    CAM0_COUNT=$(find "$SEGMENTS_DIR" -maxdepth 1 -name "cam0_*.mp4" | wc -l)
    CAM1_COUNT=$(find "$SEGMENTS_DIR" -maxdepth 1 -name "cam1_*.mp4" | wc -l)
    if [ "$CAM0_COUNT" -ge 1 ] && [ "$CAM1_COUNT" -ge 1 ]; then
        log_success "Recording segments created for both cameras"
    else
        log_error "Expected segments for both cameras in $SEGMENTS_DIR"
    fi
else
    log_error "Recording segments directory not found: $SEGMENTS_DIR"
fi

log_info "Test 4: Mutual exclusion (recording blocks preview)"
MUTEX_MATCH_ID="mutex_$(date +%s)"
MUTEX_REC_START=$(curl -s -X POST "$API_URL/recording" -H "Content-Type: application/json" -d "{\"match_id\":\"$MUTEX_MATCH_ID\",\"force\":false,\"process_after_recording\":false}")
if [ "$(echo "$MUTEX_REC_START" | json_get_bool "success")" != "true" ]; then
    log_error "Failed to start mutex recording: $MUTEX_REC_START"
fi
sleep 2

PREVIEW_BODY_FILE=$(mktemp)
PREVIEW_HTTP=$(curl -s -o "$PREVIEW_BODY_FILE" -w "%{http_code}" -X POST "$API_URL/preview" -H "Content-Type: application/json" -d "{\"transport\":\"$PREVIEW_TRANSPORT\"}")
PREVIEW_BODY=$(cat "$PREVIEW_BODY_FILE")
rm -f "$PREVIEW_BODY_FILE"

if [ "$PREVIEW_HTTP" = "400" ] || [ "$PREVIEW_HTTP" = "503" ]; then
    log_success "Preview correctly blocked while recording active (HTTP $PREVIEW_HTTP)"
else
    log_error "Preview should be blocked during recording. HTTP=$PREVIEW_HTTP body=$PREVIEW_BODY"
fi

curl -s -X DELETE "$API_URL/recording?force=true" >/dev/null
sleep 2

echo
echo "============================================================"
echo " All quick tests passed"
echo "============================================================"
echo
log_success "System is aligned with the current API/WS pipeline behavior"

#!/bin/bash
# FootballVision Pro - Quick Functionality Test
# Tests preview and recording functionality

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓ PASS]${NC} $1"; }
log_error() { echo -e "${RED}[✗ FAIL]${NC} $1"; exit 1; }

API_URL="http://localhost:8000/api/v1"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║      FootballVision Pro - Quick Functionality Test      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo

# ============================================================================
# Test 1: API Status
# ============================================================================
log_info "Test 1: Checking API status..."

STATUS=$(curl -s $API_URL/status)
if echo "$STATUS" | grep -q "status"; then
    log_success "API is responding"
    echo "  Response: $STATUS"
else
    log_error "API not responding correctly"
fi

# ============================================================================
# Test 2: Pipeline State
# ============================================================================
log_info "Test 2: Checking pipeline state..."

PIPELINE_STATE=$(curl -s $API_URL/pipeline-state)
CURRENT_MODE=$(echo "$PIPELINE_STATE" | python3 -c "import sys, json; print(json.load(sys.stdin)['mode'])" 2>/dev/null || echo "unknown")

log_success "Pipeline state: $CURRENT_MODE"
echo "  Full state: $PIPELINE_STATE"

if [ "$CURRENT_MODE" != "idle" ]; then
    log_info "Pipeline not idle, attempting to reset..."

    # Try to stop preview
    curl -s -X POST $API_URL/preview/stop > /dev/null 2>&1 || true

    # Try to stop recording
    curl -s -X POST $API_URL/recording/stop > /dev/null 2>&1 || true

    sleep 2
fi

# ============================================================================
# Test 3: Preview Start/Stop
# ============================================================================
log_info "Test 3: Testing preview functionality..."

# Start preview
log_info "Starting preview stream..."
PREVIEW_START=$(curl -s -X POST $API_URL/preview/start \
    -H "Content-Type: application/json" \
    -d '{"resolution": "1080p", "bitrate_mbps": 3}')

if echo "$PREVIEW_START" | grep -q "success\|started"; then
    log_success "Preview started successfully"
else
    log_error "Failed to start preview: $PREVIEW_START"
fi

# Wait for HLS segments
log_info "Waiting for HLS segments to generate..."
sleep 5

# Check if HLS files exist
if ls /dev/shm/hls/*.m3u8 > /dev/null 2>&1; then
    log_success "HLS playlist files generated"
    ls -lh /dev/shm/hls/*.m3u8
else
    log_error "No HLS playlist files found in /dev/shm/hls/"
fi

# Check preview status
PREVIEW_STATUS=$(curl -s $API_URL/preview/status)
log_info "Preview status: $PREVIEW_STATUS"

# Stop preview
log_info "Stopping preview..."
PREVIEW_STOP=$(curl -s -X POST $API_URL/preview/stop)

if echo "$PREVIEW_STOP" | grep -q "success\|stopped"; then
    log_success "Preview stopped successfully"
else
    log_error "Failed to stop preview: $PREVIEW_STOP"
fi

# Verify pipeline returns to idle
sleep 2
PIPELINE_STATE=$(curl -s $API_URL/pipeline-state)
CURRENT_MODE=$(echo "$PIPELINE_STATE" | python3 -c "import sys, json; print(json.load(sys.stdin)['mode'])" 2>/dev/null || echo "unknown")

if [ "$CURRENT_MODE" = "idle" ]; then
    log_success "Pipeline returned to idle state"
else
    log_error "Pipeline did not return to idle (stuck in: $CURRENT_MODE)"
fi

# ============================================================================
# Test 4: Recording Start/Stop
# ============================================================================
log_info "Test 4: Testing recording functionality..."

# Start recording (5 second test)
log_info "Starting 5-second test recording..."
RECORDING_START=$(curl -s -X POST $API_URL/recording/start \
    -H "Content-Type: application/json" \
    -d '{
        "match_id": "test_recording_'$(date +%s)'",
        "duration_minutes": 0.083,
        "bitrate_mbps": 12,
        "enable_barrel_correction": false
    }')

if echo "$RECORDING_START" | grep -q "success\|started\|match_id"; then
    log_success "Recording started successfully"

    # Extract match_id
    MATCH_ID=$(echo "$RECORDING_START" | python3 -c "import sys, json; print(json.load(sys.stdin).get('match_id', 'unknown'))" 2>/dev/null || echo "unknown")
    echo "  Match ID: $MATCH_ID"
else
    log_error "Failed to start recording: $RECORDING_START"
fi

# Wait for recording to complete
log_info "Waiting for recording to complete (5 seconds)..."
sleep 8

# Check recording status
RECORDING_STATUS=$(curl -s $API_URL/recording/status)
log_info "Recording status: $RECORDING_STATUS"

# Check if recording files were created
if [ "$MATCH_ID" != "unknown" ]; then
    RECORDING_DIR="/mnt/recordings/$MATCH_ID"

    if [ -d "$RECORDING_DIR" ]; then
        log_success "Recording directory created: $RECORDING_DIR"

        # Check for MP4 files
        MP4_COUNT=$(find "$RECORDING_DIR" -name "*.mp4" 2>/dev/null | wc -l)
        if [ "$MP4_COUNT" -ge 1 ]; then
            log_success "Found $MP4_COUNT MP4 file(s)"
            find "$RECORDING_DIR" -name "*.mp4" -exec ls -lh {} \;
        else
            log_error "No MP4 files found in recording directory"
        fi
    else
        log_error "Recording directory not found: $RECORDING_DIR"
    fi
fi

# Verify pipeline returns to idle
sleep 2
PIPELINE_STATE=$(curl -s $API_URL/pipeline-state)
CURRENT_MODE=$(echo "$PIPELINE_STATE" | python3 -c "import sys, json; print(json.load(sys.stdin)['mode'])" 2>/dev/null || echo "unknown")

if [ "$CURRENT_MODE" = "idle" ]; then
    log_success "Pipeline returned to idle state after recording"
else
    log_error "Pipeline did not return to idle (stuck in: $CURRENT_MODE)"
fi

# ============================================================================
# Test 5: Mutual Exclusion Verification
# ============================================================================
log_info "Test 5: Testing mutual exclusion (recording blocks preview)..."

# Start recording
log_info "Starting recording..."
curl -s -X POST $API_URL/recording/start \
    -H "Content-Type: application/json" \
    -d '{
        "match_id": "mutex_test_'$(date +%s)'",
        "duration_minutes": 0.05,
        "bitrate_mbps": 12
    }' > /dev/null

sleep 2

# Attempt to start preview (should fail)
log_info "Attempting to start preview while recording (should fail)..."
PREVIEW_ATTEMPT=$(curl -s -X POST $API_URL/preview/start \
    -H "Content-Type: application/json" \
    -d '{"resolution": "1080p", "bitrate_mbps": 3}')

if echo "$PREVIEW_ATTEMPT" | grep -qi "error\|failed\|lock\|503"; then
    log_success "Preview correctly blocked while recording is active"
else
    log_error "MUTUAL EXCLUSION FAILED - Preview should have been blocked!"
fi

# Wait for recording to finish
log_info "Waiting for test recording to finish..."
sleep 5

# ============================================================================
# Summary
# ============================================================================
echo
echo "╔══════════════════════════════════════════════════════════╗"
echo "║              All Tests Passed Successfully!              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo
log_success "FootballVision Pro is functioning correctly"
echo
echo "Test recordings can be found in: /mnt/recordings/"
echo "You can now safely use the system for production recordings."
echo

#!/bin/bash
# FootballVision Pro - Performance Validation Test
# Tests that the system achieves expected framerates and performance

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓ PASS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[⚠ WARN]${NC} $1"; }
log_error() { echo -e "${RED}[✗ FAIL]${NC} $1"; }

API_URL="http://localhost:8000/api/v1"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║      FootballVision Pro - Performance Test              ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo

# ============================================================================
# System Info
# ============================================================================
log_info "System Information:"
echo "  CPU: $(cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d: -f2 | xargs)"
echo "  CPU cores: $(nproc)"
echo "  Memory: $(free -h | grep Mem | awk '{print $2}')"
echo "  JetPack: $(dpkg -l | grep nvidia-jetpack | awk '{print $3}' | head -1 || echo 'Unknown')"
echo

# ============================================================================
# Test 1: Preview HLS Performance
# ============================================================================
log_info "Test 1: Preview HLS segment generation performance..."

# Stop any existing streams
curl -s -X POST $API_URL/preview/stop > /dev/null 2>&1 || true
curl -s -X POST $API_URL/recording/stop > /dev/null 2>&1 || true
sleep 2

# Clean HLS directory
sudo rm -f /dev/shm/hls/*.m3u8 /dev/shm/hls/*.ts 2>/dev/null || true

# Start preview
log_info "Starting preview stream (1080p @ 3Mbps)..."
curl -s -X POST $API_URL/preview/start \
    -H "Content-Type: application/json" \
    -d '{"resolution": "1080p", "bitrate_mbps": 3}' > /dev/null

# Wait for segments to generate
log_info "Waiting 10 seconds for HLS segments..."
sleep 10

# Count segments
CAM1_SEGMENTS=$(ls /dev/shm/hls/cam1_*.ts 2>/dev/null | wc -l)
CAM2_SEGMENTS=$(ls /dev/shm/hls/cam2_*.ts 2>/dev/null | wc -l)

log_info "Camera 1: $CAM1_SEGMENTS segments generated"
log_info "Camera 2: $CAM2_SEGMENTS segments generated"

# Each segment is 2 seconds, so 10 seconds should produce ~5 segments
if [ "$CAM1_SEGMENTS" -ge 4 ] && [ "$CAM2_SEGMENTS" -ge 4 ]; then
    log_success "HLS segments generating at expected rate (~30fps)"
else
    log_warning "Fewer segments than expected (may indicate performance issue)"
fi

# Check CPU usage during preview
log_info "Current CPU usage:"
top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print "  CPU Usage: " 100 - $1 "%"}'

# Get API process CPU usage
API_PID=$(systemctl show -p MainPID footballvision-api-enhanced | cut -d= -f2)
if [ "$API_PID" != "0" ]; then
    API_CPU=$(ps -p $API_PID -o %cpu --no-headers | xargs)
    log_info "API process CPU usage: ${API_CPU}%"
fi

# Stop preview
curl -s -X POST $API_URL/preview/stop > /dev/null
sleep 2

# ============================================================================
# Test 2: Recording Performance
# ============================================================================
log_info "Test 2: Recording performance test (15 seconds @ 12Mbps)..."

MATCH_ID="perftest_$(date +%s)"

# Start recording
log_info "Starting recording..."
START_TIME=$(date +%s)

curl -s -X POST $API_URL/recording/start \
    -H "Content-Type: application/json" \
    -d '{
        "match_id": "'$MATCH_ID'",
        "duration_minutes": 0.25,
        "bitrate_mbps": 12,
        "enable_barrel_correction": false
    }' > /dev/null

# Monitor CPU during recording
log_info "Monitoring CPU usage during recording..."
for i in {1..3}; do
    sleep 5
    CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
    log_info "CPU usage at ${i}0s: ${CPU_USAGE}%"

    if [ "$API_PID" != "0" ]; then
        API_CPU=$(ps -p $API_PID -o %cpu --no-headers | xargs || echo "N/A")
        log_info "API process CPU: ${API_CPU}%"
    fi
done

# Wait for recording to complete
log_info "Waiting for recording to complete..."
sleep 5

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
log_info "Recording duration: ${DURATION} seconds"

# ============================================================================
# Test 3: Analyze Recording Files
# ============================================================================
log_info "Test 3: Analyzing recording output files..."

RECORDING_DIR="/mnt/recordings/$MATCH_ID"

if [ -d "$RECORDING_DIR" ]; then
    log_success "Recording directory exists: $RECORDING_DIR"

    # Find MP4 files
    CAM1_FILE=$(find "$RECORDING_DIR" -name "cam1_*.mp4" | head -1)
    CAM2_FILE=$(find "$RECORDING_DIR" -name "cam2_*.mp4" | head -1)

    # Analyze Camera 1
    if [ -f "$CAM1_FILE" ]; then
        log_info "Analyzing Camera 1 recording..."

        FILE_SIZE=$(stat -f%z "$CAM1_FILE" 2>/dev/null || stat -c%s "$CAM1_FILE")
        FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))
        log_info "File size: ${FILE_SIZE_MB} MB"

        # Use ffprobe to get framerate and frame count if available
        if command -v ffprobe &> /dev/null; then
            FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 "$CAM1_FILE" 2>/dev/null | bc -l 2>/dev/null || echo "N/A")
            FRAMES=$(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of default=noprint_wrappers=1:nokey=1 "$CAM1_FILE" 2>/dev/null || echo "N/A")
            DURATION_SEC=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$CAM1_FILE" 2>/dev/null || echo "N/A")

            log_info "Camera 1 - FPS: $FPS, Frames: $FRAMES, Duration: ${DURATION_SEC}s"

            # Calculate actual framerate
            if [ "$FRAMES" != "N/A" ] && [ "$DURATION_SEC" != "N/A" ]; then
                ACTUAL_FPS=$(echo "$FRAMES / $DURATION_SEC" | bc -l 2>/dev/null | xargs printf "%.1f")
                log_info "Camera 1 - Actual average FPS: $ACTUAL_FPS"

                # Check if close to 30fps (allow 25+ for acceptable)
                FPS_INT=$(echo "$ACTUAL_FPS" | cut -d. -f1)
                if [ "$FPS_INT" -ge 25 ]; then
                    log_success "Camera 1 achieving acceptable framerate (${ACTUAL_FPS} fps)"
                elif [ "$FPS_INT" -ge 15 ]; then
                    log_warning "Camera 1 framerate lower than optimal (${ACTUAL_FPS} fps) - expected 25-30fps"
                else
                    log_error "Camera 1 framerate critically low (${ACTUAL_FPS} fps)"
                fi
            fi
        else
            log_warning "ffprobe not available - cannot analyze video details"
        fi
    else
        log_error "Camera 1 recording file not found"
    fi

    # Analyze Camera 2
    if [ -f "$CAM2_FILE" ]; then
        log_info "Analyzing Camera 2 recording..."

        FILE_SIZE=$(stat -f%z "$CAM2_FILE" 2>/dev/null || stat -c%s "$CAM2_FILE")
        FILE_SIZE_MB=$((FILE_SIZE / 1024 / 1024))
        log_info "File size: ${FILE_SIZE_MB} MB"

        if command -v ffprobe &> /dev/null; then
            FPS=$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 "$CAM2_FILE" 2>/dev/null | bc -l 2>/dev/null || echo "N/A")
            FRAMES=$(ffprobe -v error -select_streams v:0 -count_frames -show_entries stream=nb_read_frames -of default=noprint_wrappers=1:nokey=1 "$CAM2_FILE" 2>/dev/null || echo "N/A")
            DURATION_SEC=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$CAM2_FILE" 2>/dev/null || echo "N/A")

            log_info "Camera 2 - FPS: $FPS, Frames: $FRAMES, Duration: ${DURATION_SEC}s"

            if [ "$FRAMES" != "N/A" ] && [ "$DURATION_SEC" != "N/A" ]; then
                ACTUAL_FPS=$(echo "$FRAMES / $DURATION_SEC" | bc -l 2>/dev/null | xargs printf "%.1f")
                log_info "Camera 2 - Actual average FPS: $ACTUAL_FPS"

                FPS_INT=$(echo "$ACTUAL_FPS" | cut -d. -f1)
                if [ "$FPS_INT" -ge 25 ]; then
                    log_success "Camera 2 achieving acceptable framerate (${ACTUAL_FPS} fps)"
                elif [ "$FPS_INT" -ge 15 ]; then
                    log_warning "Camera 2 framerate lower than optimal (${ACTUAL_FPS} fps) - expected 25-30fps"
                else
                    log_error "Camera 2 framerate critically low (${ACTUAL_FPS} fps)"
                fi
            fi
        fi
    else
        log_error "Camera 2 recording file not found"
    fi

else
    log_error "Recording directory not found: $RECORDING_DIR"
fi

# ============================================================================
# Test 4: System Resource Check
# ============================================================================
log_info "Test 4: System resource availability..."

# Check available disk space
DISK_AVAIL=$(df -h /mnt/recordings | tail -1 | awk '{print $4}')
log_info "Available disk space on /mnt/recordings: $DISK_AVAIL"

# Check available memory
MEM_AVAIL=$(free -h | grep Mem | awk '{print $7}')
log_info "Available memory: $MEM_AVAIL"

# Check swap usage
SWAP_USED=$(free -h | grep Swap | awk '{print $3}')
if [ "$SWAP_USED" != "0B" ]; then
    log_warning "System is using swap: $SWAP_USED (may impact performance)"
else
    log_success "No swap being used"
fi

# ============================================================================
# Summary
# ============================================================================
echo
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           Performance Test Complete                      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo
log_info "Performance test recording saved to: $RECORDING_DIR"
log_info "Review the logs above for any warnings or errors"
echo
echo "Expected performance:"
echo "  - Preview HLS: 30fps for both cameras"
echo "  - Recording: 25-30fps for both cameras at 12Mbps"
echo "  - CPU usage: ~250-350% during recording (2-3 cores)"
echo
echo "Note: Lower framerates during recording may indicate:"
echo "  - CPU being overwhelmed by dual-camera encoding"
echo "  - Disk I/O bottlenecks"
echo "  - Camera daemon (nvargus-daemon) issues"
echo

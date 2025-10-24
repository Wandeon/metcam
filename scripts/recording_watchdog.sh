#!/bin/bash
# Recording Watchdog - Monitors active recordings and auto-recovers from failures

WATCHDOG_LOG="/var/log/footballvision/system/watchdog.log"
SEGMENT_TIMEOUT_MINUTES=10  # Alert if no new segments in 10 minutes
FRAMERATE_THRESHOLD=24     # Alert if fps drops below 24

log_watchdog() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$WATCHDOG_LOG"
}

# Check if recording is supposed to be active
check_recording_status() {
    local api_status=$(curl -s http://localhost/api/v1/status 2>/dev/null)
    if [ -z "$api_status" ]; then
        log_watchdog "ERROR: Cannot reach API"
        return 1
    fi

    echo "$api_status" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data.get('status') == 'recording':
    print('recording')
    print(data.get('match_id', 'unknown'))
else:
    print('idle')
" 2>/dev/null
}

# Monitor segment creation rate
check_segment_creation() {
    local match_id="$1"
    local recordings_dir="/mnt/recordings/$match_id/segments"

    if [ ! -d "$recordings_dir" ]; then
        log_watchdog "ERROR: Recording directory missing for $match_id"
        return 1
    fi

    # Find most recent segment
    local latest_cam0=$(ls -t "$recordings_dir"/cam0_*.mkv 2>/dev/null | head -1)
    local latest_cam1=$(ls -t "$recordings_dir"/cam1_*.mkv 2>/dev/null | head -1)

    if [ -z "$latest_cam0" ] || [ -z "$latest_cam1" ]; then
        log_watchdog "ERROR: No segments found for $match_id"
        return 1
    fi

    # Check age of latest segments
    for segment in "$latest_cam0" "$latest_cam1"; do
        if [ -f "$segment" ]; then
            local age_seconds=$(( $(date +%s) - $(stat -c %Y "$segment") ))
            local age_minutes=$(( age_seconds / 60 ))

            if [ "$age_minutes" -gt "$SEGMENT_TIMEOUT_MINUTES" ]; then
                log_watchdog "WARNING: Segment $(basename "$segment") is ${age_minutes} minutes old (threshold: ${SEGMENT_TIMEOUT_MINUTES})"
                return 1
            fi
        fi
    done

    return 0
}

# Check actual framerate of recent segments
check_framerate() {
    local match_id="$1"
    local recordings_dir="/mnt/recordings/$match_id/segments"

    # Get most recent segment from cam0
    local latest_segment=$(ls -t "$recordings_dir"/cam0_*.mkv 2>/dev/null | head -1)

    if [ -f "$latest_segment" ]; then
        # Extract framerate (this is quick for just checking metadata)
        local fps=$(ffprobe -v error -select_streams v:0 \
            -show_entries stream=avg_frame_rate \
            -of default=noprint_wrappers=1:nokey=1 \
            "$latest_segment" 2>/dev/null | cut -d'/' -f1)

        if [ -n "$fps" ] && [ "$fps" -lt "$FRAMERATE_THRESHOLD" ]; then
            log_watchdog "WARNING: Low framerate detected: ${fps} fps (expected 25)"
            return 1
        fi
    fi

    return 0
}

# Check process health
check_processes() {
    local cam0_pid=$(pgrep -f "gst-launch.*sensor-id=0" | head -1)
    local cam1_pid=$(pgrep -f "gst-launch.*sensor-id=1" | head -1)

    if [ -z "$cam0_pid" ]; then
        log_watchdog "ERROR: Camera 0 process not found"
        return 1
    fi

    if [ -z "$cam1_pid" ]; then
        log_watchdog "ERROR: Camera 1 process not found"
        return 1
    fi

    # Check if processes are actually working (not zombie/hung)
    for pid in "$cam0_pid" "$cam1_pid"; do
        local cpu_usage=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ')
        if [ -z "$cpu_usage" ] || [ "$(echo "$cpu_usage < 10" | bc)" -eq 1 ]; then
            log_watchdog "WARNING: Process $pid has low CPU usage: ${cpu_usage}%"
            return 1
        fi
    done

    return 0
}

# Attempt to recover recording
attempt_recovery() {
    local match_id="$1"

    log_watchdog "RECOVERY: Attempting to recover recording for $match_id"

    # Step 1: Stop current recording gracefully
    curl -X DELETE http://localhost/api/v1/recording 2>/dev/null
    sleep 5

    # Step 2: Kill any lingering processes
    pkill -INT -f "gst-launch.*nvarguscamerasrc" 2>/dev/null
    sleep 2
    pkill -9 -f "gst-launch.*nvarguscamerasrc" 2>/dev/null

    # Step 3: Wait a moment for cleanup
    sleep 3

    # Step 4: Restart recording with same match_id
    local restart_response=$(curl -X POST http://localhost/api/v1/recording \
        -H 'Content-Type: application/json' \
        -d "{\"match_id\":\"${match_id}_recovered_$(date +%Y%m%d_%H%M%S)\"}" 2>/dev/null)

    if echo "$restart_response" | grep -q "recording"; then
        log_watchdog "RECOVERY: Successfully restarted recording"
        return 0
    else
        log_watchdog "RECOVERY: Failed to restart recording: $restart_response"
        return 1
    fi
}

# Main watchdog loop iteration
watchdog_check() {
    # Get current status
    local status_output=$(check_recording_status)
    local status=$(echo "$status_output" | head -1)
    local match_id=$(echo "$status_output" | tail -1)

    if [ "$status" == "recording" ]; then
        log_watchdog "Checking recording: $match_id"

        local errors=0

        # Run all checks
        if ! check_processes; then
            ((errors++))
            log_watchdog "Process check failed"
        fi

        if ! check_segment_creation "$match_id"; then
            ((errors++))
            log_watchdog "Segment creation check failed"
        fi

        if ! check_framerate "$match_id"; then
            ((errors++))
            log_watchdog "Framerate check failed"
        fi

        # If multiple checks fail, attempt recovery
        if [ "$errors" -ge 2 ]; then
            log_watchdog "Multiple failures detected ($errors), initiating recovery"
            attempt_recovery "$match_id"
        elif [ "$errors" -eq 1 ]; then
            log_watchdog "Single failure detected, monitoring closely"
        else
            log_watchdog "All checks passed for $match_id"
        fi
    else
        # Not recording, just ensure no orphan processes
        local orphans=$(pgrep -f "gst-launch.*nvarguscamerasrc")
        if [ -n "$orphans" ]; then
            log_watchdog "Found orphan recording processes while idle: $orphans"
            kill -INT $orphans 2>/dev/null
            sleep 2
            kill -9 $orphans 2>/dev/null
        fi
    fi
}

# Run single check
mkdir -p "$(dirname "$WATCHDOG_LOG")"
watchdog_check

exit 0
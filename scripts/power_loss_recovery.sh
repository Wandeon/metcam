#!/bin/bash
# FootballVision Pro Power Loss Recovery Script
# Handles recovery after unexpected power loss or system crash

RECOVERY_LOG="/var/log/footballvision/crashes/recovery_$(date +%Y%m%d_%H%M%S).log"
RECORDINGS_DIR="/mnt/recordings"
RECOVERY_MARKER="/var/run/footballvision_recovery"

# Ensure log directory exists
mkdir -p "$(dirname "$RECOVERY_LOG")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$RECOVERY_LOG"
}

# Check if we're in recovery mode (system just booted)
check_recovery_needed() {
    local uptime_seconds=$(awk '{print int($1)}' /proc/uptime)

    # If system uptime < 5 minutes, we just booted
    if [ "$uptime_seconds" -lt 300 ]; then
        log "System just booted (uptime: ${uptime_seconds}s) - checking for recovery needs"
        return 0
    fi
    return 1
}

# Find incomplete recordings
find_incomplete_recordings() {
    log "Searching for incomplete recordings..."

    # Look for recordings without completion markers
    for match_dir in "$RECORDINGS_DIR"/*; do
        if [ -d "$match_dir/segments" ]; then
            local match_id=$(basename "$match_dir")

            # Check if recording was properly stopped (manifest exists)
            if [ ! -f "$match_dir/upload_manifest.json" ]; then
                log "Found incomplete recording: $match_id"

                # Check segment timestamps
                local last_segment=$(ls -t "$match_dir/segments/"*.mkv 2>/dev/null | head -1)
                if [ -n "$last_segment" ]; then
                    local last_modified=$(stat -c %Y "$last_segment")
                    local current_time=$(date +%s)
                    local age_seconds=$((current_time - last_modified))
                    local age_minutes=$((age_seconds / 60))

                    log "  Last segment: $(basename "$last_segment")"
                    log "  Age: ${age_minutes} minutes"

                    # Create recovery manifest
                    create_recovery_manifest "$match_dir" "$age_minutes"
                fi
            fi
        fi
    done
}

# Create recovery manifest for incomplete recording
create_recovery_manifest() {
    local match_dir="$1"
    local age_minutes="$2"
    local match_id=$(basename "$match_dir")

    cat > "$match_dir/recovery_info.json" << EOF
{
    "match_id": "$match_id",
    "recovery_time": "$(date -Iseconds)",
    "recording_age_minutes": $age_minutes,
    "status": "recovered_incomplete",
    "segments": {
        "cam0": $(ls "$match_dir/segments/cam0_"*.mkv 2>/dev/null | wc -l),
        "cam1": $(ls "$match_dir/segments/cam1_"*.mkv 2>/dev/null | wc -l)
    },
    "total_size_mb": $(du -sm "$match_dir" | cut -f1),
    "recovery_reason": "power_loss_or_crash"
}
EOF

    log "Created recovery manifest for $match_id"
}

# Verify and fix file integrity
verify_segments() {
    local match_dir="$1"

    log "Verifying segment integrity in $match_dir..."

    for segment in "$match_dir/segments/"*.mkv; do
        if [ -f "$segment" ]; then
            # Check if file is readable and has proper ending
            if ! ffprobe -v error "$segment" 2>/dev/null; then
                log "  WARNING: Corrupted segment: $(basename "$segment")"
                # Mark as corrupted
                mv "$segment" "${segment}.corrupted"
            fi
        fi
    done
}

# System configuration recovery
restore_system_config() {
    log "Restoring system configuration..."

    # 1. Set power mode to 25W
    local current_mode=$(nvpmodel -q | grep "NV Power Mode" | awk '{print $4}')
    if [ "$current_mode" != "1" ]; then
        log "  Setting power mode to 25W (was mode $current_mode)"
        sudo nvpmodel -m 1
    fi

    # 2. Set CPU governor to performance
    for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
        if [ -f "$cpu" ]; then
            echo "performance" | sudo tee "$cpu" >/dev/null
        fi
    done
    log "  CPU governor set to performance"

    # 3. Clear HLS cache (might have corrupted segments)
    if [ -d "/var/www/hls" ]; then
        sudo rm -rf /var/www/hls/*
        log "  Cleared HLS cache"
    fi

    # 4. Ensure recording directory permissions
    sudo chown -R mislav:mislav "$RECORDINGS_DIR"
    log "  Fixed recording directory permissions"
}

# Check and restart services
check_services() {
    log "Checking critical services..."

    # API service
    if ! systemctl is-active --quiet footballvision-api-enhanced; then
        log "  API service not running - starting..."
        sudo systemctl start footballvision-api-enhanced
        sleep 5
    else
        log "  API service is running"
    fi

    # Check if any stale recording processes
    local stale_recordings=$(pgrep -f "gst-launch.*nvarguscamerasrc")
    if [ -n "$stale_recordings" ]; then
        log "  Found stale recording processes: $stale_recordings"
        log "  Killing stale processes..."
        kill -INT $stale_recordings 2>/dev/null
        sleep 2
        kill -9 $stale_recordings 2>/dev/null
    fi
}

# Send notification of recovery
notify_recovery() {
    local incomplete_count=$(find "$RECORDINGS_DIR" -name "recovery_info.json" | wc -l)

    if [ "$incomplete_count" -gt 0 ]; then
        log "RECOVERY COMPLETE: Found $incomplete_count incomplete recordings"

        # Create system notification
        cat > "/var/log/footballvision/system/last_recovery.txt" << EOF
Recovery completed at $(date)
Incomplete recordings found: $incomplete_count
Check recovery logs at: $RECOVERY_LOG

Affected recordings:
$(find "$RECORDINGS_DIR" -name "recovery_info.json" -exec dirname {} \; | xargs -n1 basename)
EOF
    else
        log "RECOVERY COMPLETE: No incomplete recordings found"
    fi
}

# Main recovery process
main() {
    log "=== FootballVision Pro Recovery Process Started ==="

    # Only run if system just booted or recovery marker exists
    if check_recovery_needed || [ -f "$RECOVERY_MARKER" ]; then
        log "Recovery mode activated"

        # Step 1: Find and mark incomplete recordings
        find_incomplete_recordings

        # Step 2: Verify segment integrity
        for match_dir in "$RECORDINGS_DIR"/*; do
            if [ -f "$match_dir/recovery_info.json" ]; then
                verify_segments "$match_dir"
            fi
        done

        # Step 3: Restore system configuration
        restore_system_config

        # Step 4: Check and restart services
        check_services

        # Step 5: Notify
        notify_recovery

        # Remove recovery marker
        rm -f "$RECOVERY_MARKER"

        log "=== Recovery Process Complete ==="
    else
        log "No recovery needed (system uptime > 5 minutes)"
    fi
}

# Run recovery
main

exit 0
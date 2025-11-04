#!/bin/bash
# FootballVision Pro System Health Monitor
# Monitors critical system parameters and takes action on issues

LOG_FILE="/var/log/footballvision/system/health_monitor.log"
ALERT_FILE="/var/log/footballvision/system/alerts.log"
RECORDINGS_DIR="/mnt/recordings"
MIN_FREE_GB=20
MAX_TEMP_C=75
POWER_MODE_REQUIRED=2  # MAXN_SUPER mode for maximum performance

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Logging function
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

alert() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ALERT: $1" | tee -a "$ALERT_FILE"
    # Could send email/notification here
}

# 1. Check Storage Space
check_storage() {
    local free_gb=$(df /mnt/recordings | awk 'NR==2 {print int($4/1024/1024)}')
    local usage_percent=$(df /mnt/recordings | awk 'NR==2 {print int($5)}')

    if [ "$free_gb" -lt "$MIN_FREE_GB" ]; then
        alert "Low storage: ${free_gb}GB free (minimum: ${MIN_FREE_GB}GB)"

        # Auto-cleanup old test recordings
        find "$RECORDINGS_DIR" -maxdepth 1 -type d -name "*test*" -mtime +7 -exec rm -rf {} \; 2>/dev/null

        # If still low, stop recording
        if [ "$free_gb" -lt 10 ]; then
            alert "Critical storage! Stopping recording if active"
            curl -X DELETE http://localhost/api/v1/recording 2>/dev/null
        fi
    fi

    log_message "Storage: ${free_gb}GB free (${usage_percent}% used)"
}

# 2. Check Temperature
check_temperature() {
    local max_temp=0
    for zone in /sys/class/thermal/thermal_zone*/temp; do
        if [ -f "$zone" ]; then
            temp=$(cat "$zone")
            temp_c=$((temp / 1000))
            if [ "$temp_c" -gt "$max_temp" ]; then
                max_temp=$temp_c
            fi
        fi
    done

    if [ "$max_temp" -gt "$MAX_TEMP_C" ]; then
        alert "High temperature: ${max_temp}°C (max: ${MAX_TEMP_C}°C)"

        # If critical (>80°C), stop recording
        if [ "$max_temp" -gt 80 ]; then
            alert "Critical temperature! Stopping recording"
            curl -X DELETE http://localhost/api/v1/recording 2>/dev/null
        fi
    fi

    log_message "Temperature: ${max_temp}°C"
}

# 3. Check Power Mode
check_power_mode() {
    # Get the numeric mode ID (second line of nvpmodel -q output)
    local current_mode=$(nvpmodel -q | tail -1)
    local current_mode_name=$(nvpmodel -q | grep "NV Power Mode" | awk '{print $4}')

    if [ "$current_mode" != "$POWER_MODE_REQUIRED" ]; then
        alert "Wrong power mode: mode $current_mode ($current_mode_name) - expected mode $POWER_MODE_REQUIRED"
        # Auto-fix
        sudo nvpmodel -m "$POWER_MODE_REQUIRED"
        log_message "Power mode corrected to $POWER_MODE_REQUIRED"
    fi
}

# 4. Check Camera Connectivity
check_cameras() {
    local cam0_exists=$(ls /dev/video0 2>/dev/null)
    local cam1_exists=$(ls /dev/video1 2>/dev/null)

    if [ -z "$cam0_exists" ] || [ -z "$cam1_exists" ]; then
        alert "Camera disconnected! Cam0: ${cam0_exists:-missing}, Cam1: ${cam1_exists:-missing}"
    fi
}

# 5. Check Recording Process Health
check_recording_health() {
    local status=$(curl -s http://localhost/api/v1/status 2>/dev/null | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('status','unknown'))" 2>/dev/null)

    if [ "$status" == "recording" ]; then
        # Check if processes are actually running
        local cam0_pid=$(pgrep -f "gst-launch.*sensor-id=0" | head -1)
        local cam1_pid=$(pgrep -f "gst-launch.*sensor-id=1" | head -1)

        if [ -z "$cam0_pid" ] || [ -z "$cam1_pid" ]; then
            alert "Recording state mismatch! API says recording but processes missing"
            # Force stop and cleanup
            curl -X DELETE http://localhost/api/v1/recording 2>/dev/null
        fi

        # Check for stalled recordings (no new segments in 10 minutes)
        local latest_segment=$(find "$RECORDINGS_DIR" -name "*.mkv" -type f -mmin -10 2>/dev/null | head -1)
        if [ -z "$latest_segment" ] && [ "$status" == "recording" ]; then
            alert "Recording stalled! No new segments in 10 minutes"
        fi
    fi
}

# 6. Check CPU Frequency (throttling detection)
check_cpu_frequency() {
    local min_freq=1728000  # 1.728 GHz is max for Jetson Orin Nano Super
    # Check only performance cores (CPUs 0-3), CPUs 4-5 are efficiency cores
    local total_freq=0
    local count=0

    for cpu in 0 1 2 3; do
        local freq=$(cat /sys/devices/system/cpu/cpu${cpu}/cpufreq/scaling_cur_freq 2>/dev/null)
        if [ -n "$freq" ]; then
            total_freq=$((total_freq + freq))
            count=$((count + 1))
        fi
    done

    if [ "$count" -gt 0 ]; then
        local avg_freq=$((total_freq / count))
        if [ "$avg_freq" -lt "$min_freq" ]; then
            local freq_ghz=$(echo "scale=2; $avg_freq / 1000000" | bc)
            alert "Performance CPU throttling detected: ${freq_ghz}GHz avg (expected 1.728GHz)"
        fi
    fi
}

# 7. Check Network (for uploads)
check_network() {
    # Ping gateway
    local gateway=$(ip route | awk '/default/ {print $3}' | head -1)
    if [ -n "$gateway" ]; then
        if ! ping -c 1 -W 2 "$gateway" >/dev/null 2>&1; then
            log_message "Network unreachable (gateway: $gateway)"
        fi
    fi
}

# 8. Check API Service
check_api_service() {
    # Check which service is active (production or development)
    local prod_active=$(systemctl is-active footballvision-api-enhanced 2>/dev/null)
    local dev_active=$(systemctl is-active footballvision-api-dev 2>/dev/null)

    if [ "$prod_active" == "active" ]; then
        log_message "API service status: production active"
    elif [ "$dev_active" == "active" ]; then
        log_message "API service status: development active"
    else
        # Neither service is running - this is a problem
        # Only auto-restart production if it's enabled (not in development mode)
        if systemctl is-enabled --quiet footballvision-api-enhanced 2>/dev/null; then
            alert "API service is not running! Attempting to restart production..."
            sudo systemctl restart footballvision-api-enhanced
            sleep 5

            if ! systemctl is-active --quiet footballvision-api-enhanced; then
                alert "Failed to restart API service!"
            else
                log_message "API service restarted successfully"
            fi
        else
            log_message "API service not running (development mode, skipping auto-restart)"
        fi
    fi
}

# Main monitoring loop
main() {
    log_message "=== System Health Check Started ==="

    check_api_service
    check_storage
    check_temperature
    check_power_mode
    check_cameras
    check_recording_health
    check_cpu_frequency
    check_network

    log_message "=== Health Check Complete ==="
}

# Run the check
main

# Exit with appropriate code
if [ -f "$ALERT_FILE" ] && [ "$(find "$ALERT_FILE" -mmin -5 2>/dev/null)" ]; then
    exit 1  # Recent alerts
else
    exit 0  # All good
fi
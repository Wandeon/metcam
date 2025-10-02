#!/bin/bash
# System watchdog - monitors critical services

SERVICES=("footballvision-api" "nginx")
LOG_FILE="/var/log/footballvision/watchdog.log"

# Create log directory if needed
sudo mkdir -p /var/log/footballvision
sudo chmod 755 /var/log/footballvision

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | sudo tee -a $LOG_FILE
}

check_service() {
    local service=$1
    if ! systemctl is-active --quiet $service; then
        log "⚠ Service $service is down, restarting..."
        sudo systemctl restart $service
        sleep 2
        if systemctl is-active --quiet $service; then
            log "✓ Service $service restarted successfully"
        else
            log "✗ Failed to restart $service"
        fi
    fi
}

log "Watchdog started - monitoring: ${SERVICES[*]}"

while true; do
    for service in "${SERVICES[@]}"; do
        check_service $service
    done
    sleep 30
done

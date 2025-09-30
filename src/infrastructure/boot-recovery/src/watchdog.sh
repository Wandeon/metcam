#!/bin/bash
# System Watchdog - Monitors critical services and restarts on failure

SERVICES=("nvargus-daemon" "thermal-monitor" "network-optimization")
LOG="/var/log/watchdog.log"

log() {
    echo "[$(date)] $1" | tee -a $LOG
}

check_service() {
    if ! systemctl is-active --quiet $1; then
        log "Service $1 failed, restarting..."
        systemctl restart $1
    fi
}

log "Watchdog started"

while true; do
    for service in "${SERVICES[@]}"; do
        check_service $service
    done
    sleep 30
done
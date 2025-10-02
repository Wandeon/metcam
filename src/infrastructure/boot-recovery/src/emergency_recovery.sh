#!/bin/bash
# Emergency recovery script for FootballVision Pro

echo "=========================================="
echo "FootballVision Pro - Emergency Recovery"
echo "=========================================="

# 1. Stop all services
echo "[1/5] Stopping all services..."
sudo systemctl stop footballvision-api nginx watchdog 2>/dev/null || true

# 2. Check disk space
echo "[2/5] Checking disk space..."
FREE_SPACE=$(df -h /mnt/recordings | awk 'NR==2 {print $4}')
echo "  Available space: $FREE_SPACE"

if [ $(df /mnt/recordings | awk 'NR==2 {print $5}' | sed 's/%//') -gt 95 ]; then
    echo "  WARNING: Low disk space, cleaning old recordings..."
    find /mnt/recordings -name "*.mp4" -type f -mtime +7 -delete
fi

# 3. Check camera devices
echo "[3/5] Checking camera devices..."
CAMERAS=$(ls /dev/video* 2>/dev/null | wc -l)
echo "  Cameras detected: $CAMERAS"

if [ $CAMERAS -lt 2 ]; then
    echo "  WARNING: Expected 2 cameras, found $CAMERAS"
    echo "  Attempting to reload camera driver..."
    sudo modprobe -r v4l2_common 2>/dev/null || true
    sudo modprobe v4l2_common 2>/dev/null || true
    sleep 2
fi

# 4. Reset network
echo "[4/5] Resetting network configuration..."
sudo /home/mislav/footballvision-pro/src/infrastructure/network-optimization/scripts/optimize-network.sh 2>/dev/null || true

# 5. Restart services
echo "[5/5] Restarting services..."
sudo systemctl start footballvision-api
sudo systemctl start nginx

sleep 3

# Verify
echo ""
echo "=========================================="
echo "Recovery Status:"
echo "=========================================="
systemctl is-active footballvision-api >/dev/null && echo "✓ API Service: Running" || echo "✗ API Service: Failed"
systemctl is-active nginx >/dev/null && echo "✓ Nginx: Running" || echo "✗ Nginx: Failed"
curl -s http://localhost:8000/api/v1/status >/dev/null && echo "✓ API Endpoint: Responding" || echo "✗ API Endpoint: Not responding"
echo ""
echo "Recovery procedure complete"

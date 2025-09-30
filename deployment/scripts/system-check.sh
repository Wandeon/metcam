#!/bin/bash
# System Health Check and Validation Script

set -e

echo "FootballVision Pro - System Health Check"
echo "========================================="

# Check 1: System Information
echo -e "\n[System Information]"
echo "Platform: $(cat /etc/nv_tegra_release 2>/dev/null || echo 'Not Jetson')"
echo "OS: $(lsb_release -d | cut -f2)"
echo "Kernel: $(uname -r)"

# Check 2: Resources
echo -e "\n[Resources]"
echo "RAM: $(free -h | awk 'NR==2 {print $2}') total, $(free -h | awk 'NR==2 {print $3}') used"
echo "Storage: $(df -h / | awk 'NR==2 {print $4}') available"
echo "Temperature: $(cat /sys/devices/virtual/thermal/thermal_zone0/temp 2>/dev/null | awk '{print $1/1000 "°C"}' || echo 'N/A')"

# Check 3: Network
echo -e "\n[Network]"
if ping -c 1 google.com >/dev/null 2>&1; then
    echo "✓ Internet: Connected"
else
    echo "⚠ Internet: Disconnected"
fi
echo "IP Address: $(hostname -I | awk '{print $1}')"

# Check 4: Cameras
echo -e "\n[Cameras]"
CAMERAS=$(v4l2-ctl --list-devices 2>/dev/null | grep -c imx477 || echo 0)
if [ "$CAMERAS" -ge 2 ]; then
    echo "✓ Cameras: $CAMERAS detected"
else
    echo "⚠ Cameras: Only $CAMERAS detected (need 2)"
fi

# Check 5: Services
echo -e "\n[Services]"
if systemctl is-active --quiet footballvision.service; then
    echo "✓ FootballVision: Running"
else
    echo "✗ FootballVision: Not running"
fi

# Check 6: Storage Health
echo -e "\n[Storage Health]"
STORAGE_USED=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$STORAGE_USED" -lt 80 ]; then
    echo "✓ Storage: $STORAGE_USED% used (healthy)"
else
    echo "⚠ Storage: $STORAGE_USED% used (consider cleanup)"
fi

echo -e "\n========================================="
echo "Health check complete"
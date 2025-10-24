#!/bin/bash
# Run after boot to verify system is ready

echo "=== FootballVision Pro Boot Verification ==="

# Wait for system to stabilize
sleep 10

# Check power mode
power_mode=$(nvpmodel -q | grep "NV Power Mode" | awk '{print $4}')
if [ "$power_mode" == "1" ]; then
    echo "✓ Power mode: 25W"
else
    echo "✗ Power mode: $power_mode (should be 1)"
    sudo nvpmodel -m 1
fi

# Check API service
if systemctl is-active --quiet footballvision-api-enhanced; then
    echo "✓ API service: Running"
else
    echo "✗ API service: Not running"
    sudo systemctl start footballvision-api-enhanced
fi

# Check cameras
if [ -e /dev/video0 ] && [ -e /dev/video1 ]; then
    echo "✓ Cameras: Both detected"
else
    echo "✗ Cameras: Missing devices"
fi

# Check storage
free_gb=$(df /mnt/recordings | awk 'NR==2 {print int($4/1024/1024)}')
echo "✓ Storage: ${free_gb}GB free"

# Check temperature
max_temp=$(cat /sys/class/thermal/thermal_zone*/temp | sort -n | tail -1)
temp_c=$((max_temp / 1000))
echo "✓ Temperature: ${temp_c}°C"

echo "=== Boot Verification Complete ==="

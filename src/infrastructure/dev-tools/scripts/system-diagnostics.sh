#!/bin/bash
# System diagnostics and health check

echo "=========================================="
echo "  FootballVision System Diagnostics"
echo "=========================================="
echo ""

# Hardware info
echo "=== Hardware ==="
echo "CPU: $(nproc) cores"
echo "Memory: $(free -h | grep Mem | awk '{print $2}')"
echo "GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"
echo "Storage: $(df -h /mnt/recordings | tail -1 | awk '{print $2 " total, " $4 " free"}')"
echo ""

# Cameras
echo "=== Cameras ==="
ls -l /dev/video* 2>/dev/null || echo "No cameras detected"
echo ""

# Temperature
echo "=== Temperature ==="
for zone in /sys/class/thermal/thermal_zone*/temp; do
    temp=$(($(cat $zone) / 1000))
    echo "$(basename $(dirname $zone)): ${temp}°C"
done
echo ""

# Services
echo "=== Services ==="
systemctl is-active nvargus-daemon thermal-monitor recording
echo ""

# Performance
echo "=== Performance ==="
echo "CPU Frequency: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq) kHz"
echo "GPU Frequency: $(cat /sys/kernel/debug/bpmp/debug/clk/gpu/rate 2>/dev/null || echo 'N/A')"
echo ""

echo "Diagnostics complete"
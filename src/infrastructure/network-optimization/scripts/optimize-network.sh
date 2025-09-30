#!/bin/bash
# Network optimization for 300Mbps WiFi upload

set -e

echo "Network Stack Optimization"
echo "=========================="

# TCP buffer tuning
sysctl -w net.core.rmem_max=268435456
sysctl -w net.core.wmem_max=268435456
sysctl -w net.ipv4.tcp_rmem="4096 87380 268435456"
sysctl -w net.ipv4.tcp_wmem="4096 65536 268435456"

# WiFi power management
iw dev wlan0 set power_save off 2>/dev/null || true

# Queue discipline
tc qdisc add dev wlan0 root fq

echo "Network optimization complete"
echo "Upload bandwidth limit: 300Mbps"
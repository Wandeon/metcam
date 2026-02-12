#!/bin/bash
# Setup script for FootballVision Pro resilience features

set -e

echo "=== FootballVision Pro Resilience Setup ==="

# 1. Make scripts executable
echo "Setting script permissions..."
chmod +x /home/mislav/footballvision-pro/scripts/system_health_monitor.sh
chmod +x /home/mislav/footballvision-pro/scripts/power_loss_recovery.sh
chmod +x /home/mislav/footballvision-pro/scripts/recording_watchdog.sh

# 2. Create log directories
echo "Creating log directories..."
sudo mkdir -p /var/log/footballvision/{api,system,crashes,uploads,processing}
sudo chown -R mislav:mislav /var/log/footballvision

# 3. Install improved systemd service
echo "Installing resilient systemd service..."
sudo cp /home/mislav/footballvision-pro/deploy/systemd/footballvision-api-enhanced.service \
    /etc/systemd/system/footballvision-api-enhanced.service
sudo systemctl daemon-reload
sudo systemctl enable footballvision-api-enhanced
sudo systemctl reset-failed footballvision-api-enhanced || true

# 4. Setup cron jobs for monitoring
echo "Setting up cron jobs..."

# Add crontab entries (without duplicates)
(crontab -l 2>/dev/null | grep -v "footballvision" || true; cat << EOF
# FootballVision Pro System Monitoring
*/5 * * * * /home/mislav/footballvision-pro/scripts/system_health_monitor.sh >/dev/null 2>&1
*/2 * * * * /home/mislav/footballvision-pro/scripts/recording_watchdog.sh >/dev/null 2>&1

# Daily cleanup of old test recordings (3 AM)
0 3 * * * find /mnt/recordings -maxdepth 1 -type d -name "*test*" -mtime +7 -exec rm -rf {} \; >/dev/null 2>&1

# Weekly log rotation (Sunday 2 AM)
0 2 * * 0 find /var/log/footballvision -name "*.log" -size +100M -exec gzip {} \; >/dev/null 2>&1

# Boot-time recovery check
@reboot sleep 30 && /home/mislav/footballvision-pro/scripts/power_loss_recovery.sh >/dev/null 2>&1
EOF
) | crontab -

# 5. Setup log rotation
echo "Configuring log rotation..."
sudo tee /etc/logrotate.d/footballvision > /dev/null << EOF
/var/log/footballvision/*/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 mislav mislav
    sharedscripts
    postrotate
        systemctl reload footballvision-api-enhanced 2>/dev/null || true
    endscript
}
EOF

# 6. Configure kernel parameters for stability
echo "Setting kernel parameters..."
sudo tee /etc/sysctl.d/99-footballvision.conf > /dev/null << EOF
# FootballVision Pro Optimizations

# Increase inotify limits for file monitoring
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 512

# Network optimizations
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728

# Reduce swappiness (prefer RAM)
vm.swappiness = 10

# Increase file handle limits
fs.file-max = 2097152
EOF
sudo sysctl -p /etc/sysctl.d/99-footballvision.conf

# 7. Setup systemd journal persistence
echo "Configuring journal persistence..."
sudo mkdir -p /var/log/journal
sudo systemd-tmpfiles --create --prefix /var/log/journal
sudo systemctl restart systemd-journald

# 8. Create startup verification script
cat > /home/mislav/footballvision-pro/scripts/verify_boot.sh << 'VERIFY_EOF'
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
VERIFY_EOF
chmod +x /home/mislav/footballvision-pro/scripts/verify_boot.sh

# 9. Create system status command
cat > /home/mislav/footballvision-pro/scripts/fv_status << 'STATUS_EOF'
#!/bin/bash
# Quick system status check

echo "=== FootballVision Pro Status ==="
echo ""
echo "System:"
echo "  Uptime: $(uptime -p)"
echo "  Power Mode: $(nvpmodel -q | grep "NV Power Mode")"
echo "  CPU Freq: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq) Hz"
echo "  Temperature: $(echo "scale=1; $(cat /sys/class/thermal/thermal_zone0/temp) / 1000" | bc)°C"
echo ""
echo "Storage:"
df -h /mnt/recordings | tail -1 | awk '{print "  Used: "$3" / "$2" ("$5" full)"}'
echo "  Recordings: $(find /mnt/recordings -maxdepth 1 -type d | wc -l) matches"
echo ""
echo "Services:"
echo -n "  API: "
systemctl is-active footballvision-api-enhanced
echo ""
echo "Recording:"
curl -s http://localhost/api/v1/status 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if data.get('status') == 'recording':
        print(f'  Status: RECORDING')
        print(f'  Match: {data.get(\"match_id\")}')
        print(f'  Duration: {int(data.get(\"duration_seconds\", 0)) // 60} minutes')
    else:
        print('  Status: Idle')
except:
    print('  Status: Unknown (API error)')
" 2>/dev/null
echo ""
echo "Recent Alerts:"
tail -5 /var/log/footballvision/system/alerts.log 2>/dev/null | sed 's/^/  /'
STATUS_EOF
chmod +x /home/mislav/footballvision-pro/scripts/fv_status
sudo ln -sf /home/mislav/footballvision-pro/scripts/fv_status /usr/local/bin/fv_status

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Resilience features installed:"
echo "  ✓ Health monitoring (every 5 minutes)"
echo "  ✓ Recording watchdog (every 2 minutes)"
echo "  ✓ Power loss recovery (on boot)"
echo "  ✓ Automatic cleanup (daily)"
echo "  ✓ Log rotation (daily/weekly)"
echo "  ✓ Service auto-restart"
echo "  ✓ System status command: fv_status"
echo ""
echo "To verify setup:"
echo "  1. Run: fv_status"
echo "  2. Check cron: crontab -l"
echo "  3. Check logs: ls -la /var/log/footballvision/"
echo ""
echo "Restart system to fully activate all features."

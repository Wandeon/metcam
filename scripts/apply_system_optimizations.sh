#!/bin/bash
# FootballVision Pro - System Optimization Script
# Applies system-level optimizations for stable 1080p 30fps recording

set -euo pipefail

echo "=== FootballVision Pro System Optimization ==="
echo "Applying optimizations for stable 1080p 30fps recording..."
echo

# 1. Set MAXN power mode (25W)
echo "Setting MAXN power mode..."
sudo nvpmodel -m 1 2>/dev/null || echo "  Already in MAXN mode"

# 2. Enable jetson_clocks for maximum performance
echo "Enabling jetson_clocks..."
sudo jetson_clocks 2>/dev/null || echo "  jetson_clocks already enabled"

# 3. Switch CPU governor to performance mode
echo "Setting CPU governor to performance mode..."
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    if [ -f "$cpu" ]; then
        echo performance | sudo tee "$cpu" > /dev/null
    fi
done
echo "  CPU governor set to: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"

# 4. Set minimum CPU frequency to 1.5GHz (from 1.344GHz)
echo "Setting minimum CPU frequency to 1.5GHz..."
for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_min_freq; do
    if [ -f "$cpu" ]; then
        echo 1500000 | sudo tee "$cpu" > /dev/null 2>&1 || true
    fi
done
echo "  Min frequency set to: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq) Hz"

# 5. Reduce swappiness for better memory performance
echo "Reducing swappiness to 10..."
echo 10 | sudo tee /proc/sys/vm/swappiness > /dev/null
echo "  Swappiness set to: $(cat /proc/sys/vm/swappiness)"

# 6. Increase shared memory limits
echo "Increasing shared memory limits..."
echo 2147483648 | sudo tee /proc/sys/kernel/shmmax > /dev/null
echo 2097152 | sudo tee /proc/sys/kernel/shmall > /dev/null
echo "  shmmax: $(cat /proc/sys/kernel/shmmax)"
echo "  shmall: $(cat /proc/sys/kernel/shmall)"

# 7. Configure real-time scheduler for better performance
echo "Configuring real-time scheduler..."
echo -1 | sudo tee /proc/sys/kernel/sched_rt_runtime_us > /dev/null 2>&1 || \
    echo 980000 | sudo tee /proc/sys/kernel/sched_rt_runtime_us > /dev/null
echo "  RT runtime: $(cat /proc/sys/kernel/sched_rt_runtime_us) us"

# 8. Disable CPU frequency boost delays
echo "Optimizing CPU frequency scaling..."
for cpu in /sys/devices/system/cpu/cpufreq/policy*/scaling_governor; do
    if [ -f "${cpu%/*}/scaling_up_rate_limit_us" ]; then
        echo 1000 | sudo tee "${cpu%/*}/scaling_up_rate_limit_us" > /dev/null 2>&1 || true
        echo 1000 | sudo tee "${cpu%/*}/scaling_down_rate_limit_us" > /dev/null 2>&1 || true
    fi
done

# 9. Set interrupt affinity to avoid recording cores
echo "Optimizing interrupt affinity..."
# Move interrupts away from cores 1-4 (used for recording)
for irq in /proc/irq/*/smp_affinity_list; do
    if [ -w "$irq" ]; then
        echo "0,5" | sudo tee "$irq" > /dev/null 2>&1 || true
    fi
done

# 10. Increase file descriptor limits
echo "Increasing file descriptor limits..."
ulimit -n 65536 2>/dev/null || true

# 11. Clear page cache to free memory
echo "Clearing page cache..."
sync
echo 1 | sudo tee /proc/sys/vm/drop_caches > /dev/null

echo
echo "=== System Optimization Complete ==="
echo "System is now optimized for 1080p 30fps dual-camera recording"
echo

# Display current system status
echo "Current System Status:"
echo "  CPU Governor: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
echo "  CPU Frequency: $(cat /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_cur_freq) Hz"
echo "  Free Memory: $(free -h | grep Mem | awk '{print $4}')"
echo "  Swappiness: $(cat /proc/sys/vm/swappiness)"
echo "  Power Mode: $(sudo nvpmodel -q | head -1)"
#!/bin/bash
# NVMe optimization script for Jetson
# Optimizes NVMe drive for video recording workloads

set -e

NVME_DEV="/dev/nvme0n1"

echo "NVMe Optimization Script"
echo "========================"

if [ ! -b "$NVME_DEV" ]; then
    echo "ERROR: NVMe device not found: $NVME_DEV"
    exit 1
fi

# Set I/O scheduler to none (for NVMe SSDs)
echo "Setting I/O scheduler..."
echo "none" > /sys/block/nvme0n1/queue/scheduler

# Increase queue depth
echo "Increasing queue depth..."
echo "1024" > /sys/block/nvme0n1/queue/nr_requests

# Enable write cache
echo "Enabling write cache..."
hdparm -W1 $NVME_DEV 2>/dev/null || nvme set-feature $NVME_DEV -f 0x06 -v 1

# Set readahead
echo "Setting readahead..."
blockdev --setra 8192 $NVME_DEV

# Enable APST (Autonomous Power State Transition) with low latency
echo "Configuring power management..."
nvme set-feature $NVME_DEV -f 0x0c -v 0 || true

# Verify settings
echo ""
echo "Current settings:"
echo "  Scheduler: $(cat /sys/block/nvme0n1/queue/scheduler)"
echo "  Queue depth: $(cat /sys/block/nvme0n1/queue/nr_requests)"
echo "  Readahead: $(blockdev --getra $NVME_DEV)"

echo ""
echo "NVMe optimization complete!"
#!/bin/bash
# Storage performance benchmark

echo "Testing NVMe write performance..."

# Check if fio is installed
if ! command -v fio &> /dev/null; then
    echo "Installing fio..."
    sudo apt-get update && sudo apt-get install -y fio
fi

sudo fio --filename=/mnt/recordings/test \
    --direct=1 \
    --rw=write \
    --bs=4M \
    --size=10G \
    --numjobs=1 \
    --runtime=30 \
    --time_based \
    --group_reporting \
    --name=nvme-test

sudo rm -f /mnt/recordings/test
echo ""
echo "Target: >400 MB/s sustained write"

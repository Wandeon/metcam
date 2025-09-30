#!/bin/bash
# NVMe Storage Benchmark Suite
# Comprehensive performance testing for video recording workload

set -e

DEVICE="/dev/nvme0n1"
MOUNT_POINT="/mnt/recordings"
RESULTS_FILE="/tmp/storage_benchmark_results.txt"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_result() {
    echo -e "${GREEN}[RESULT]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo "========================================"
echo "  NVMe Storage Benchmark Suite"
echo "========================================"
echo ""

# Check requirements
if [ ! -b "$DEVICE" ]; then
    log_warning "NVMe device not found: $DEVICE"
    exit 1
fi

if ! command -v fio >/dev/null 2>&1; then
    log_info "Installing fio..."
    sudo apt-get update && sudo apt-get install -y fio
fi

echo "Device: $DEVICE"
echo "Mount: $MOUNT_POINT"
echo ""
echo "Starting benchmarks..."
echo ""

# 1. Sequential Write Test (Video Recording Simulation)
log_info "Test 1: Sequential Write (1GB, 1MB blocks)"
SEQ_WRITE=$(sudo fio --name=seq_write \
    --filename=$MOUNT_POINT/test_seq_write \
    --rw=write \
    --bs=1M \
    --direct=1 \
    --numjobs=1 \
    --size=1G \
    --runtime=60 \
    --time_based=0 \
    --group_reporting \
    --output-format=json | jq -r '.jobs[0].write.bw / 1024')

log_result "Sequential Write: ${SEQ_WRITE} MB/s"
echo "seq_write_mbps=$SEQ_WRITE" >> $RESULTS_FILE

# 2. Sustained Write Test (150 minute match simulation)
log_info "Test 2: Sustained Write (5 minutes @ 370MB/s target)"
SUSTAINED=$(sudo fio --name=sustained_write \
    --filename=$MOUNT_POINT/test_sustained \
    --rw=write \
    --bs=4M \
    --direct=1 \
    --numjobs=1 \
    --rate=370M \
    --size=10G \
    --runtime=300 \
    --time_based \
    --group_reporting \
    --output-format=json | jq -r '.jobs[0].write.bw / 1024')

log_result "Sustained Write: ${SUSTAINED} MB/s"
echo "sustained_write_mbps=$SUSTAINED" >> $RESULTS_FILE

# 3. Dual Stream Write (Two Cameras)
log_info "Test 3: Dual Stream Write (2x 370MB/s)"
DUAL=$(sudo fio --name=dual_write \
    --filename=$MOUNT_POINT/test_dual_1:$MOUNT_POINT/test_dual_2 \
    --rw=write \
    --bs=1M \
    --direct=1 \
    --numjobs=2 \
    --size=2G \
    --group_reporting \
    --output-format=json | jq -r '.jobs[0].write.bw / 1024')

log_result "Dual Stream Write: ${DUAL} MB/s"
echo "dual_write_mbps=$DUAL" >> $RESULTS_FILE

# 4. Write Latency Test
log_info "Test 4: Write Latency (99th percentile)"
LATENCY=$(sudo fio --name=latency_test \
    --filename=$MOUNT_POINT/test_latency \
    --rw=write \
    --bs=1M \
    --direct=1 \
    --numjobs=1 \
    --size=1G \
    --runtime=30 \
    --time_based \
    --group_reporting \
    --output-format=json | jq -r '.jobs[0].write.lat_ns.percentile."99.000000" / 1000000')

log_result "P99 Latency: ${LATENCY} ms"
echo "p99_latency_ms=$LATENCY" >> $RESULTS_FILE

# 5. IOPS Test (Metadata Operations)
log_info "Test 5: Random Write IOPS (4K blocks)"
IOPS=$(sudo fio --name=iops_test \
    --filename=$MOUNT_POINT/test_iops \
    --rw=randwrite \
    --bs=4K \
    --direct=1 \
    --numjobs=1 \
    --size=1G \
    --runtime=30 \
    --time_based \
    --group_reporting \
    --output-format=json | jq -r '.jobs[0].write.iops')

log_result "Random Write IOPS: ${IOPS}"
echo "iops=$IOPS" >> $RESULTS_FILE

# 6. CPU Overhead Test
log_info "Test 6: CPU Usage During Write"
(sudo fio --name=cpu_test \
    --filename=$MOUNT_POINT/test_cpu \
    --rw=write \
    --bs=1M \
    --direct=1 \
    --numjobs=1 \
    --size=2G \
    --runtime=30 \
    --time_based \
    --group_reporting \
    > /dev/null 2>&1) &

FIO_PID=$!
sleep 5

CPU_USAGE=$(top -b -n 10 -d 1 -p $FIO_PID | grep fio | awk '{sum+=$9; count++} END {print sum/count}')
wait $FIO_PID

log_result "Average CPU Usage: ${CPU_USAGE}%"
echo "cpu_usage_pct=$CPU_USAGE" >> $RESULTS_FILE

# Cleanup test files
log_info "Cleaning up test files..."
sudo rm -f $MOUNT_POINT/test_*

# Display summary
echo ""
echo "========================================"
echo "  Benchmark Results Summary"
echo "========================================"
cat $RESULTS_FILE
echo ""

# Validate against requirements
echo "Validation Against Requirements:"
echo "--------------------------------"

PASS=0
FAIL=0

# Sequential write: > 400 MB/s
if (( $(echo "$SEQ_WRITE > 400" | bc -l) )); then
    echo -e "${GREEN}✓${NC} Sequential Write: ${SEQ_WRITE} MB/s (> 400 MB/s)"
    ((PASS++))
else
    echo -e "${RED}✗${NC} Sequential Write: ${SEQ_WRITE} MB/s (< 400 MB/s)"
    ((FAIL++))
fi

# Sustained write: > 370 MB/s
if (( $(echo "$SUSTAINED > 370" | bc -l) )); then
    echo -e "${GREEN}✓${NC} Sustained Write: ${SUSTAINED} MB/s (> 370 MB/s)"
    ((PASS++))
else
    echo -e "${RED}✗${NC} Sustained Write: ${SUSTAINED} MB/s (< 370 MB/s)"
    ((FAIL++))
fi

# Dual stream: > 740 MB/s
if (( $(echo "$DUAL > 740" | bc -l) )); then
    echo -e "${GREEN}✓${NC} Dual Stream: ${DUAL} MB/s (> 740 MB/s)"
    ((PASS++))
else
    echo -e "${RED}✗${NC} Dual Stream: ${DUAL} MB/s (< 740 MB/s)"
    ((FAIL++))
fi

# Latency: < 10 ms
if (( $(echo "$LATENCY < 10" | bc -l) )); then
    echo -e "${GREEN}✓${NC} P99 Latency: ${LATENCY} ms (< 10 ms)"
    ((PASS++))
else
    echo -e "${RED}✗${NC} P99 Latency: ${LATENCY} ms (> 10 ms)"
    ((FAIL++))
fi

# CPU usage: < 5%
if (( $(echo "$CPU_USAGE < 5" | bc -l) )); then
    echo -e "${GREEN}✓${NC} CPU Usage: ${CPU_USAGE}% (< 5%)"
    ((PASS++))
else
    echo -e "${YELLOW}⚠${NC} CPU Usage: ${CPU_USAGE}% (> 5%)"
fi

echo ""
echo "Tests Passed: $PASS"
echo "Tests Failed: $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}All performance requirements met!${NC}"
    exit 0
else
    echo -e "${RED}Performance requirements not met${NC}"
    echo "Consider:"
    echo "  - Verify NVMe is properly installed"
    echo "  - Run: sudo /opt/footballvision/scripts/optimize-nvme.sh"
    echo "  - Check thermal throttling"
    echo "  - Verify I/O scheduler settings"
    exit 1
fi
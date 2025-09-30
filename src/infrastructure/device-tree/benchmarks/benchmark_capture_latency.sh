#!/bin/bash
# Benchmark camera capture latency
# Measures time from capture request to frame availability

set -e

CAMERA_DEV="/dev/video0"
NUM_SAMPLES=100
WIDTH=4056
HEIGHT=3040
FORMAT="RG10"

echo "=================================="
echo "Camera Capture Latency Benchmark"
echo "=================================="
echo "Device: $CAMERA_DEV"
echo "Resolution: ${WIDTH}x${HEIGHT}"
echo "Samples: $NUM_SAMPLES"
echo ""

if [ ! -c "$CAMERA_DEV" ]; then
    echo "ERROR: Camera device not found: $CAMERA_DEV"
    exit 1
fi

if ! command -v v4l2-ctl >/dev/null 2>&1; then
    echo "ERROR: v4l2-ctl not installed"
    echo "Install with: sudo apt-get install v4l2-utils"
    exit 1
fi

# Set camera format
echo "Configuring camera..."
v4l2-ctl --device=$CAMERA_DEV \
    --set-fmt-video=width=$WIDTH,height=$HEIGHT,pixelformat=$FORMAT \
    > /dev/null 2>&1

# Warm-up captures
echo "Warming up..."
for i in {1..5}; do
    v4l2-ctl --device=$CAMERA_DEV \
        --stream-mmap --stream-count=1 \
        --stream-to=/dev/null \
        > /dev/null 2>&1
done

# Benchmark captures
echo "Running benchmark..."
LATENCIES=()
for i in $(seq 1 $NUM_SAMPLES); do
    START=$(date +%s%N)
    v4l2-ctl --device=$CAMERA_DEV \
        --stream-mmap --stream-count=1 \
        --stream-to=/dev/null \
        > /dev/null 2>&1
    END=$(date +%s%N)

    LATENCY=$(( (END - START) / 1000000 ))  # Convert to ms
    LATENCIES+=($LATENCY)

    if [ $(($i % 10)) -eq 0 ]; then
        echo -n "."
    fi
done
echo ""

# Calculate statistics
IFS=$'\n' SORTED=($(sort -n <<<"${LATENCIES[*]}"))
unset IFS

SUM=0
for val in "${LATENCIES[@]}"; do
    SUM=$((SUM + val))
done

AVG=$((SUM / NUM_SAMPLES))
MIN=${SORTED[0]}
MAX=${SORTED[-1]}
P50=${SORTED[$((NUM_SAMPLES / 2))]}
P95=${SORTED[$((NUM_SAMPLES * 95 / 100))]}
P99=${SORTED[$((NUM_SAMPLES * 99 / 100))]}

# Display results
echo ""
echo "Results:"
echo "  Average: ${AVG}ms"
echo "  Minimum: ${MIN}ms"
echo "  Maximum: ${MAX}ms"
echo "  P50:     ${P50}ms"
echo "  P95:     ${P95}ms"
echo "  P99:     ${P99}ms"
echo ""

# Pass/Fail criteria
if [ $P99 -lt 100 ]; then
    echo "✓ PASS: Latency within target (<100ms)"
    exit 0
else
    echo "✗ FAIL: Latency exceeds target (P99: ${P99}ms > 100ms)"
    exit 1
fi
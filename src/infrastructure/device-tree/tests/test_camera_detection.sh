#!/bin/bash
# Test script for camera detection
# Verifies both IMX477 cameras are detected and accessible

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

echo "=================================="
echo "Camera Detection Test"
echo "=================================="
echo ""

# Test 1: Check video devices exist
echo -n "Test 1: Checking video devices... "
if [ -c /dev/video0 ] && [ -c /dev/video1 ]; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    echo "  Expected: /dev/video0 and /dev/video1"
    ls -l /dev/video* 2>/dev/null || echo "  No video devices found"
    ((ERRORS++))
fi

# Test 2: Check device tree nodes
echo -n "Test 2: Checking device tree nodes... "
CAM0_NODE="/proc/device-tree/cam_i2cmux/i2c@0/imx477_a@1a"
CAM1_NODE="/proc/device-tree/cam_i2cmux/i2c@1/imx477_b@1a"
if [ -d "$CAM0_NODE" ] && [ -d "$CAM1_NODE" ]; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    echo "  Camera nodes not found in device tree"
    ((ERRORS++))
fi

# Test 3: Check kernel driver loaded
echo -n "Test 3: Checking IMX477 driver... "
if lsmod | grep -q imx477; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${YELLOW}WARNING${NC}"
    echo "  IMX477 driver not loaded (may be built-in)"
fi

# Test 4: Check I2C devices
echo -n "Test 4: Checking I2C communication... "
I2C_FOUND=0
if command -v i2cdetect >/dev/null 2>&1; then
    # Check camera 0 (bus 30)
    if i2cdetect -y -r 30 2>/dev/null | grep -q "1a"; then
        ((I2C_FOUND++))
    fi
    # Check camera 1 (bus 31)
    if i2cdetect -y -r 31 2>/dev/null | grep -q "1a"; then
        ((I2C_FOUND++))
    fi

    if [ $I2C_FOUND -eq 2 ]; then
        echo -e "${GREEN}PASS${NC}"
    else
        echo -e "${RED}FAIL${NC}"
        echo "  Found $I2C_FOUND/2 cameras on I2C"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}SKIP${NC}"
    echo "  i2c-tools not installed"
fi

# Test 5: Check V4L2 capabilities
echo -n "Test 5: Checking V4L2 capabilities... "
if command -v v4l2-ctl >/dev/null 2>&1; then
    if v4l2-ctl --device=/dev/video0 --all >/dev/null 2>&1 && \
       v4l2-ctl --device=/dev/video1 --all >/dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
    else
        echo -e "${RED}FAIL${NC}"
        echo "  V4L2 query failed"
        ((ERRORS++))
    fi
else
    echo -e "${YELLOW}SKIP${NC}"
    echo "  v4l2-utils not installed"
fi

# Test 6: Check CSI configuration
echo -n "Test 6: Checking CSI configuration... "
if dmesg | grep -q "imx477.*detected"; then
    echo -e "${GREEN}PASS${NC}"
else
    echo -e "${RED}FAIL${NC}"
    echo "  Camera detection not found in kernel log"
    ((ERRORS++))
fi

# Test 7: Check for CSI errors
echo -n "Test 7: Checking CSI error counters... "
if [ -f /sys/kernel/debug/tegra_csi/csi_err ]; then
    CSI_ERRORS=$(cat /sys/kernel/debug/tegra_csi/csi_err | grep -v "0$" | wc -l)
    if [ $CSI_ERRORS -eq 0 ]; then
        echo -e "${GREEN}PASS${NC}"
    else
        echo -e "${YELLOW}WARNING${NC}"
        echo "  Found $CSI_ERRORS CSI error(s)"
    fi
else
    echo -e "${YELLOW}SKIP${NC}"
    echo "  CSI debug interface not available"
fi

# Summary
echo ""
echo "=================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}$ERRORS test(s) failed${NC}"
    exit 1
fi
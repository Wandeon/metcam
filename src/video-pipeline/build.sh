#!/bin/bash
#
# FootballVision Pro - Build Script
#

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BUILD_DIR="${SCRIPT_DIR}/build"
INSTALL_PREFIX="/usr/local"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "  FootballVision Pro - Build Script"
echo "========================================"
echo ""

# Parse arguments
BUILD_TYPE="Release"
CLEAN=0
RUN_TESTS=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --debug)
            BUILD_TYPE="Debug"
            shift
            ;;
        --clean)
            CLEAN=1
            shift
            ;;
        --test)
            RUN_TESTS=1
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --debug      Build in debug mode"
            echo "  --clean      Clean build directory first"
            echo "  --test       Run tests after build"
            echo "  --help       Show this help"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Clean if requested
if [ $CLEAN -eq 1 ]; then
    echo -e "${YELLOW}Cleaning build directory...${NC}"
    rm -rf "${BUILD_DIR}"
fi

# Create build directory
echo "Creating build directory: ${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"
cd "${BUILD_DIR}"

# Configure
echo -e "\n${GREEN}Configuring CMake...${NC}"
cmake .. \
    -DCMAKE_BUILD_TYPE=${BUILD_TYPE} \
    -DCMAKE_INSTALL_PREFIX=${INSTALL_PREFIX}

# Build
echo -e "\n${GREEN}Building...${NC}"
make -j$(nproc)

# Run tests if requested
if [ $RUN_TESTS -eq 1 ]; then
    echo -e "\n${GREEN}Running tests...${NC}"

    if [ -f camera-control/test_camera_control ]; then
        echo "Running camera control tests..."
        ./camera-control/test_camera_control
    fi

    if [ -f gstreamer-core/test_gstreamer_core ]; then
        echo "Running GStreamer core tests..."
        ./gstreamer-core/test_gstreamer_core
    fi
fi

# Show summary
echo ""
echo "========================================"
echo -e "  ${GREEN}Build Complete!${NC}"
echo "========================================"
echo ""
echo "Build type: ${BUILD_TYPE}"
echo "Build directory: ${BUILD_DIR}"
echo ""
echo "Binaries:"
echo "  - footballvision-recorder: ${BUILD_DIR}/footballvision-recorder"
echo "  - libfootballvision.so: ${BUILD_DIR}/libfootballvision.so"
echo ""
echo "To install:"
echo "  sudo make install"
echo ""
echo "To run:"
echo "  ./footballvision-recorder game_test_20250930"
echo ""
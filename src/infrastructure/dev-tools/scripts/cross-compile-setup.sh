#!/bin/bash
# Cross-compilation toolchain setup for ARM64 Jetson

set -e

echo "Installing ARM64 Cross-Compilation Toolchain"
echo "============================================"

# Install cross-compiler
sudo apt-get update
sudo apt-get install -y \
    gcc-aarch64-linux-gnu \
    g++-aarch64-linux-gnu \
    binutils-aarch64-linux-gnu

# Set environment variables
cat >> ~/.bashrc << 'EOF'

# Jetson Cross-Compilation
export CROSS_COMPILE=aarch64-linux-gnu-
export ARCH=arm64
export CC=${CROSS_COMPILE}gcc
export CXX=${CROSS_COMPILE}g++
EOF

echo "Cross-compilation toolchain installed"
echo "Run: source ~/.bashrc"
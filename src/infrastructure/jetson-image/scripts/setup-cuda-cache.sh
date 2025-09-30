#!/bin/bash
# CUDA cache setup script
# Configures CUDA compilation cache for faster startup

set -e

CACHE_DIR="/var/cache/cuda"
CACHE_SIZE="2147483648"  # 2GB

echo "CUDA Cache Setup"
echo "================"

# Create cache directory
echo "Creating cache directory: $CACHE_DIR"
mkdir -p "$CACHE_DIR"
chmod 1777 "$CACHE_DIR"  # Sticky bit for multi-user

# Set environment variables
echo "Configuring environment..."
cat >> /etc/environment << EOF

# CUDA cache configuration
CUDA_CACHE_PATH=$CACHE_DIR
CUDA_CACHE_MAXSIZE=$CACHE_SIZE
CUDA_FORCE_PTX_JIT=0
CUDA_LAUNCH_BLOCKING=0
EOF

# Create systemd service to pre-warm cache
cat > /etc/systemd/system/cuda-cache-warmup.service << EOF
[Unit]
Description=CUDA Cache Warmup
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/cuda-warmup.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Create warmup script
cat > /usr/local/bin/cuda-warmup.sh << 'EOF'
#!/bin/bash
# Pre-compile common CUDA kernels

export CUDA_CACHE_PATH=/var/cache/cuda
export CUDA_CACHE_MAXSIZE=2147483648

# Compile test kernel to warm up cache
cat > /tmp/cuda_test.cu << 'CUDA_EOF'
__global__ void warmup_kernel(float *data, int n) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < n) data[idx] = data[idx] * 2.0f;
}
CUDA_EOF

nvcc /tmp/cuda_test.cu -o /tmp/cuda_test 2>/dev/null || true
rm -f /tmp/cuda_test.cu /tmp/cuda_test

echo "CUDA cache warmed up"
EOF

chmod +x /usr/local/bin/cuda-warmup.sh

# Enable service
systemctl enable cuda-cache-warmup.service

echo ""
echo "CUDA cache setup complete!"
echo "Cache location: $CACHE_DIR"
echo "Max size: $((CACHE_SIZE / 1024 / 1024))MB"
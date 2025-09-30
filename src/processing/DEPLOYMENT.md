# Deployment Guide - Processing Pipeline

## System Requirements

### Hardware
- **Platform:** NVIDIA Jetson Orin Nano Super
- **GPU:** 6 TFLOPS, Ampere architecture
- **RAM:** 8GB LPDDR5
- **Storage:** 256GB NVMe SSD minimum
- **Cameras:** Dual Sony IMX477 with M12 2.7mm lenses

### Software
- **OS:** JetPack 6.0+ (Ubuntu 22.04 based)
- **CUDA:** 12.0+
- **Python:** 3.10+
- **OpenCV:** 4.8+ with CUDA support
- **FFmpeg:** 6.0+ with NVENC/NVDEC

## Installation

### 1. System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install CUDA toolkit
sudo apt install -y \
    cuda-toolkit-12-0 \
    nvidia-cuda-toolkit \
    libcudnn8 \
    libcudnn8-dev

# Install OpenCV with CUDA
sudo apt install -y \
    libopencv-dev \
    libopencv-contrib-dev \
    python3-opencv

# Install video codecs
sudo apt install -y \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev

# Install build tools
sudo apt install -y \
    cmake \
    build-essential \
    pkg-config \
    git
```

### 2. Python Environment

```bash
# Create virtual environment
python3 -m venv ~/venv/metcam
source ~/venv/metcam/bin/activate

# Install Python packages
pip install --upgrade pip
pip install \
    numpy>=1.24.0 \
    opencv-python>=4.8.0 \
    pybind11>=2.11.0 \
    pyyaml>=6.0 \
    pytest>=7.4.0 \
    psutil>=5.9.0
```

### 3. Build Processing Pipeline

```bash
cd ~/metcam/src/processing

# Create build directory
mkdir -p build && cd build

# Configure
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/opt/metcam \
    -DCMAKE_CUDA_ARCHITECTURES=87

# Build
make -j$(nproc)

# Install
sudo make install

# Add to Python path
echo "export PYTHONPATH=/opt/metcam/python:$PYTHONPATH" >> ~/.bashrc
source ~/.bashrc
```

### 4. Verify Installation

```bash
# Check CUDA
nvidia-smi
nvcc --version

# Check Python imports
python3 << EOF
import processing
print(f"Processing pipeline version: {processing.__version__}")

from processing import create_processor
print("✓ All imports successful")
EOF

# Run tests
cd ~/metcam/src/processing
pytest tests/ -v
```

## Initial Calibration

### 1. Prepare Calibration Pattern

Print or display checkerboard pattern:
- **Pattern:** 9×6 squares
- **Square size:** 30mm
- **Print on:** Rigid surface (foam board recommended)
- **Ensure:** Pattern is perfectly flat

### 2. Capture Calibration Images

```bash
# Create calibration directory
mkdir -p ~/calibration/cam0 ~/calibration/cam1

# Capture images using processing tools
python3 -m processing.calibration.capture \
    --camera 0 \
    --output ~/calibration/cam0 \
    --num-images 25

python3 -m processing.calibration.capture \
    --camera 1 \
    --output ~/calibration/cam1 \
    --num-images 25
```

**Capture Guidelines:**
- Vary distances: 2m, 5m, 10m, 20m from pattern
- Vary angles: -30°, 0°, +30° relative to pattern
- Cover entire field of view
- Focus on overlap region
- Ensure good lighting (no shadows)

### 3. Compute Calibration

```bash
python3 -m processing.calibration.calibrate compute \
    --cam0-images ~/calibration/cam0 \
    --cam1-images ~/calibration/cam1 \
    --pattern-size 9x6 \
    --square-size 30 \
    --output /opt/metcam/calibration.yaml
```

Expected output:
```
Detecting patterns...
✓ Camera 0: 25/25 patterns detected
✓ Camera 1: 25/25 patterns detected

Calibrating camera 0...
✓ Reprojection error: 0.32 pixels

Calibrating camera 1...
✓ Reprojection error: 0.28 pixels

Computing stereo calibration...
✓ Camera angle: 90.2°
✓ Baseline: 198.5mm

Calibration saved to /opt/metcam/calibration.yaml
```

### 4. Validate Calibration

```bash
python3 -m processing.calibration.calibrate validate \
    --calibration /opt/metcam/calibration.yaml \
    --test-footage ~/test_recordings/cam0.h265
```

## Processing First Game

### 1. Process Single Game

```bash
python3 ~/metcam/src/processing/examples/process_game.py \
    --cam0 /recordings/game_20250930/cam0.h265 \
    --cam1 /recordings/game_20250930/cam1.h265 \
    --output /output/game_20250930_panorama.h265 \
    --calibration /opt/metcam/calibration.yaml \
    --quality high
```

### 2. Monitor Processing

Watch system resources:
```bash
# Terminal 1: GPU monitoring
watch -n 1 nvidia-smi

# Terminal 2: System resources
htop

# Terminal 3: Processing log
tail -f /var/log/metcam/processing.log
```

### 3. Verify Output

```bash
# Check output file
ffprobe /output/game_20250930_panorama.h265

# Expected output:
# Resolution: 7000x3040
# Frame rate: 30 fps
# Codec: hevc (H.265)
# Duration: ~150 minutes
```

## Batch Processing Setup

### 1. Configure Batch Manager

```python
# batch_config.yaml
max_concurrent_jobs: 1
quality_preset: high
enable_quality_checks: true
gpu_device: 0
batch_size: 8
output_directory: /output
calibration_file: /opt/metcam/calibration.yaml
```

### 2. Start Batch Processing Service

```bash
# Create systemd service
sudo tee /etc/systemd/system/metcam-batch.service << EOF
[Unit]
Description=MetCam Batch Processing Service
After=network.target

[Service]
Type=simple
User=metcam
WorkingDirectory=/opt/metcam
ExecStart=/usr/bin/python3 -m processing.batch_manager.service --config /opt/metcam/batch_config.yaml
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable metcam-batch
sudo systemctl start metcam-batch

# Check status
sudo systemctl status metcam-batch
```

### 3. Submit Jobs via API

```python
import requests

# Submit job
response = requests.post('http://localhost:8080/api/processing/jobs', json={
    'input_cam0': '/recordings/game1/cam0.h265',
    'input_cam1': '/recordings/game1/cam1.h265',
    'output_path': '/output/game1_panorama.h265'
})

job_id = response.json()['job_id']

# Check status
status = requests.get(f'http://localhost:8080/api/processing/jobs/{job_id}')
print(status.json())
```

## Performance Optimization

### 1. GPU Performance Mode

```bash
# Set maximum performance
sudo nvpmodel -m 0  # Max performance mode
sudo jetson_clocks  # Lock clocks to maximum
```

### 2. Memory Optimization

```bash
# Increase swap if needed
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 3. Storage Optimization

```bash
# Use NVMe for recordings and output
sudo mkdir -p /nvme/recordings /nvme/output
sudo chown metcam:metcam /nvme/recordings /nvme/output

# Configure in application
# input_base: /nvme/recordings
# output_base: /nvme/output
```

## Monitoring and Maintenance

### 1. Setup Monitoring

```bash
# Install monitoring tools
pip install prometheus-client grafana-api

# Start metrics endpoint
python3 -m processing.monitoring.metrics_server --port 9090
```

### 2. Log Rotation

```bash
sudo tee /etc/logrotate.d/metcam << EOF
/var/log/metcam/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 metcam metcam
}
EOF
```

### 3. Health Checks

```bash
# Create health check script
sudo tee /opt/metcam/health_check.sh << 'EOF'
#!/bin/bash

# Check GPU
nvidia-smi > /dev/null || exit 1

# Check disk space (need at least 100GB)
SPACE=$(df /output | tail -1 | awk '{print $4}')
[[ $SPACE -gt 100000000 ]] || exit 1

# Check batch service
systemctl is-active --quiet metcam-batch || exit 1

echo "Health check passed"
exit 0
EOF

chmod +x /opt/metcam/health_check.sh

# Add to cron
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/metcam/health_check.sh") | crontab -
```

### 4. Recalibration Schedule

```bash
# Weekly validation check
0 2 * * 0 /opt/metcam/scripts/validate_calibration.sh

# Monthly full recalibration prompt
0 9 1 * * /opt/metcam/scripts/recalibration_reminder.sh
```

## Troubleshooting

### CUDA Errors

```bash
# Check CUDA installation
nvcc --version
ldconfig -p | grep cuda

# Verify GPU access
python3 -c "import torch; print(torch.cuda.is_available())"
```

### Memory Issues

```bash
# Check GPU memory
nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv

# Clear GPU memory cache
sudo fuser -v /dev/nvidia*
```

### Processing Failures

```bash
# Check logs
journalctl -u metcam-batch -n 100

# Test with smaller file
python3 examples/process_game.py \
    --cam0 test_short.h265 \
    --cam1 test_short.h265 \
    --output test_output.h265 \
    --calibration /opt/metcam/calibration.yaml
```

## Backup and Recovery

### 1. Backup Calibration

```bash
# Backup calibration
cp /opt/metcam/calibration.yaml /backup/calibration_$(date +%Y%m%d).yaml

# Cloud backup
rclone copy /opt/metcam/calibration.yaml remote:metcam/calibration/
```

### 2. Configuration Backup

```bash
# Backup all configs
tar -czf metcam_config_$(date +%Y%m%d).tar.gz \
    /opt/metcam/*.yaml \
    /opt/metcam/*.json \
    /etc/systemd/system/metcam-*
```

## Upgrade Procedure

### 1. Backup Current Installation

```bash
# Stop services
sudo systemctl stop metcam-batch

# Backup
sudo cp -r /opt/metcam /opt/metcam.backup.$(date +%Y%m%d)
```

### 2. Pull Latest Code

```bash
cd ~/metcam
git pull origin develop
```

### 3. Rebuild

```bash
cd ~/metcam/src/processing/build
cmake .. -DCMAKE_INSTALL_PREFIX=/opt/metcam
make -j$(nproc)
sudo make install
```

### 4. Test and Restart

```bash
# Run tests
pytest ~/metcam/src/processing/tests/ -v

# Restart services
sudo systemctl start metcam-batch
sudo systemctl status metcam-batch
```

## Support

For issues:
1. Check logs: `/var/log/metcam/`
2. Run health check: `/opt/metcam/health_check.sh`
3. GitHub issues: `github.com/Wandeon/metcam/issues`
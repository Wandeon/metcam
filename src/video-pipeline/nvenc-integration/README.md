# NVENC Integration (W14)

## Overview
Hardware H.265 encoder integration using NVIDIA NVENC on Jetson Orin Nano.

## Features
- H.265/HEVC encoding (Main10 profile support)
- Hardware acceleration (6 TFLOPS GPU)
- Bitrate control (CBR/VBR)
- Zero-copy from NVMM buffers
- Low-latency encoding

## Encoder Configuration

### Target Settings
- **Codec**: H.265/HEVC
- **Profile**: Main (Main10 for 10-bit future support)
- **Bitrate**: 100 Mbps CBR (120 Mbps peak)
- **GOP**: 30 frames (1 second)
- **Preset**: UltraFast (low latency)
- **Quality**: High (maxperf-enable=1)

### GStreamer Element
```
nvv4l2h265enc
    control-rate=1          # CBR
    bitrate=100000000       # 100 Mbps
    peak-bitrate=120000000  # 120 Mbps peak
    profile=1               # Main profile
    preset-level=0          # UltraFast
    maxperf-enable=1        # Maximum performance
    insert-sps-pps=1        # Insert SPS/PPS
    insert-vui=1            # Insert VUI
    iframeinterval=30       # I-frame every 30 frames
    poc-type=2              # POC type 2
```

## Performance
- Encoding latency: <33ms (1 frame)
- CPU overhead: <2%
- Power: ~15W for dual 4K streams
- Quality: High (sports-optimized)
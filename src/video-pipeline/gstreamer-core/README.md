# GStreamer Pipeline Core (W13)

## Overview
Core GStreamer pipeline implementation for dual 4K camera recording with zero-copy NVMM buffers.

## Features
- Main recording pipeline builder
- NVMM buffer pool management (zero-copy)
- Pipeline state machine
- Error recovery mechanisms
- Bus message handling
- Element factory and management

## Pipeline Architecture

### Per-Camera Pipeline
```
nvarguscamerasrc → capsfilter → nvvidconv → queue → [encoder] → [muxer] → filesink
      ↓
   NVMM buffer pool (30 buffers, ~550MB each)
```

### Key Elements
1. **nvarguscamerasrc**: Direct sensor capture (libargus)
2. **capsfilter**: Format negotiation (4056x3040 NV12 @ 30fps)
3. **nvvidconv**: GPU color conversion (NVMM to NVMM)
4. **queue**: Buffer decoupling (prevents backpressure)
5. **Encoder/Muxer**: Connected by W14/W19

## NVMM Buffer Management

### Zero-Copy Strategy
- All buffers stay in GPU memory (NVMM)
- No CPU memcpy operations
- DMA-BUF passing between elements
- 256-byte aligned allocations

### Pool Configuration
```c
typedef struct {
    uint32_t num_buffers;     // 30 (1 second @ 30fps)
    uint32_t buffer_size;     // 18,531,360 bytes (4056*3040*1.5)
    uint32_t memory_type;     // NVBUF_MEM_SURFACE_ARRAY
    uint32_t alignment;       // 256
} NVMMBufferPool;
```

## Error Recovery

### Soft Errors (recoverable)
- Timestamp discontinuity → Recalibrate
- Buffer underrun → Insert padding frame
- Network issue → Continue recording

### Hard Errors (restart required)
- Camera disconnect
- Encoder crash
- Pipeline stall (>5 seconds)

## Performance
- Startup latency: <2s
- CPU usage: <5% per pipeline
- Memory: ~600MB NVMM per camera
- Frame drops: 0 target
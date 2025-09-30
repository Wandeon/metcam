# FootballVision Pro - Pipeline Architecture

## Overview
Master architecture for dual 4K camera recording system targeting zero frame drops over 150-minute recordings.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Football Vision Pipeline                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │  Camera 0 │───▶│ GStreamer    │───▶│   NVENC      │     │
│  │ IMX477 #0 │    │ Pipeline #0  │    │  Encoder #0  │     │
│  └───────────┘    └──────────────┘    └──────┬───────┘     │
│                                               │              │
│                                               │              │
│  ┌───────────┐    ┌──────────────┐    ┌──────▼───────┐     │
│  │  Camera 1 │───▶│ GStreamer    │───▶│   NVENC      │     │
│  │ IMX477 #1 │    │ Pipeline #1  │    │  Encoder #1  │     │
│  └───────────┘    └──────────────┘    └──────┬───────┘     │
│                                               │              │
│                    ┌──────────────┐           │              │
│                    │  Sync        │◀──────────┘              │
│                    │  Manager     │                          │
│                    └──────┬───────┘                          │
│                           │                                  │
│                    ┌──────▼───────┐                          │
│                    │  Recording   │                          │
│                    │  Manager     │                          │
│                    └──────┬───────┘                          │
│                           │                                  │
│                    ┌──────▼───────┐                          │
│                    │  Storage     │                          │
│                    │  Writer      │                          │
│                    └──────────────┘                          │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Component Integration Map

### Data Flow
1. **Camera Control** → Raw sensor data (10-bit Bayer)
2. **GStreamer Core** → Debayering & Format conversion (NVMM)
3. **NVENC Integration** → H.265 encoding (Main10 profile)
4. **Stream Sync** → Timestamp alignment
5. **Recording Manager** → State control & coordination
6. **Storage Writer** → MP4 muxing & disk I/O
7. **Pipeline Monitor** → Health metrics
8. **Recovery System** → Error handling & restart

### Memory Model
```
Sensor → NVMM Buffer Pool → GPU ISP → NVMM Encoder Input → Bitstream → CPU Memory → Disk
         └─ Zero-copy region (no CPU intervention) ──┘
```

## GStreamer Pipeline Template

### Main Recording Pipeline (Per Camera)
```
nvarguscamerasrc sensor-id={0,1} sensor-mode=0
    bufapi-version=1
    aeantibanding=3
    ee-mode=0 ee-strength=0
    tnr-mode=0
    wbmode=1
! video/x-raw(memory:NVMM),
    width=4056, height=3040,
    format=NV12, framerate=30/1
! nvvidconv compute-hw=1 nvbuf-memory-type=4
! video/x-raw(memory:NVMM), format=I420
! queue max-size-buffers=30 max-size-time=1000000000 leaky=0
! nvv4l2h265enc
    control-rate=1
    bitrate=100000000
    peak-bitrate=120000000
    profile=1
    preset-level=0
    maxperf-enable=1
    insert-sps-pps=1
    insert-vui=1
    iframeinterval=30
    poc-type=2
! h265parse
! queue max-size-buffers=100 max-size-time=2000000000
! mp4mux reserved-moov-update-period=1000000000 streamable=true
! filesink location={output_path} sync=false async=false
```

### Preview Pipeline (Low-res)
```
nvarguscamerasrc sensor-id=0
! video/x-raw(memory:NVMM), width=1280, height=720, framerate=15/1
! nvvidconv
! video/x-raw, format=I420
! jpegenc quality=75
! multipartmux
! tcpserversink host=0.0.0.0 port=8554
```

## API Specifications

### Recording Control API
```python
class RecordingAPI:
    def start_recording(self, game_id: str, output_dir: str) -> bool:
        """Start dual camera recording"""

    def stop_recording(self) -> RecordingResult:
        """Stop recording and finalize files"""

    def get_status(self) -> RecordingStatus:
        """Get current pipeline state"""

    def get_metrics(self) -> PipelineMetrics:
        """Get performance metrics"""
```

### Frame Access API (for Processing Team)
```python
class FrameAccessAPI:
    def get_frame_buffer(self, camera_id: int) -> NVMMBuffer:
        """Access raw frame buffer (zero-copy)"""

    def get_timestamp(self, camera_id: int) -> int:
        """Get frame PTS in nanoseconds"""

    def subscribe_frames(self, callback: Callable) -> int:
        """Subscribe to frame notifications"""
```

## Component Dependencies

```
pipeline-architecture (W11)
├── camera-control (W12)
├── gstreamer-core (W13)
│   ├── nvenc-integration (W14)
│   └── stream-sync (W16)
├── recording-manager (W15)
│   ├── storage-writer (W19)
│   └── recovery-system (W20)
├── preview-pipeline (W17)
└── pipeline-monitor (W18)
```

## State Machine

```
┌─────────┐
│  IDLE   │
└────┬────┘
     │ start_recording()
     ▼
┌─────────┐
│ STARTING│──────┐ (error)
└────┬────┘      │
     │           ▼
     │      ┌─────────┐
     │      │RECOVERY │
     │      └────┬────┘
     │           │
     ▼           │
┌─────────┐◀─────┘
│RECORDING│
└────┬────┘
     │ stop_recording()
     ▼
┌─────────┐
│STOPPING │
└────┬────┘
     │
     ▼
┌─────────┐
│FINALIZING│
└────┬────┘
     │
     ▼
┌─────────┐
│  IDLE   │
└─────────┘
```

## Performance Targets

| Metric | Target | Critical |
|--------|--------|----------|
| Frame drops | 0 | Yes |
| Latency (preview) | <100ms | No |
| CPU usage | <20% | Yes |
| Memory usage | <1GB buffers | Yes |
| Startup time | <5s | No |
| Recovery time | <1s | Yes |
| Sync accuracy | ±1 frame | Yes |

## Buffer Management Strategy

### NVMM Pool Configuration
```c
BufferPoolConfig camera0_pool = {
    .num_buffers = 30,              // 1 second @ 30fps
    .buffer_size = 4056*3040*3/2,   // NV12 format
    .memory_type = NVBUF_MEM_SURFACE_ARRAY,
    .alignment = 256
};
```

### Queue Sizing
- **Pre-encoder**: 30 buffers (1 second)
- **Post-encoder**: 100 buffers (3.3 seconds)
- **Preview tee**: 5 buffers (333ms)

## Error Handling Strategy

1. **Soft errors** (recoverable):
   - Buffer underrun → Insert padding
   - Timestamp discontinuity → Recalibrate
   - Network preview failure → Continue recording

2. **Hard errors** (require restart):
   - Camera disconnect
   - Encoder crash
   - Disk full
   - Memory exhaustion

## Testing Requirements

### Continuous Operation
- 3-hour recording without frame drops
- CPU <20%, Memory <6GB total
- All files playable and in-sync

### Recovery Testing
- Camera hot-unplug during recording
- Disk space exhaustion
- Process SIGKILL and restart
- Power loss simulation

### Synchronization
- Frame alignment within 33ms (1 frame @ 30fps)
- Audio/video sync (future)
- Timestamp monotonicity

## Build Configuration

### CMake Structure
```cmake
project(FootballVision)

add_subdirectory(camera-control)
add_subdirectory(gstreamer-core)
add_subdirectory(nvenc-integration)
add_subdirectory(recording-manager)
add_subdirectory(stream-sync)
add_subdirectory(preview-pipeline)
add_subdirectory(pipeline-monitor)
add_subdirectory(storage-writer)
add_subdirectory(recovery-system)

add_library(footballvision SHARED
    $<TARGET_OBJECTS:camera-control>
    $<TARGET_OBJECTS:gstreamer-core>
    # ... all components
)
```

## Integration Timeline

1. **Phase 1**: Core pipeline (W11-W14)
2. **Phase 2**: Recording & storage (W15, W19)
3. **Phase 3**: Sync & monitoring (W16, W18)
4. **Phase 4**: Preview & recovery (W17, W20)

## Critical Path Items

- [x] Pipeline architecture design
- [ ] Camera control API
- [ ] GStreamer core implementation
- [ ] NVENC integration
- [ ] Recording manager
- [ ] Stream synchronization
- [ ] Full integration test

## Contact & Coordination

**Team Lead**: W11 (Pipeline Architecture)
**Integration Points**: All components must implement standardized C++ interfaces defined in `include/footballvision/`

---
**Version**: 1.0
**Last Updated**: 2025-09-30
**Status**: Architecture Complete
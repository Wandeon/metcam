# NVMe Storage Optimization

## Overview
High-performance storage layer optimized for dual 4K@30fps video recording. Provides write buffer management, filesystem tuning, and performance monitoring for sustained 740 MB/s throughput.

## Features
- Direct I/O with zero-copy writes
- Pre-allocation to prevent fragmentation
- Automatic space management
- Performance benchmarking
- Write cache optimization
- Filesystem tuning for video workloads

## Performance Targets
- **Sequential Write**: > 400 MB/s
- **Sustained Write**: > 370 MB/s (5+ minutes)
- **Dual Stream**: > 740 MB/s
- **Latency (P99)**: < 10 ms
- **CPU Overhead**: < 5%

## Build & Install

```bash
make
sudo make install
```

## API Usage

```c
#include <footballvision/storage_manager.h>

// Initialize
storage_init("/mnt/recordings");

// Check space
if (!storage_has_space(10LL * 1024 * 1024 * 1024)) {
    // Cleanup old recordings
    storage_cleanup_old_recordings(20LL * 1024 * 1024 * 1024);
}

// Open recording file
int fd = storage_open_recording("match_2024_01_15.mp4", O_WRONLY | O_CREAT);

// Write video data
storage_write_optimized(fd, buffer, size);

// Sync to disk
storage_sync(fd);
close(fd);

// Cleanup
storage_cleanup();
```

## Benchmarking

```bash
# Run comprehensive benchmark
sudo ./benchmarks/benchmark_storage.sh

# Expected results:
# - Sequential: 450+ MB/s
# - Sustained: 400+ MB/s
# - Latency: <5ms P99
```

## Integration
- **Video Pipeline**: Use `storage_open_recording()` and `storage_write_optimized()`
- **Platform Team**: Use `storage_get_stats()` for monitoring
- **Processing Team**: Use `storage_has_space()` before stitching

## Testing
```bash
make test
```

## Team Coordination
- **Owner**: W3 (Infrastructure Team)
- **Dependencies**: W2 (JetPack Image)
- **Consumers**: W11-W20 (Video Pipeline), W31-W40 (Platform)

## Change Log
- v1.0.0: Initial NVMe storage optimization
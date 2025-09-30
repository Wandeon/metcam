# Memory Management

## Overview
NVMM buffer allocation for zero-copy video pipeline. Manages GPU memory pools and prevents OOM conditions.

## Features
- NVMM buffer pool (6 buffers)
- Zero-copy DMA buffers
- Automatic memory cleanup
- OOM prevention

## Buffer Configuration
- **Count**: 6 buffers
- **Size**: 4056×3040 NV12
- **Type**: NVMM surface array
- **Memory**: < 2GB baseline

## API
```c
nvmm_init();
int buf_id = nvmm_alloc_buffer();
// Use buffer...
nvmm_free_buffer(buf_id);
nvmm_cleanup();
```

## Team
- Owner: W6
- Consumers: W11-W20 (Video Pipeline)

## Change Log
- v1.0.0: NVMM allocator
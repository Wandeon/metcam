# Storage Writer (W19)

## Overview
Optimized MP4 muxing and disk I/O for high-bitrate 4K video.

## Features
- MP4 muxer with fast-start support
- Write buffer management (reduces syscalls)
- Filesystem monitoring (space checks)
- Optimized for sequential writes
- No file segmentation (single file per camera)

## Performance
- Write buffer: 64MB
- Target write speed: >200 MB/s (dual streams)
- Syscall batching
- Direct I/O support

## File Format
```
MP4 Container
├── ftyp (file type)
├── moov (metadata - fast start)
├── mdat (video data)
└── Compatible with all players
```
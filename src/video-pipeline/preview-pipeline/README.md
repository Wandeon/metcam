# Preview Pipeline (W17)

## Overview
Low-resolution preview stream for monitoring during recording. Isolated from main pipeline.

## Features
- 1280x720 @ 15fps preview
- MJPEG streaming over TCP
- HLS support (future)
- Resource isolation (<5% CPU)

## Pipeline
```
nvarguscamerasrc → 720p → jpegenc → multipartmux → tcpserversink:8554
```

## Usage
```bash
# View preview
ffplay tcp://jetson-ip:8554

# Or in browser (with HLS)
http://jetson-ip:8080/preview.m3u8
```
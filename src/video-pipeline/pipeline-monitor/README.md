# Pipeline Monitor (W18)

## Overview
Real-time monitoring of pipeline health, frame drops, and performance metrics.

## Features
- Frame drop detection (target: 0)
- Buffer level monitoring
- Quality metrics collection
- Alert system (INFO/WARNING/ERROR/CRITICAL)
- Performance dashboard data

## Metrics Collected
- Frames captured/encoded per camera
- Frame drops
- Current/average FPS
- CPU/memory usage
- Disk write rate
- Timestamp drift

## Alerts
- **WARNING**: Frame drop detected
- **ERROR**: >10 frames dropped
- **CRITICAL**: Pipeline stall >5s
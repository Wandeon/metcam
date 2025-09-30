# Stream Synchronization (W16)

## Overview
Synchronizes dual camera streams to ensure frame alignment within 1 frame (33ms @ 30fps).

## Features
- PTS timestamp alignment
- Drift detection and compensation
- Frame-level synchronization
- Hardware trigger support (future)

## Sync Strategy
1. Align first frames at recording start
2. Monitor timestamp drift continuously
3. Apply corrections when drift >16ms (0.5 frames)
4. Report sync status to monitoring

## Performance
- Sync accuracy: ±1 frame (33ms)
- Correction latency: <100ms
- CPU overhead: <1%
# Recovery System (W20)

## Overview
Crash recovery, partial recording salvage, and pipeline restart logic.

## Features
- Automatic crash detection
- State persistence (JSON)
- Partial recording salvage
- Pipeline restart (<1 second)
- Recovery action determination

## Recovery Actions
1. **RESTART_PIPELINE**: Soft reset, keep config
2. **RESTART_CAMERA**: Camera reconnection
3. **RESTART_ENCODER**: Encoder reinitialization
4. **SALVAGE_RECORDING**: Fix partial MP4 files
5. **FULL_RESET**: Complete system restart

## State Persistence
```json
{
  "recording_active": true,
  "game_id": "game_20250930_1430",
  "start_time": 1727702400000,
  "frames_recorded": [54321, 54320],
  "output_paths": ["/mnt/recordings/cam0.mp4", "/mnt/recordings/cam1.mp4"]
}
```

## Salvage Process
1. Check MP4 file integrity
2. Rebuild moov atom if corrupted
3. Recover playable video
4. Log unrecoverable frames
# Recording Manager (W15)

## Overview
Manages recording state machine, coordinates dual pipelines, handles metadata.

## Features
- Recording state machine (IDLE → STARTING → RECORDING → STOPPING → IDLE)
- Dual camera coordination
- Metadata injection (game ID, timestamps)
- Graceful start/stop
- File management

## State Machine
```
IDLE → start_recording() → STARTING → RECORDING
RECORDING → stop_recording() → STOPPING → FINALIZING → IDLE
ERROR → recovery() → RECORDING or IDLE
```

## API
```cpp
RecordingAPI api;
api.Initialize("/etc/footballvision/config.json");
api.StartRecording("game_20250930_1430", "/mnt/recordings");
// ... match recording ...
auto result = api.StopRecording();  // Returns file paths
```
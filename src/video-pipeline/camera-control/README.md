# Camera Control Module (W12)

## Overview
libargus camera wrapper for Sony IMX477 sensors with sports-optimized settings.

## Features
- Direct libargus API access
- Exposure/gain control for fast motion (sports)
- White balance management (daylight optimized)
- Hardware camera synchronization
- Zero-latency configuration

## Camera Settings for Football

### Exposure Strategy
- **Target**: 1/1000s to 1/2000s (freeze motion)
- **Mode**: Manual (disable auto-exposure during match)
- **Range**: 500-2000 μs

### Gain Strategy
- **Target**: ISO 100-400 (daylight)
- **Mode**: Fixed gain during recording
- **Range**: 1.0-4.0x

### Other Settings
- **White Balance**: Daylight (5500K) - locked
- **Edge Enhancement**: Disabled (preserve detail)
- **Temporal Noise Reduction**: Disabled (avoid motion artifacts)
- **Anti-banding**: 50Hz (Europe)

## API Usage

```cpp
#include <footballvision/camera_control.h>

using namespace footballvision;

CameraConfig config{
    .sensor_id = 0,
    .width = 4056,
    .height = 3040,
    .framerate = 30,
    .exposure_time_us = 1000,  // 1/1000s
    .gain = 2.0,                // ISO 200
    .white_balance_mode = 1,    // Daylight
    .auto_exposure = false
};

auto camera = CameraControl::Create();
camera->Initialize(config);
camera->Start();

// Adjust during recording if lighting changes
camera->SetExposure(800);   // Brighter
camera->SetGain(1.5);        // Lower ISO
```

## Synchronization
Both cameras share the same master clock via hardware trigger (future hardware mod) or software PTS alignment.

## Performance
- Initialization: <500ms
- Setting change: <5ms (no frame drops)
- CPU overhead: <1%
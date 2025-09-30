# Hardware Abstraction Layer

## Overview
Unified interface for camera control, GPIO, LEDs, and buttons. Provides consistent API across hardware revisions.

## Components
- **Camera HAL**: V4L2 wrapper for IMX477 control
- **GPIO Control**: LED and button management
- **LED Status**: System status indicators
- **Button Input**: User interaction handling

## API
```c
// Camera
camera_init(0, "/dev/video0");
camera_set_exposure(0, 16666);
camera_set_gain(0, 100);

// GPIO
led_status(1);  // Status LED on
led_recording(1);  // Recording LED on
```

## GPIOs
- LED_STATUS: GPIO 216
- LED_RECORDING: GPIO 217
- BUTTON: GPIO 218

## Team
- Owner: W8
- Consumers: W11-W20 (Video), W31-W40 (Platform)

## Change Log
- v1.0.0: Initial HAL
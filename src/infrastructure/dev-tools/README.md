# Development Tools

## Overview
Cross-compilation setup, debugging utilities, performance profiling, and system diagnostics for FootballVision development.

## Tools
- **cross-compile-setup.sh**: ARM64 toolchain installation
- **system-diagnostics.sh**: Comprehensive health check
- **performance-profiler.sh**: CPU/GPU profiling
- **debug-recorder.sh**: GDB remote debugging setup

## Cross-Compilation
```bash
./scripts/cross-compile-setup.sh
source ~/.bashrc
make CROSS_COMPILE=aarch64-linux-gnu-
```

## Diagnostics
```bash
./scripts/system-diagnostics.sh
```

Output:
- Hardware configuration
- Camera status
- Temperature readings
- Service status
- Performance metrics

## Profiling
```bash
./scripts/performance-profiler.sh
```

## Remote Debugging
```bash
# On Jetson
gdbserver :2345 /opt/footballvision/bin/recording_service

# On host
aarch64-linux-gnu-gdb /path/to/binary
(gdb) target remote jetson-ip:2345
```

## Team
- Owner: W10
- Consumers: All teams

## Change Log
- v1.0.0: Development tools
# SystemD Services

## Overview
SystemD unit files and service configuration for FootballVision components. Manages dependencies and auto-start.

## Services
- **footballvision.target**: Main system target
- **recording.service**: Video recording service
- **thermal-monitor.service**: Temperature monitoring
- **watchdog.service**: System health monitoring

## Dependencies
- nvargus-daemon.service (NVIDIA Argus)
- network.target
- multi-user.target

## Installation
```bash
sudo cp systemd/*.service /etc/systemd/system/
sudo cp systemd/*.target /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable footballvision.target
```

## Service Order
1. nvargus-daemon
2. thermal-monitor
3. network-optimization
4. recording.service

## Team
- Owner: W9
- Consumers: All teams

## Change Log
- v1.0.0: SystemD configuration
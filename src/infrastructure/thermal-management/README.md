# Thermal Management

## Overview
Monitors system temperature and throttles performance to prevent overheating during extended recording sessions.

## Features
- Real-time temperature monitoring
- Automatic throttling at 75°C
- Fan control integration
- Performance restoration

## Thresholds
- **Warning**: 65°C
- **Critical**: 75°C (throttle)
- **Target**: < 60°C sustained

## Installation
```bash
sudo cp systemd/thermal-monitor.service /etc/systemd/system/
sudo systemctl enable thermal-monitor
sudo systemctl start thermal-monitor
```

## Team
- Owner: W5
- Consumers: All teams

## Change Log
- v1.0.0: Thermal monitoring
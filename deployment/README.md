# Deployment & Installer - W46
## FootballVision Pro Deployment Tools

## Overview
One-click deployment and installation system for FootballVision Pro on NVIDIA Jetson platforms.

## Quick Install

```bash
# Download installer
wget https://releases.footballvision.com/latest/installer.tar.gz
tar -xzf installer.tar.gz
cd footballvision-installer

# Run system check
sudo ./deployment/scripts/system-check.sh

# Install
sudo ./deployment/installer/install.sh
```

## Installation Requirements
- NVIDIA Jetson Orin Nano Super (8GB)
- JetPack 6.1 or later
- 50GB+ available storage
- 2x IMX477 cameras
- Network connection (WiFi or Ethernet)

## Deployment Package Contents
```
deployment/
├── installer/
│   ├── install.sh           # Main installation script
│   ├── uninstall.sh         # Removal script
│   └── upgrade.sh           # Upgrade script
├── scripts/
│   ├── system-check.sh      # Pre-flight validation
│   ├── configure.sh         # Configuration wizard
│   └── backup.sh            # Backup utility
├── configs/
│   ├── default.yaml         # Default configuration
│   ├── prometheus.yml       # Monitoring config
│   └── nginx.conf           # Web server config
└── validation/
    └── post-install-test.sh # Installation verification
```

## Installation Process

### 1. Pre-Flight Check
```bash
sudo ./deployment/scripts/system-check.sh
```
Validates:
- Jetson platform
- Storage (>50GB)
- RAM (>7GB)
- Cameras (2x IMX477)
- Network connectivity

### 2. Installation
```bash
sudo ./deployment/installer/install.sh
```

Steps:
1. System validation
2. Dependency installation
3. User/directory creation
4. Application installation
5. Service configuration
6. Monitoring setup
7. Camera detection
8. Service startup

Duration: ~10-15 minutes

### 3. Post-Install Validation
```bash
sudo ./deployment/validation/post-install-test.sh
```
Verifies:
- Services running
- API responding
- Cameras accessible
- Storage configured

## Configuration

### Network Setup
```bash
# WiFi configuration
sudo ./deployment/scripts/configure.sh network --wifi

# Static IP
sudo ./deployment/scripts/configure.sh network --static 192.168.1.100
```

### Camera Calibration
```bash
# Run calibration wizard
sudo ./deployment/scripts/configure.sh calibrate
```

## Uninstallation

```bash
# Remove FootballVision Pro
sudo ./deployment/installer/uninstall.sh

# Keep data?
sudo ./deployment/installer/uninstall.sh --keep-data
```

## Upgrades

```bash
# Download new version
wget https://releases.footballvision.com/v1.1.0/upgrade.tar.gz

# Run upgrade
sudo ./deployment/installer/upgrade.sh

# Rollback if needed
sudo ./deployment/installer/upgrade.sh --rollback
```

## Troubleshooting

### Installation Fails
```bash
# Check system requirements
./deployment/scripts/system-check.sh

# View installation logs
cat /var/log/footballvision-install.log
```

### Service Won't Start
```bash
# Check service status
systemctl status footballvision.service

# View logs
journalctl -u footballvision.service -f
```

### Camera Not Detected
```bash
# List V4L2 devices
v4l2-ctl --list-devices

# Check camera module loaded
lsmod | grep imx477
```

## Deployment Checklist

- [ ] System meets requirements
- [ ] Network configured
- [ ] Cameras connected and detected
- [ ] Installation completed successfully
- [ ] Services running
- [ ] API accessible
- [ ] Test recording successful
- [ ] Monitoring configured
- [ ] Backup configured

## Version History
- **v1.0** (2025-09-30): Initial deployment system - W46
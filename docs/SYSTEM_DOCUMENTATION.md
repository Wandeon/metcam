# MetCam System Documentation

> Auto-generated: 2026-01-27

This document describes the current state of the MetCam dual sports camera system.

---

## Hardware

### Device
| Specification | Value |
|---------------|-------|
| **Model** | NVIDIA Jetson Orin Nano Dev Kit Super |
| **CPU** | 12x ARM Cortex-A78 (64-bit) |
| **GPU** | NVIDIA Orin (nvgpu) |
| **CUDA** | 12.6 |
| **RAM** | 7.4 GiB |
| **Primary Storage** | 238.5 GiB NVMe SSD |
| **Secondary Storage** | 59.5 GiB eMMC |

### Cameras
| Sensor | Device | Connection |
|--------|--------|------------|
| IMX477 (10-001a) | /dev/video1 | tegra-capture-vi:1 |
| IMX477 (9-001a) | /dev/video0 | tegra-capture-vi:2 |

Camera framework: NVIDIA ARGUS + V4L2 (Video4Linux2)

### Thermal Status (typical)
| Zone | Temperature |
|------|-------------|
| CPU | ~40°C |
| GPU | ~40°C |
| SoC | ~38-39°C |

---

## Software

### OS & Platform
| Component | Version |
|-----------|---------|
| **OS** | NVIDIA Jetson Linux (L4T) |
| **Release** | R36.4.7 |
| **Kernel** | 5.15.148-tegra (out-of-tree) |
| **Build Date** | 2025-09-18 |

### Key Software
| Package | Version |
|---------|---------|
| Docker | 29.2.0 |
| CUDA | 12.6 |
| cuDNN | 9.3.0 |
| TensorRT | 10.3.0 |
| Python | 3.10.12 |

---

## Network Configuration

### Hostname
- **Local**: `metcam`
- **Tailscale FQDN**: `metcam.taildb94e1.ts.net`

### Interfaces
| Interface | IP Address | Status |
|-----------|------------|--------|
| enP8p1s0 (Ethernet) | 192.168.18.235/24 | UP |
| tailscale0 (VPN) | 100.78.19.7/32 | UP |
| wlP1s0 (WiFi) | — | DOWN |
| docker0 | 172.17.0.1/16 | DOWN |

### DNS
- Primary: 1.1.1.1
- Fallback: 8.8.8.8
- Search domains: taildb94e1.ts.net, tailnet.local

### Listening Ports
| Port | Service |
|------|---------|
| 22 | SSH |
| 80/443 | Caddy (HTTP/HTTPS) |
| 8000 | FootballVision API |
| 8080 | HTTP Alternate |

---

## Storage

### Disk Usage
| Mount | Size | Used | Available |
|-------|------|------|-----------|
| / (NVMe) | 234G | 85G (38%) | 138G |
| /media (eMMC) | 57G | 22G (41%) | 33G |

### Key Directories
| Directory | Size | Purpose |
|-----------|------|---------|
| /home/mislav/footballvision-pro | 157M | Production app |
| /home/mislav/footballvision-dev | 154M | Development app |
| /home/mislav/metcam | 2.2M | This repository |

---

## Services

### FootballVision Application

| Service | Status | Memory | Purpose |
|---------|--------|--------|---------|
| footballvision-api-enhanced | Running | ~68M | Main API (port 8000) |
| footballvision-nvmm-monitor | Running | ~7M | NVMM buffer monitoring |
| footballvision-recording-health | Running | ~20M | Recording health checks |

**Configuration**:
- User: mislav
- Working directory: /home/mislav/footballvision-pro
- Logs: /var/log/footballvision/api/
- Restart policy: Always (10s delay, max 5 in 300s)

### NVIDIA Services (25+)
Core services for hardware management:
- `nvargus-daemon` - Camera daemon
- `nvfancontrol` - Fan control
- `nvphs` - Power/thermal management
- `nvpmodel` - Power model
- `nv-tee-supplicant` - OP-TEE client

### System Services
| Service | Purpose |
|---------|---------|
| caddy | Reverse proxy (HTTP/HTTPS) |
| docker | Container runtime |
| tailscaled | VPN connectivity |
| ssh | Remote access |

### Disabled Services
| Service | Reason |
|---------|--------|
| grafana-server | Unused monitoring |
| prometheus | Unused monitoring |
| prometheus-alertmanager | Unused monitoring |
| prometheus-node-exporter | Unused monitoring |
| gdm (masked) | Headless device |

---

## Docker

| Component | Status |
|-----------|--------|
| Version | 29.2.0 |
| Daemon | Active |
| Containers | 0 |
| Images | 0 |
| Volumes | 0 |

Docker is installed but not actively used. Only default networks (bridge, host, none) exist.

---

## Application Architecture

```
/home/mislav/
├── footballvision-pro/          # Production deployment
│   ├── src/
│   │   ├── platform/
│   │   │   ├── simple_api_v3.py           # Main API
│   │   │   ├── nvmm_monitor.py            # Buffer monitor
│   │   │   └── recording_health_monitor.py
│   │   ├── panorama/                      # Panorama stitching
│   │   └── video-pipeline/                # Video processing
│   └── scripts/
│       └── power_loss_recovery.sh
│
├── footballvision-dev/          # Development deployment
│   └── (same structure, port 8001)
│
└── metcam/                      # This repository
    ├── src/
    ├── docs/
    ├── config/
    ├── deploy/
    └── scripts/
```

---

## Maintenance Notes

### Recent Changes (2026-01-27)
- Disabled monitoring stack (Grafana, Prometheus) - freed ~410MB RAM
- Disabled GNOME desktop (GDM masked) - freed ~400MB RAM
- Applied 108 system package updates
- System rebooted for clean state

### Memory Optimization
After cleanup, typical memory usage:
- Before: 6.8GB / 7.4GB (92%)
- After: 2.3GB / 7.4GB (31%)

### Update Commands
```bash
# System updates
sudo apt update && sudo apt upgrade

# NVIDIA/JetPack updates
# Check: https://developer.nvidia.com/embedded/jetpack
# Current: JetPack 6.x (L4T R36.4.7)
```

### Service Management
```bash
# FootballVision
sudo systemctl status footballvision-api-enhanced
sudo systemctl restart footballvision-api-enhanced
journalctl -u footballvision-api-enhanced -f

# Re-enable GUI (if needed)
sudo systemctl unmask gdm
sudo systemctl set-default graphical.target
sudo reboot
```

---

## Connectivity

### SSH Access
```bash
ssh mislav@metcam                    # Via Tailscale
ssh mislav@192.168.18.235            # Via local network
```

### API Access
```bash
curl http://metcam:8000/             # Via Tailscale
curl http://192.168.18.235:8000/     # Via local network
```

### Tailscale Network
Device is part of a 34+ node Tailscale network including:
- gpu-01 (Windows)
- vps-02 (Linux)
- pi-audio-02, pi-video-01 (Raspberry Pi devices)
- Multiple GitHub runner instances

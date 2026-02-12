# FootballVision Pro v3

Professional dual-camera recording system for football matches on NVIDIA Jetson Orin Nano Super.

## System Overview

**Hardware:**
- NVIDIA Jetson Orin Nano Super (8GB, 6 cores: 4 performance @ 1.728GHz + 2 efficiency @ 729MHz)
- 2x Sony IMX477 CSI cameras (4K@30fps)
- JetPack 6.1+ (tested on 6.1)
- 32GB+ storage (128GB+ SSD recommended for recordings)

**Features:**
- ✅ Dual-camera synchronized recording at 1080p@25-30fps
- ✅ CPU-based crop pipeline (NV12 → videocrop → I420) for color accuracy
- ✅ In-process GStreamer pipelines with Python bindings
- ✅ **System-level mutual exclusion** - recording and preview never run simultaneously
- ✅ File-based pipeline locking with automatic recovery
- ✅ Dual-stack preview transport (WebRTC primary + HLS fallback)
- ✅ **go2rtc WebRTC relay** for low-latency remote preview through VPS reverse proxy
- ✅ High-quality recording (12Mbps x264, 10-minute segments)
- ✅ Recording management (list, download, delete via web UI)
- ✅ FastAPI REST API with Prometheus metrics
- ✅ Modern React-based web dashboard
- ✅ Caddy web server for WebSocket signaling, API, static serving, and optional HLS fallback
- ✅ Systemd service integration with automatic startup

## Quick Deployment

**For new installations on fresh Jetson Orin Nano Super:**

```bash
# Clone repository
git clone https://github.com/Wandeon/metcam.git
cd metcam

# One-command installation (~10 minutes)
chmod +x deploy/install-complete.sh
./deploy/install-complete.sh

# Post-installation:
# 1. Log out and back in (if added to video group)
# 2. Restart camera daemon: sudo systemctl restart nvargus-daemon
# 3. Access web UI at http://<your-jetson-ip>
```

See **[Deployment Guide](deploy/README.md)** for detailed installation instructions.

## Baseline Restore (Recording + Preview)

If future development breaks recording or preview stability, restore the known-good baseline using:

- **[Recording & Preview Baseline Fallback](docs/BASELINE_RECORDING_PREVIEW_FALLBACK.md)**

Minimal recovery flow:

```bash
cd /home/mislav/footballvision-pro
git stash push -u -m "pre-baseline-restore-$(date +%F-%H%M%S)" || true
git fetch origin
git checkout main
git pull --ff-only origin main

sudo cp deploy/config/Caddyfile /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo caddy reload --config /etc/caddy/Caddyfile

sudo systemctl daemon-reload
sudo systemctl restart footballvision-api-enhanced
```

Baseline fingerprint:

- Commit: `6cd65539a4a8e5c3d3eab8d556158b4825ad7d75`
- Includes preview teardown hardening (non-EOS stop for preview pipelines)

## Quick Start (API)

### Start Recording
```bash
curl -X POST 'http://localhost:8000/api/v1/recording' \
  -H 'Content-Type: application/json' \
  -d '{
    "match_id": "match_2025_01_15",
    "force": false,
    "process_after_recording": false
  }'
```

### Stop Recording
```bash
curl -X DELETE 'http://localhost:8000/api/v1/recording'
```

### Check Status
```bash
# API status
curl http://localhost:8000/api/v1/status | python3 -m json.tool

# Pipeline state (shows if recording/preview is active)
curl http://localhost:8000/api/v1/pipeline-state | python3 -m json.tool

# Recording status
curl http://localhost:8000/api/v1/recording | python3 -m json.tool
```

## Architecture

### Recording Pipeline (Per Camera)
```
nvarguscamerasrc (4K@30fps NV12)
  ↓
nvvidconv (NVMM → system memory, no crop)
  ↓
videocrop (CPU trim to 2880x1616)
  ↓
videoconvert (NV12 → I420)
  ↓
x264enc (12 Mbps, 6 threads)
  ↓
splitmuxsink (10-minute segments)
  → /mnt/recordings/{match_id}/segments/
```

### WebRTC Preview via go2rtc Relay

When accessed through the VPS reverse proxy (`vid.nk-otok.hr`), WebRTC preview uses a **go2rtc relay** to bypass GStreamer 1.20's broken webrtcbin DTLS implementation:

```
Browser ←—WebRTC—→ go2rtc (VPS-02) ←—RTSP—→ GstRtspServer (Jetson)
                     :8555/udp                  :8554 (Tailscale)
```

- **Jetson** serves RTSP via GstRtspServer at `rtsp://100.78.19.7:8554/cam{N}`
- **go2rtc** (on VPS-02) pulls RTSP on-demand and serves WebRTC to browsers
- **Feature-flagged**: enabled by `WEBRTC_RELAY_URL` env var; without it, direct WebRTC is used
- UI-facing transport stays `"webrtc"` — RTSP is internal ingest only

### Core Components
- **pipeline_manager.py** - System-level mutual exclusion with file locks (CRITICAL)
- **gstreamer_manager.py** - Thread-safe in-process GStreamer pipeline manager
- **pipeline_builders.py** - Pipeline string construction for recording, preview (HLS/WebRTC/RTSP)
- **preview_service.py** - Dual-camera preview with transport abstraction (HLS/WebRTC/RTSP relay)
- **recording_service.py** - Dual-camera recording coordinator
- **simple_api_v3.py** - FastAPI REST server with pipeline lock integration

### Pipeline Mutual Exclusion

**Critical Feature:** Recording and preview are **mutually exclusive** at the OS level:

- File-based locks in `/var/lock/footballvision/`
- Recording mode uses `force=True` (takes priority, stops preview)
- Preview mode uses `force=False` (respects recording, won't start)
- Locks persist across crashes
- Automatic stale lock cleanup (5+ minute threshold)

This prevents the CPU from being overwhelmed by running 4 pipelines simultaneously.

### Performance Characteristics
- Preview streaming (WebRTC via go2rtc relay): sub-second latency, even through VPS proxy
- Preview streaming (HLS fallback): ~5-8 seconds latency
- Recording: 25-30fps (both cameras @ 12Mbps)
- CPU usage during recording: 250-350% (2-3 cores)
- Recording start latency: ~500ms (including lock acquisition)
- Recording stop latency: ~2s (graceful EOS)

## Documentation

### Deployment & Setup
- **[Deployment Guide](deploy/README.md)** - Complete installation guide
- **`deploy/deploy-safe.sh`** - Deterministic update script with rollback + smoke checks
- **[Post-Installation Checklist](deploy/CHECKLIST.md)** - Verification steps
- **[Hardware Setup](docs/HARDWARE_SETUP.md)** - Camera and Jetson configuration
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

### Validation & Testing
- **[System Validation](deploy/validate.sh)** - Comprehensive system checks
- **[Quick Functionality Test](deploy/quick-test.sh)** - Preview and recording tests
- **[Performance Test](deploy/performance-test.sh)** - Framerate and CPU analysis
- **[Recording Regression Matrix](docs/RECORDING_REGRESSION_MATRIX.md)** - Hardware-in-loop preset matrix (`fast`, `balanced`, `high`)

### Technical Documentation
- [Architecture Details](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Recording/Preview Baseline Fallback](docs/BASELINE_RECORDING_PREVIEW_FALLBACK.md)
- [Recording SLO + Alert Runbook](docs/RECORDING_SLO.md)

## API Endpoints (v3)

### System Status
- `GET /api/v1/status` - API and system status
- `GET /api/v1/pipeline-state` - Current pipeline lock state (idle/preview/recording)

### Recording
- `POST /api/v1/recording` - Start recording (acquires exclusive lock)
- `DELETE /api/v1/recording` - Stop recording (releases lock)
- `GET /api/v1/recording` - Get recording status
- `GET /api/v1/recording-health` - Segment health diagnostics
- `GET /api/v1/recordings` - List all recordings
- `DELETE /api/v1/recordings/{match_id}` - Delete recording

### Preview
- `POST /api/v1/preview` - Start preview (optional `transport: hls|webrtc`, fails if recording active)
- `DELETE /api/v1/preview` - Stop preview (releases lock)
- `POST /api/v1/preview/restart` - Restart preview pipeline(s)
- `GET /api/v1/preview` - Get preview status

### WebSocket
- `GET /ws` (WebSocket upgrade endpoint) - Real-time status, command plane, and WebRTC signaling

### Recordings Access
- Recordings served via Caddy at: `/recordings/{match_id}/`
- Optional HLS fallback streams at: `/hls/cam0.m3u8` and `/hls/cam1.m3u8`

## System Requirements

### Hardware
- NVIDIA Jetson Orin Nano Super 8GB (6 cores: 4 performance @ 1.728GHz + 2 efficiency @ 729MHz)
- 2x Sony IMX477 CSI camera modules
- 32GB+ microSD or NVMe SSD (128GB+ recommended)
- 5V/4A power supply
- Network connection (Ethernet recommended)
- **Power mode:** Must be set to Mode 2 (MAXN_SUPER) for reliable 30fps recording

### Software
- JetPack 6.1 or higher
- Ubuntu 22.04 (included with JetPack)
- Python 3.10+
- GStreamer 1.20+
- Node.js 20+ (for web dashboard build)

## Installation

### Automated Installation (Recommended)

```bash
git clone https://github.com/Wandeon/metcam.git
cd metcam
./deploy/install-complete.sh
```

### Manual Installation

See **[Deployment Guide](deploy/README.md)** for:
- Step-by-step installation instructions
- Hardware setup guide
- Post-installation validation
- Troubleshooting common issues

## Web UI

After installation, access the web dashboard at:
```
http://<your-jetson-ip>
```

Features:
- Live preview from both cameras (WebRTC via go2rtc relay, with HLS fallback)
- Start/stop recording with match details
- View recording status and metrics
- Download or delete recordings
- System status monitoring

## Useful Commands

```bash
# View API logs
journalctl -u footballvision-api-enhanced -f

# Check service status
sudo systemctl status footballvision-api-enhanced

# Restart services
sudo systemctl restart nvargus-daemon
sudo systemctl restart footballvision-api-enhanced

# Validate system
./deploy/validate.sh

# Test functionality
./deploy/quick-test.sh

# Check performance
./deploy/performance-test.sh
```

## Troubleshooting

**Most common issues:**

1. **Cameras not detected:** Restart nvargus-daemon
   ```bash
   sudo systemctl restart nvargus-daemon
   ```

2. **502 Bad Gateway:** API service crashed, check logs
   ```bash
   journalctl -u footballvision-api-enhanced -n 50
   sudo systemctl restart footballvision-api-enhanced
   ```

3. **Preview/Recording won't start:** Pipeline locked
   ```bash
   curl http://localhost:8000/api/v1/pipeline-state
   # If needed, restart API service to force release
   ```

4. **WebRTC preview black/fails through VPS:** Check go2rtc relay
   ```bash
   # Check go2rtc is running on VPS-02
   ssh root@vps-02 "docker ps | grep go2rtc"
   # Check RTSP is reachable from VPS-02
   ssh root@vps-02 "curl -s http://127.0.0.1:1984/api/streams"
   ```

See **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** for comprehensive solutions.

## Project Structure

```
footballvision-pro/
├── deploy/                       # Deployment infrastructure
│   ├── install-complete.sh      # One-command installation
│   ├── deploy-safe.sh           # Safe production updates with rollback
│   ├── validate.sh              # System validation
│   ├── quick-test.sh            # Functionality tests
│   ├── performance-test.sh      # Performance validation
│   ├── config/
│   │   └── Caddyfile            # Jetson Caddy configuration
│   └── systemd/
│       └── footballvision-api-enhanced.service
├── src/
│   ├── platform/
│   │   ├── simple_api_v3.py     # FastAPI server
│   │   └── web-dashboard/       # React web UI
│   │       └── src/services/
│   │           ├── api.ts       # REST API client
│   │           └── go2rtc.ts    # go2rtc WebRTC signaling service
│   └── video-pipeline/
│       ├── pipeline_manager.py  # Mutex system
│       ├── gstreamer_manager.py # GStreamer wrapper
│       ├── pipeline_builders.py # Pipeline construction (recording + preview + RTSP)
│       ├── preview_service.py   # Preview with transport abstraction + RTSP relay
│       └── recording_service.py # Recording coordinator
├── docs/
│   ├── HARDWARE_SETUP.md        # Hardware guide
│   ├── TROUBLESHOOTING.md       # Issue resolution
│   └── ARCHITECTURE.md          # System design
└── requirements.txt             # Python dependencies
```

## Remote Access (VPS Proxy)

The system is accessible remotely via VPS-02 reverse proxy:

- **URL**: `https://vid.nk-otok.hr`
- **Proxy chain**: Browser → VPS-02 Caddy → Tailscale → Jetson

**Infrastructure on VPS-02** (`152.53.206.126` / Tailscale `100.82.2.46`):
- **Caddy**: Reverse proxies `/api/*` and `/ws` to Jetson FastAPI, `/go2rtc/api/*` to local go2rtc
- **go2rtc** (`alexxit/go2rtc`): Docker container with `network_mode: host`, WebRTC on `:8555/udp`, API on `127.0.0.1:1984`
- **Streams**: `cam0` and `cam1` configured as on-demand RTSP pulls from Jetson

**Infrastructure on Jetson** (`100.78.19.7` via Tailscale):
- **GstRtspServer**: Serves RTSP at `rtsp://100.78.19.7:8554/cam{N}` (only when preview is active)
- **Env vars**: `WEBRTC_RELAY_URL`, `RTSP_BIND_ADDRESS`, `RTSP_PORT` in systemd override

## License

Proprietary - All rights reserved.

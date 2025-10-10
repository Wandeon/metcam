# Development Setup

## Prerequisites
- NVIDIA Jetson Orin Nano Super with JetPack 6.1
- Ubuntu 20.04/22.04 host with SSH access to the Jetson
- GStreamer 1.20+ with NVIDIA multimedia plugins
- Python 3.10

## Environment Setup
1. Clone the repository onto the Jetson: `git clone https://.../footballvision-pro.git`
2. Install system dependencies and create `/mnt/recordings`: `cd footballvision-pro/deploy && ./install.sh`
3. (Optional) Populate test directories: `sudo mkdir -p /var/www/hls /mnt/recordings`
4. Start the FastAPI service locally for development:
   ```bash
   uvicorn src.platform.simple_api:app --reload --host 0.0.0.0 --port 8000
   ```
5. Verify camera access:
   ```bash
   gst-launch-1.0 nvarguscamerasrc sensor-id=0 ! fakesink
   gst-launch-1.0 nvarguscamerasrc sensor-id=1 ! fakesink
   ```

## Component Development
- `scripts/record_dual_1080p30.sh` is the production pipeline. Edit and test it directly, then run `scripts/record_test_simple.sh` for quick smoke tests.
- Use `src/video-pipeline/recording_manager.py` to adjust lifecycle or manifest behaviour.
- API changes live in `src/platform/simple_api.py`. Visit `http://<jetson-ip>:8000/docs` to validate endpoints.

#!/bin/bash
# FootballVision Pro - Installation Script
set -e

echo "=== FootballVision Pro Installation ==="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "ERROR: Do not run this script as root. It will use sudo when needed."
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Project root: $PROJECT_ROOT"
echo ""

# 1. Install system dependencies
echo "[1/5] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-venv \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev

echo "✓ System dependencies installed"
echo ""

# 2. Install Python dependencies
echo "[2/5] Installing Python dependencies..."
pip3 install --user fastapi uvicorn[standard] pydantic

echo "✓ Python dependencies installed"
echo ""

# 3. Create recordings directory
echo "[3/5] Creating recordings directory..."
RECORDINGS_DIR="/mnt/recordings"
sudo mkdir -p "$RECORDINGS_DIR"
sudo chown $USER:$USER "$RECORDINGS_DIR"
chmod 755 "$RECORDINGS_DIR"

echo "✓ Recordings directory created: $RECORDINGS_DIR"
echo ""

# 4. Install systemd service
echo "[4/5] Installing systemd service..."
sudo cp "$SCRIPT_DIR/footballvision-api.service" /etc/systemd/system/
sudo systemctl daemon-reload

echo "✓ Systemd service installed"
echo ""

# 5. Set CPU governor to performance
echo "[5/5] Setting CPU governor to performance mode..."
echo "performance" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > /dev/null

echo "✓ CPU governor set to performance"
echo ""

echo "=== Installation Complete ==="
echo ""
echo "To start the service:"
echo "  sudo systemctl start footballvision-api"
echo ""
echo "To enable auto-start on boot:"
echo "  sudo systemctl enable footballvision-api"
echo ""
echo "To check service status:"
echo "  sudo systemctl status footballvision-api"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u footballvision-api -f"
echo ""
echo "API will be available at:"
echo "  http://localhost:8000"
echo "  http://localhost:8000/docs (Swagger UI)"
echo ""

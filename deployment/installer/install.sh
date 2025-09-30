#!/bin/bash
# FootballVision Pro One-Click Installer
# Supports: NVIDIA Jetson Orin Nano Super with JetPack 6.1+

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/footballvision"
SERVICE_USER="footballvision"
MIN_STORAGE_GB=50
MIN_RAM_GB=7

echo -e "${GREEN}FootballVision Pro Installer${NC}"
echo "======================================"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: Please run as root (sudo)${NC}"
    exit 1
fi

# Step 1: System Validation
echo -e "\n${YELLOW}[1/8] Validating system requirements...${NC}"

# Check Jetson platform
if [ ! -f /etc/nv_tegra_release ]; then
    echo -e "${RED}ERROR: Not running on NVIDIA Jetson${NC}"
    exit 1
fi
echo "✓ Jetson platform detected"

# Check storage
AVAILABLE_GB=$(df / | awk 'NR==2 {print int($4/1024/1024)}')
if [ "$AVAILABLE_GB" -lt "$MIN_STORAGE_GB" ]; then
    echo -e "${RED}ERROR: Insufficient storage. Need ${MIN_STORAGE_GB}GB, have ${AVAILABLE_GB}GB${NC}"
    exit 1
fi
echo "✓ Storage: ${AVAILABLE_GB}GB available"

# Check RAM
TOTAL_RAM_GB=$(free -g | awk 'NR==2 {print $2}')
if [ "$TOTAL_RAM_GB" -lt "$MIN_RAM_GB" ]; then
    echo -e "${RED}ERROR: Insufficient RAM. Need ${MIN_RAM_GB}GB, have ${TOTAL_RAM_GB}GB${NC}"
    exit 1
fi
echo "✓ RAM: ${TOTAL_RAM_GB}GB"

# Step 2: Install Dependencies
echo -e "\n${YELLOW}[2/8] Installing dependencies...${NC}"
apt-get update -qq
apt-get install -y python3-pip python3-venv docker.io v4l-utils ffmpeg \
    prometheus-node-exporter nginx >/dev/null 2>&1
echo "✓ Dependencies installed"

# Step 3: Create User and Directories
echo -e "\n${YELLOW}[3/8] Creating system user and directories...${NC}"
if ! id -u $SERVICE_USER >/dev/null 2>&1; then
    useradd -r -s /bin/false $SERVICE_USER
fi
mkdir -p $INSTALL_DIR/{bin,config,data,logs}
chown -R $SERVICE_USER:$SERVICE_USER $INSTALL_DIR
echo "✓ User and directories created"

# Step 4: Install Application
echo -e "\n${YELLOW}[4/8] Installing FootballVision Pro...${NC}"
cp -r ../src/* $INSTALL_DIR/bin/
python3 -m venv $INSTALL_DIR/venv
$INSTALL_DIR/venv/bin/pip install -r ../requirements.txt >/dev/null 2>&1
echo "✓ Application installed"

# Step 5: Configure System Services
echo -e "\n${YELLOW}[5/8] Configuring system services...${NC}"
cp ../services/systemd/footballvision.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable footballvision.service
echo "✓ Services configured"

# Step 6: Setup Monitoring
echo -e "\n${YELLOW}[6/8] Setting up monitoring...${NC}"
cp ../configs/prometheus.yml /etc/prometheus/
systemctl restart prometheus-node-exporter
echo "✓ Monitoring configured"

# Step 7: Configure Cameras
echo -e "\n${YELLOW}[7/8] Detecting cameras...${NC}"
CAMERA_COUNT=$(v4l2-ctl --list-devices | grep -c imx477 || true)
if [ "$CAMERA_COUNT" -ge 2 ]; then
    echo "✓ Found $CAMERA_COUNT cameras"
else
    echo -e "${YELLOW}⚠ Warning: Only $CAMERA_COUNT camera(s) found. Need 2 for operation.${NC}"
fi

# Step 8: Start Services
echo -e "\n${YELLOW}[8/8] Starting services...${NC}"
systemctl start footballvision.service
sleep 3

if systemctl is-active --quiet footballvision.service; then
    echo -e "✓ Service started"
else
    echo -e "${RED}⚠ Service failed to start. Check logs: journalctl -u footballvision.service${NC}"
fi

# Final Status
echo -e "\n${GREEN}======================================"
echo "Installation Complete!"
echo "======================================${NC}"
echo ""
echo "Access dashboard: http://$(hostname -I | awk '{print $1}'):8000"
echo "System status: systemctl status footballvision.service"
echo "Logs: journalctl -u footballvision.service -f"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Configure network settings"
echo "2. Run camera calibration"
echo "3. Perform test recording"
echo ""
echo "Documentation: https://docs.footballvision.com"
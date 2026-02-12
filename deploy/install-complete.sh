#!/bin/bash
# FootballVision Pro - Complete Installation Script
# For NVIDIA Jetson Orin Nano with JetPack 6.1+
#
# This script performs a complete automated installation of the
# FootballVision Pro v3 system on a fresh Jetson Orin Nano device.

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Banner
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     FootballVision Pro - Complete Installation v3       ║"
echo "║     NVIDIA Jetson Orin Nano with JetPack 6.1+          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   log_error "Please run as regular user (will use sudo when needed)"
   exit 1
fi

# Get repo directory
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
log_info "Repository directory: $REPO_DIR"

# ============================================================================
# Step 1: Verify Hardware & JetPack
# ============================================================================
log_info "Step 1/10: Verifying hardware and JetPack version..."

if [ ! -f "/etc/nv_tegra_release" ]; then
    log_error "This doesn't appear to be a Jetson device"
    exit 1
fi

JETPACK_VERSION=$(dpkg -l | grep nvidia-jetpack | awk '{print $3}' | head -1)
log_info "Detected JetPack version: ${JETPACK_VERSION:-Unknown}"
log_success "Hardware check passed"

# ============================================================================
# Step 2: Install System Dependencies
# ============================================================================
log_info "Step 2/10: Installing system dependencies..."

sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-gi \
    python3-dev \
    gir1.2-gstreamer-1.0 \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    git \
    curl \
    ffmpeg \
    debian-keyring \
    debian-archive-keyring \
    apt-transport-https

log_success "System dependencies installed"

# ============================================================================
# Step 3: Install Caddy Web Server
# ============================================================================
log_info "Step 3/10: Installing Caddy web server..."

if ! command -v caddy &> /dev/null; then
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
    sudo apt-get update
    sudo apt-get install -y caddy
    log_success "Caddy installed"
else
    log_info "Caddy already installed"
fi

# ============================================================================
# Step 4: Install Node.js (if needed)
# ============================================================================
log_info "Step 4/10: Checking Node.js installation..."

if ! command -v node &> /dev/null || [ "$(node -v | cut -d'v' -f2 | cut -d'.' -f1)" -lt 20 ]; then
    log_warning "Node.js 20+ not found, installing..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
    log_success "Node.js installed"
else
    log_info "Node.js $(node -v) already installed"
fi

# ============================================================================
# Step 5: Install Python Dependencies
# ============================================================================
log_info "Step 5/10: Installing Python dependencies..."

pip3 install -r "$REPO_DIR/requirements.txt"
log_success "Python dependencies installed"

# ============================================================================
# Step 6: Create Required Directories
# ============================================================================
log_info "Step 6/10: Creating required directories..."

sudo mkdir -p /var/log/footballvision/{api,system,crashes}
sudo mkdir -p /var/www/footballvision
sudo mkdir -p /mnt/recordings
sudo mkdir -p /dev/shm/hls
sudo mkdir -p /var/lock/footballvision
sudo mkdir -p /var/log/caddy

# Set ownership
sudo chown -R $USER:$USER /var/log/footballvision
sudo chown -R $USER:$USER /var/www/footballvision
sudo chown -R $USER:$USER /mnt/recordings
sudo chown -R $USER:$USER /var/lock/footballvision

# Set permissions
sudo chmod 777 /var/lock/footballvision  # Needed for pipeline manager locks

log_success "Directories created"

# ============================================================================
# Step 7: Add User to Video Group
# ============================================================================
log_info "Step 7/10: Adding user to video group..."

if ! groups $USER | grep -q video; then
    sudo usermod -aG video $USER
    log_warning "Added to video group - YOU MUST LOG OUT AND BACK IN for camera access"
else
    log_info "User already in video group"
fi

# ============================================================================
# Step 8: Build Web Dashboard
# ============================================================================
log_info "Step 8/10: Building web dashboard..."

cd "$REPO_DIR/src/platform/web-dashboard"
npm install
npm run build
sudo rsync -a --delete dist/ /var/www/footballvision/
log_success "Web dashboard built and deployed"

cd "$REPO_DIR"

# ============================================================================
# Step 9: Install Caddy Configuration
# ============================================================================
log_info "Step 9/10: Installing Caddy configuration..."

sudo cp "$REPO_DIR/deploy/config/Caddyfile" /etc/caddy/Caddyfile
sudo systemctl restart caddy
sudo systemctl enable caddy
log_success "Caddy configured and started"

# ============================================================================
# Step 10: Install and Start API Service
# ============================================================================
log_info "Step 10/10: Installing API service..."

# Copy systemd service
sudo cp "$REPO_DIR/deploy/systemd/footballvision-api-enhanced.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable footballvision-api-enhanced
# Clear any prior start-limit failure state before restart.
sudo systemctl reset-failed footballvision-api-enhanced || true
sudo systemctl restart footballvision-api-enhanced

# Wait for service to start
sleep 3

# Check service status
if systemctl is-active --quiet footballvision-api-enhanced; then
    log_success "API service started successfully"
else
    log_error "API service failed to start. Check logs: journalctl -u footballvision-api-enhanced"
    exit 1
fi

# ============================================================================
# Validation
# ============================================================================
echo
log_info "Running validation checks..."

# Check API endpoint
if curl -s http://localhost:8000/api/v1/status > /dev/null 2>&1; then
    log_success "API endpoint responding"
else
    log_warning "API endpoint not responding yet (may need a moment to start)"
fi

# ============================================================================
# Installation Complete!
# ============================================================================
echo
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           Installation Complete!                         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo
log_success "FootballVision Pro v3 has been installed successfully!"
echo
echo "Next steps:"
echo "  1. If you were added to the video group, LOG OUT and back in"
echo "  2. Restart nvargus-daemon: sudo systemctl restart nvargus-daemon"
echo "  3. Access the web UI at: http://$(hostname -I | awk '{print $1}')"
echo "  4. Check service status: sudo systemctl status footballvision-api-enhanced"
echo
echo "Useful commands:"
echo "  - View API logs: journalctl -u footballvision-api-enhanced -f"
echo "  - Check cameras: ls -la /dev/video*"
echo "  - Test API: curl http://localhost:8000/api/v1/status"
echo
log_info "For troubleshooting, see: docs/TROUBLESHOOTING.md"
echo

#!/bin/bash
# FootballVision Pro - System Validation Script
# Run after installation to verify everything is working correctly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Logging
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓ PASS]${NC} $1"; PASSED=$((PASSED+1)); }
log_warning() { echo -e "${YELLOW}[⚠ WARN]${NC} $1"; WARNINGS=$((WARNINGS+1)); }
log_error() { echo -e "${RED}[✗ FAIL]${NC} $1"; FAILED=$((FAILED+1)); }

# Banner
echo "╔══════════════════════════════════════════════════════════╗"
echo "║      FootballVision Pro - System Validation             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo

# ============================================================================
# Check 1: Hardware Detection
# ============================================================================
log_info "Checking hardware..."

if [ -f "/etc/nv_tegra_release" ]; then
    log_success "Running on NVIDIA Jetson device"
else
    log_error "Not a Jetson device - /etc/nv_tegra_release not found"
fi

# ============================================================================
# Check 2: Required Directories
# ============================================================================
log_info "Checking required directories..."

for dir in /var/log/footballvision/api /var/log/footballvision/system /var/www/footballvision /mnt/recordings /dev/shm/hls /var/lock/footballvision; do
    if [ -d "$dir" ]; then
        log_success "Directory exists: $dir"
    else
        log_error "Directory missing: $dir"
    fi
done

# Check directory permissions
if [ -w /var/lock/footballvision ]; then
    log_success "Lock directory is writable"
else
    log_error "Lock directory not writable: /var/lock/footballvision"
fi

# ============================================================================
# Check 3: System Packages
# ============================================================================
log_info "Checking system packages..."

for pkg in python3-gi gir1.2-gstreamer-1.0 gstreamer1.0-tools caddy; do
    if dpkg -l | grep -q "^ii  $pkg"; then
        log_success "Package installed: $pkg"
    else
        log_error "Package missing: $pkg"
    fi
done

# ============================================================================
# Check 4: Python Dependencies
# ============================================================================
log_info "Checking Python dependencies..."

for module in fastapi uvicorn pydantic psutil prometheus_client; do
    if python3 -c "import $module" 2>/dev/null; then
        log_success "Python module available: $module"
    else
        log_error "Python module missing: $module"
    fi
done

# Check PyGObject (special case)
if python3 -c "import gi; gi.require_version('Gst', '1.0')" 2>/dev/null; then
    log_success "Python GStreamer bindings available"
else
    log_error "Python GStreamer bindings missing (python3-gi)"
fi

# ============================================================================
# Check 5: Camera Detection
# ============================================================================
log_info "Checking cameras..."

CAMERA_COUNT=$(ls -1 /dev/video* 2>/dev/null | wc -l)
if [ "$CAMERA_COUNT" -ge 2 ]; then
    log_success "Found $CAMERA_COUNT camera devices"
    ls -la /dev/video* 2>/dev/null | while read line; do
        echo "  $line"
    done
else
    log_warning "Only found $CAMERA_COUNT camera device(s) - expected 2+"
fi

# Check video group membership
if groups $USER | grep -q video; then
    log_success "User $USER is in video group"
else
    log_error "User $USER NOT in video group (run: sudo usermod -aG video $USER)"
fi

# ============================================================================
# Check 6: nvargus-daemon
# ============================================================================
log_info "Checking nvargus-daemon..."

if systemctl is-active --quiet nvargus-daemon 2>/dev/null; then
    log_success "nvargus-daemon is running"
else
    log_warning "nvargus-daemon not running (may need: sudo systemctl restart nvargus-daemon)"
fi

# ============================================================================
# Check 7: API Service
# ============================================================================
log_info "Checking API service..."

if systemctl is-active --quiet footballvision-api-enhanced; then
    log_success "footballvision-api-enhanced service is running"

    # Check process
    API_PID=$(systemctl show -p MainPID footballvision-api-enhanced | cut -d= -f2)
    if [ "$API_PID" != "0" ]; then
        log_success "API process running with PID: $API_PID"
    fi
else
    log_error "footballvision-api-enhanced service NOT running"
fi

# Check if service is enabled
if systemctl is-enabled --quiet footballvision-api-enhanced; then
    log_success "API service is enabled at boot"
else
    log_warning "API service not enabled at boot"
fi

# ============================================================================
# Check 8: Caddy Service
# ============================================================================
log_info "Checking Caddy service..."

if systemctl is-active --quiet caddy; then
    log_success "Caddy web server is running"
else
    log_error "Caddy web server NOT running"
fi

if systemctl is-enabled --quiet caddy; then
    log_success "Caddy service is enabled at boot"
else
    log_warning "Caddy service not enabled at boot"
fi

# ============================================================================
# Check 9: API Endpoints
# ============================================================================
log_info "Checking API endpoints..."

# Status endpoint
if curl -s -f http://localhost:8000/api/v1/status > /dev/null 2>&1; then
    log_success "API status endpoint responding"

    # Get detailed status
    STATUS_JSON=$(curl -s http://localhost:8000/api/v1/status)
    echo "  Status: $STATUS_JSON"
else
    log_error "API status endpoint NOT responding"
fi

# Pipeline state endpoint
if curl -s -f http://localhost:8000/api/v1/pipeline-state > /dev/null 2>&1; then
    log_success "Pipeline state endpoint responding"

    PIPELINE_STATE=$(curl -s http://localhost:8000/api/v1/pipeline-state)
    echo "  State: $PIPELINE_STATE"
else
    log_error "Pipeline state endpoint NOT responding"
fi

# ============================================================================
# Check 10: Web UI
# ============================================================================
log_info "Checking web UI..."

if [ -f "/var/www/footballvision/index.html" ]; then
    log_success "Web UI files deployed"
else
    log_error "Web UI files missing in /var/www/footballvision"
fi

# Check if UI is accessible via Caddy
if curl -s -f http://localhost/ > /dev/null 2>&1; then
    log_success "Web UI accessible via Caddy"
else
    log_error "Web UI NOT accessible via Caddy"
fi

# ============================================================================
# Check 11: GStreamer Plugins
# ============================================================================
log_info "Checking GStreamer plugins..."

# Check nvv4l2camerasrc (critical for cameras)
if gst-inspect-1.0 nvv4l2camerasrc > /dev/null 2>&1; then
    log_success "GStreamer nvv4l2camerasrc plugin available"
else
    log_error "GStreamer nvv4l2camerasrc plugin MISSING"
fi

# Check nvvidconv (critical for colorspace conversion)
if gst-inspect-1.0 nvvidconv > /dev/null 2>&1; then
    log_success "GStreamer nvvidconv plugin available"
else
    log_error "GStreamer nvvidconv plugin MISSING"
fi

# Check x264enc (software encoder)
if gst-inspect-1.0 x264enc > /dev/null 2>&1; then
    log_success "GStreamer x264enc plugin available"
else
    log_error "GStreamer x264enc plugin MISSING"
fi

# Check splitmuxsink (for recording)
if gst-inspect-1.0 splitmuxsink > /dev/null 2>&1; then
    log_success "GStreamer splitmuxsink plugin available"
else
    log_error "GStreamer splitmuxsink plugin MISSING"
fi

# ============================================================================
# Check 12: Node.js and npm
# ============================================================================
log_info "Checking Node.js..."

if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    NODE_MAJOR=$(echo $NODE_VERSION | cut -d'v' -f2 | cut -d'.' -f1)

    if [ "$NODE_MAJOR" -ge 20 ]; then
        log_success "Node.js $NODE_VERSION installed"
    else
        log_warning "Node.js version $NODE_VERSION is older than recommended 20.x"
    fi
else
    log_error "Node.js NOT installed"
fi

# ============================================================================
# Summary
# ============================================================================
echo
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                 Validation Summary                       ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo
echo -e "${GREEN}Passed:${NC}   $PASSED"
echo -e "${YELLOW}Warnings:${NC} $WARNINGS"
echo -e "${RED}Failed:${NC}   $FAILED"
echo

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ System validation PASSED - FootballVision Pro is ready!${NC}"
    echo
    echo "Access the web UI at: http://$(hostname -I | awk '{print $1}')"
    exit 0
else
    echo -e "${RED}✗ System validation FAILED - please address the errors above${NC}"
    echo
    echo "For troubleshooting, see: docs/TROUBLESHOOTING.md"
    echo "View API logs: journalctl -u footballvision-api-enhanced -f"
    exit 1
fi

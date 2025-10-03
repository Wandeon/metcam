#!/bin/bash
#
# FootballVision Pro Platform Installer
# Complete web UI + API deployment for NVIDIA Jetson Orin Nano
#

set -e

echo "========================================="
echo "FootballVision Pro Platform Installer"
echo "========================================="
echo ""

# Check if NOT running as root
if [ "$EUID" -eq 0 ]; then
  echo "ERROR: Do not run this script as root. It will use sudo when needed."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$(dirname "$PLATFORM_ROOT")")"

echo "Platform root: $PLATFORM_ROOT"
echo "Project root: $PROJECT_ROOT"
echo ""

# Install system dependencies
echo "[1/7] Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y nginx

echo "✓ Nginx installed"
echo ""

# Python dependencies already installed from backend setup
echo "[2/7] Verifying Python dependencies..."
python3 -c "import fastapi, uvicorn" 2>/dev/null && echo "✓ Python dependencies verified" || {
    echo "Installing Python dependencies..."
    pip3 install --user fastapi uvicorn[standard] pydantic
}
echo ""

# Create recordings directory
echo "[3/7] Setting up recordings directory..."
RECORDINGS_DIR="/mnt/recordings"
sudo mkdir -p "$RECORDINGS_DIR"
sudo chown $USER:$USER "$RECORDINGS_DIR"
chmod 755 "$RECORDINGS_DIR"

echo "✓ Recordings directory: $RECORDINGS_DIR"
echo ""

# Verify API service
echo "[4/7] Configuring API service..."
if [ -f /etc/systemd/system/footballvision-api.service ]; then
    echo "✓ API service already configured"
else
    sudo cp "$PROJECT_ROOT/deploy/footballvision-api.service" /etc/systemd/system/
    sudo systemctl daemon-reload
fi
sudo systemctl enable footballvision-api
sudo systemctl restart footballvision-api
echo "✓ API service running"
echo ""

# Deploy web UI
echo "[5/7] Deploying web UI..."
WEB_ROOT="/var/www/footballvision"
sudo mkdir -p "$WEB_ROOT"

# Check if dist exists
if [ ! -d "$PLATFORM_ROOT/web-dashboard/dist" ]; then
    echo "Building web UI..."
    cd "$PLATFORM_ROOT/web-dashboard"
    npm run build
fi

sudo cp -r "$PLATFORM_ROOT/web-dashboard/dist/"* "$WEB_ROOT/"
sudo chown -R www-data:www-data "$WEB_ROOT"

echo "✓ Web UI deployed to $WEB_ROOT"
echo ""

# Configure Nginx
echo "[6/7] Configuring Nginx..."

sudo tee /etc/nginx/sites-available/footballvision > /dev/null <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    root /var/www/footballvision;
    index index.html;

    # Serve static files
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Serve recording files for download
    location /recordings/ {
        alias /mnt/recordings/;
        autoindex on;
        add_header Content-Disposition 'attachment';
    }
}
EOF

# Enable site
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/footballvision /etc/nginx/sites-enabled/

# Test and restart Nginx
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx

echo "✓ Nginx configured and restarted"
echo ""

# Set CPU governor
echo "[7/7] Setting CPU to performance mode..."
echo "performance" | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor > /dev/null
echo "✓ CPU governor set to performance"
echo ""

# Get IP address
JETSON_IP=$(hostname -I | awk '{print $1}')

# Final checks
echo "Running final checks..."
sleep 2

API_STATUS=$(curl -s http://localhost:8000/api/v1/status 2>/dev/null | grep -q "status" && echo "OK" || echo "FAILED")
WEB_STATUS=$(curl -s -I http://localhost/ 2>/dev/null | head -1 | grep -q "200" && echo "OK" || echo "FAILED")

echo ""
echo "========================================="
echo "Installation Complete!"
echo "========================================="
echo ""
echo "FootballVision Pro is now running!"
echo ""
echo "Web Interface:"
echo "  Local:    http://localhost"
echo "  Network:  http://$JETSON_IP"
echo ""
echo "Login Password: 'admin' or 'footballvision'"
echo ""
echo "System Status:"
echo "  API Backend:  $API_STATUS"
echo "  Web UI:       $WEB_STATUS"
echo ""
echo "Service Management:"
echo "  API:    sudo systemctl status footballvision-api"
echo "  Nginx:  sudo systemctl status nginx"
echo "  Logs:   sudo journalctl -u footballvision-api -f"
echo ""
echo "Recording Files:"
echo "  Location:   /mnt/recordings"
echo "  Web Access: http://$JETSON_IP/recordings/"
echo ""
echo "========================================="
#!/bin/bash
# Deploy enhanced FootballVision Pro API with mode support

set -e

echo "================================"
echo "FootballVision Pro Enhanced API Deployment"
echo "================================"
echo

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo "Please run as regular user (will use sudo when needed)"
   exit 1
fi

# Paths
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
API_SCRIPT="$REPO_DIR/src/platform/simple_api_enhanced.py"
SERVICE_NAME="footballvision-api-enhanced"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "1. Installing Python dependencies..."
pip3 install fastapi uvicorn python-multipart prometheus-fastapi-instrumentator psutil python-dotenv

echo
echo "2. Creating systemd service..."
sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=FootballVision Pro Enhanced API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$REPO_DIR
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$REPO_DIR/src"
ExecStart=/usr/bin/python3 $API_SCRIPT
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo
echo "3. Reloading systemd..."
sudo systemctl daemon-reload

echo
echo "4. Stopping old API if running..."
sudo systemctl stop footballvision-api 2>/dev/null || true

echo
echo "5. Starting enhanced API..."
sudo systemctl restart $SERVICE_NAME
sudo systemctl enable $SERVICE_NAME

echo
echo "6. Checking service status..."
sleep 2
sudo systemctl status $SERVICE_NAME --no-pager

echo
echo "7. Testing API endpoints..."
sleep 2

# Test health endpoint
echo "Testing health endpoint..."
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool | head -10

echo
echo "Testing modes endpoint..."
curl -s http://localhost:8000/api/v1/modes | python3 -m json.tool | head -20

echo
echo "================================"
echo "Deployment Complete!"
echo "================================"
echo
echo "Enhanced API is running at: http://localhost:8000"
echo "Access from browser: http://$(hostname -I | awk '{print $1}'):8000"
echo
echo "New features available:"
echo "  - Mode switching: /api/v1/modes"
echo "  - Setup mode: /api/v1/setup/start"
echo "  - No-crop recording and preview"
echo
echo "To view logs: sudo journalctl -u $SERVICE_NAME -f"
echo "To restart: sudo systemctl restart $SERVICE_NAME"
echo "To stop: sudo systemctl stop $SERVICE_NAME"
echo
echo "UI should now show mode selection controls at:"
echo "  http://vid.nk-otok.hr"
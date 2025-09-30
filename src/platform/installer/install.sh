#!/bin/bash
#
# FootballVision Pro Platform Installer
# One-click installation script for NVIDIA Jetson Orin Nano
#

set -e

echo "========================================="
echo "FootballVision Pro Platform Installer"
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# Detect system
echo "Detecting system..."
if [ ! -f /etc/nv_tegra_release ]; then
  echo "Warning: This doesn't appear to be a Jetson device"
  read -p "Continue anyway? (y/n) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# Install system dependencies
echo ""
echo "Installing system dependencies..."
apt-get update
apt-get install -y \
  python3.11 \
  python3-pip \
  python3-venv \
  nodejs \
  npm \
  sqlite3 \
  nginx \
  supervisor \
  git

# Create application directory
echo ""
echo "Creating application directories..."
mkdir -p /opt/footballvision
mkdir -p /var/lib/footballvision/recordings
mkdir -p /var/log/footballvision

# Set permissions
chown -R $SUDO_USER:$SUDO_USER /opt/footballvision
chown -R $SUDO_USER:$SUDO_USER /var/lib/footballvision
chown -R $SUDO_USER:$SUDO_USER /var/log/footballvision

# Copy application files
echo ""
echo "Installing application files..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -r "$SCRIPT_DIR/../api-server" /opt/footballvision/
cp -r "$SCRIPT_DIR/../web-dashboard" /opt/footballvision/
cp -r "$SCRIPT_DIR/../database" /opt/footballvision/

# Setup Python virtual environment
echo ""
echo "Setting up Python environment..."
cd /opt/footballvision/api-server
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Initialize database
echo ""
echo "Initializing database..."
python3 -c "
from database.db_manager import init_database
init_database('/var/lib/footballvision/data.db')
print('Database initialized successfully')
"

# Build frontend
echo ""
echo "Building web dashboard..."
cd /opt/footballvision/web-dashboard
npm install
npm run build

# Configure Nginx
echo ""
echo "Configuring Nginx..."
cat > /etc/nginx/sites-available/footballvision <<'EOF'
server {
    listen 80;
    server_name _;

    # Frontend
    location / {
        root /opt/footballvision/web-dashboard/dist;
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

ln -sf /etc/nginx/sites-available/footballvision /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

# Configure Supervisor
echo ""
echo "Configuring service..."
cat > /etc/supervisor/conf.d/footballvision-api.conf <<'EOF'
[program:footballvision-api]
command=/opt/footballvision/api-server/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8080
directory=/opt/footballvision/api-server
user=nobody
autostart=true
autorestart=true
stderr_logfile=/var/log/footballvision/api.err.log
stdout_logfile=/var/log/footballvision/api.out.log
EOF

supervisorctl reread
supervisorctl update
supervisorctl start footballvision-api

# Enable services on boot
systemctl enable nginx
systemctl enable supervisor

# Get IP address
IP_ADDR=$(hostname -I | awk '{print $1}')

echo ""
echo "========================================="
echo "Installation Complete!"
echo "========================================="
echo ""
echo "Access the dashboard at:"
echo "  http://$IP_ADDR"
echo ""
echo "Default credentials:"
echo "  Email: admin@localhost"
echo "  Password: admin123"
echo ""
echo "IMPORTANT: Change the default password immediately!"
echo ""
echo "Services:"
echo "  API: http://$IP_ADDR/api/docs"
echo "  Status: supervisorctl status footballvision-api"
echo "  Logs: tail -f /var/log/footballvision/api.out.log"
echo ""
echo "========================================="
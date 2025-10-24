# Development Workflow

## Overview

FootballVision Pro uses a **multi-environment setup** that allows safe development and testing on the production device without risk to the live system. This workflow provides:

- **Zero-risk development**: Production remains untouched during development
- **Real hardware testing**: Test with actual cameras before deployment
- **Seamless deployment**: One-command deployment with automatic backups
- **Emergency rollback**: Quick restoration from any backup

## Architecture

### Environment Separation

| Environment | Directory | Port | Service | Branch |
|------------|-----------|------|---------|--------|
| **Production** | `/home/mislav/footballvision-pro` | 8000 | `footballvision-api-enhanced` | `pipeline-native-60fps` |
| **Development** | `/home/mislav/footballvision-dev` | 8001 | `footballvision-api-dev` | `dev` |

### Key Features

- **Systemd Conflicts**: Services use `Conflicts=` directive to ensure only one can access cameras
- **Port Differentiation**: Production (8000) vs Development (8001) via `API_PORT` env var
- **Automatic Backups**: Every deployment creates timestamped backup for rollback
- **Git-Based**: All deployments pull from GitHub (single source of truth)

## Initial Setup

### 1. Clone Development Environment

```bash
cd /home/mislav
git clone https://github.com/Wandeon/metcam.git footballvision-dev
cd footballvision-dev
git checkout pipeline-native-60fps
git checkout -b dev
```

### 2. Install Development Service

```bash
sudo cp /home/mislav/footballvision-pro/deploy/systemd/footballvision-api-dev.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### 3. Create Log Directory

```bash
sudo mkdir -p /var/log/footballvision-dev/api
sudo chown -R mislav:mislav /var/log/footballvision-dev
```

### 4. Make Helper Scripts Executable

```bash
chmod +x ~/switch-to-dev.sh
chmod +x ~/switch-to-prod.sh
chmod +x ~/deploy-to-prod.sh
chmod +x ~/rollback-prod.sh
```

## Daily Development Workflow

### Step 1: Switch to Development Environment

```bash
~/switch-to-dev.sh
```

This will:
- Stop production API
- Wait for cameras to release (3 seconds)
- Start development API on port 8001
- Verify success

**Development API**: http://192.168.x.x:8001
**Logs**: `journalctl -u footballvision-api-dev -f`

### Step 2: Make Changes

Work in `/home/mislav/footballvision-dev`:

```bash
cd ~/footballvision-dev

# Create feature branch from dev
git checkout -b feature/my-improvement

# Make your changes
vim src/platform/simple_api_v3.py

# Test with real hardware
curl http://localhost:8001/api/v1/status
curl http://localhost:8001/api/v1/pipeline-state
```

### Step 3: Test Thoroughly

- Test all functionality with actual cameras
- Check logs: `journalctl -u footballvision-api-dev -f`
- Test preview streaming: http://192.168.x.x:8001/preview
- Test recording: `curl -X POST http://localhost:8001/api/v1/control/start`
- Verify mutual exclusion (preview stops when recording starts)

### Step 4: Commit and Push

```bash
# Commit your changes
git add .
git commit -m "feat: Description of improvement"

# Push to GitHub
git push origin feature/my-improvement

# Merge to dev branch (or create PR)
git checkout dev
git merge feature/my-improvement
git push origin dev
```

### Step 5: Deploy to Production

When satisfied with testing:

```bash
# First, ensure production branch has your changes
cd ~/footballvision-pro
git checkout pipeline-native-60fps
git pull origin pipeline-native-60fps

# Option A: If dev → production merge done on GitHub
# Production already has latest code

# Option B: If merging locally
cd ~/footballvision-dev
git checkout pipeline-native-60fps
git merge dev
git push origin pipeline-native-60fps

# Deploy to production
~/deploy-to-prod.sh
```

The deployment script will:
1. Show current production and GitHub states
2. Ask for confirmation
3. Create automatic backup
4. Pull latest code from GitHub
5. Update dependencies (if changed)
6. Build web dashboard
7. Deploy and restart service
8. Verify deployment success

### Step 6: Switch Back to Production

```bash
~/switch-to-prod.sh
```

This restores the production environment:
- Stops development API
- Starts production API on port 8000
- Verifies success

## Helper Scripts Reference

### switch-to-dev.sh

**Purpose**: Activate development environment for testing

**Usage**:
```bash
~/switch-to-dev.sh
```

**What it does**:
- Stops production service
- Waits 3 seconds for camera release
- Starts development service (port 8001)
- Verifies success

**When to use**: When you want to test changes on real hardware

---

### switch-to-prod.sh

**Purpose**: Return to production environment

**Usage**:
```bash
~/switch-to-prod.sh
```

**What it does**:
- Stops development service
- Waits 3 seconds for camera release
- Starts production service (port 8000)
- Verifies success

**When to use**: After development testing, to restore normal operation

---

### deploy-to-prod.sh

**Purpose**: Deploy tested code from GitHub to production

**Usage**:
```bash
~/deploy-to-prod.sh
```

**What it does**:
1. Shows current development and production states
2. Asks for confirmation
3. Stops all services
4. Creates automatic backup (`/home/mislav/footballvision-backup-YYYYMMDD_HHMMSS`)
5. Pulls latest code from `origin/pipeline-native-60fps`
6. Updates Python dependencies (if `requirements.txt` changed)
7. Updates npm dependencies (if `package.json` changed)
8. Builds web dashboard
9. Deploys to `/var/www/footballvision/`
10. Starts production service
11. Verifies API responds correctly

**When to use**: When you've tested changes and want to deploy to production

**Safety features**:
- Automatic backup before deployment
- Dependency change detection
- API health verification
- Rollback instructions on failure

---

### rollback-prod.sh

**Purpose**: Emergency restoration from backup

**Usage**:
```bash
~/rollback-prod.sh
```

**What it does**:
1. Lists available backups (5 most recent)
2. Shows details: date, size, branch, commit
3. Asks for selection
4. Asks for confirmation
5. Stops production service
6. Backs up current (broken) state
7. Restores from selected backup
8. Rebuilds web dashboard
9. Starts production service
10. Verifies success

**When to use**:
- Deployment caused issues
- Need to restore to known-good state
- Emergency recovery

**Safety features**:
- Current state is backed up before rollback
- Interactive selection with confirmation
- Full verification after restoration

## Troubleshooting

### Service Won't Start

**Symptom**: `footballvision-api-enhanced` or `footballvision-api-dev` fails to start

**Check logs**:
```bash
# Production
journalctl -u footballvision-api-enhanced -n 100

# Development
journalctl -u footballvision-api-dev -n 100
```

**Common causes**:

1. **Cameras locked by another process**
   ```bash
   # Check what's using cameras
   sudo lsof /dev/video*

   # Restart camera daemon
   sudo systemctl restart nvargus-daemon
   sudo systemctl restart footballvision-api-enhanced
   ```

2. **Port already in use**
   ```bash
   # Check what's using port 8000
   sudo lsof -i :8000

   # Or port 8001
   sudo lsof -i :8001
   ```

3. **File lock not released**
   ```bash
   # Check locks
   ls -la /var/lock/footballvision/

   # Remove stale locks (if service is stopped)
   sudo rm /var/lock/footballvision/*.lock
   ```

### API Not Responding

**Symptom**: Service is running but API returns errors

**Checks**:
```bash
# Test API directly
curl -v http://localhost:8000/api/v1/status

# Check system resources
htop
nvidia-smi  # GPU usage

# Check pipeline state
curl http://localhost:8000/api/v1/pipeline-state
```

**Solutions**:
```bash
# Restart nvargus daemon
sudo systemctl restart nvargus-daemon
sudo systemctl restart footballvision-api-enhanced

# Check camera permissions
ls -la /dev/video*
groups mislav  # Should include 'video'
```

### Preview/Recording Conflicts

**Symptom**: Preview doesn't stop when recording starts, or vice versa

**This should not happen** - `pipeline_manager.py` enforces mutual exclusion with file locks.

**Debug**:
```bash
# Check locks
ls -la /var/lock/footballvision/

# View lock acquisition in logs
journalctl -u footballvision-api-enhanced -f | grep -i lock
```

**Solution**:
```bash
# Stop service
sudo systemctl stop footballvision-api-enhanced

# Clear locks
sudo rm /var/lock/footballvision/*.lock

# Restart
sudo systemctl start footballvision-api-enhanced
```

### Web Dashboard Not Updating

**Symptom**: Changes to web dashboard not visible

**Check**:
```bash
# Verify build completed
cd ~/footballvision-pro/src/platform/web-dashboard
ls -la dist/

# Verify deployment
ls -la /var/www/footballvision/

# Check Caddy
sudo systemctl status caddy
```

**Solution**:
```bash
# Rebuild and redeploy
cd ~/footballvision-pro/src/platform/web-dashboard
npm run build
sudo rsync -a --delete dist/ /var/www/footballvision/

# Restart Caddy
sudo systemctl restart caddy

# Clear browser cache (Ctrl+Shift+R)
```

### Deployment Failed

**Symptom**: `deploy-to-prod.sh` reported failure

**Immediate action**:
```bash
# Rollback to last working backup
~/rollback-prod.sh
```

**Then investigate**:
```bash
# Check what changed
cd ~/footballvision-pro
git log -5 --oneline

# Check for conflicts
git status

# Review logs
journalctl -u footballvision-api-enhanced -n 200
```

## Git Workflow

### Branch Strategy

```
main (stable releases)
  ↓
pipeline-native-60fps (production branch)
  ↓
dev (active development)
  ↓
feature/* (feature branches)
```

### Development Process

1. **Create feature branch**:
   ```bash
   cd ~/footballvision-dev
   git checkout dev
   git pull origin dev
   git checkout -b feature/my-improvement
   ```

2. **Work and test**:
   ```bash
   # Make changes
   # Test with ~/switch-to-dev.sh
   git add .
   git commit -m "feat: Description"
   ```

3. **Push and merge**:
   ```bash
   git push origin feature/my-improvement

   # Merge to dev (locally or via PR)
   git checkout dev
   git merge feature/my-improvement
   git push origin dev
   ```

4. **Deploy to production**:
   ```bash
   # Merge dev → pipeline-native-60fps (on GitHub or locally)
   git checkout pipeline-native-60fps
   git merge dev
   git push origin pipeline-native-60fps

   # Deploy
   ~/deploy-to-prod.sh
   ```

## System Maintenance

### Backup Management

Backups are created automatically but accumulate over time:

```bash
# List backups
ls -lh /home/mislav/footballvision-backup-*

# Check backup sizes
du -sh /home/mislav/footballvision-backup-*

# Remove old backups (keep last 5)
ls -t /home/mislav/footballvision-backup-* | tail -n +6 | xargs rm -rf
```

### Log Management

```bash
# View service logs
journalctl -u footballvision-api-enhanced -n 100
journalctl -u footballvision-api-dev -n 100

# Check log sizes
sudo du -sh /var/log/footballvision*

# Rotate logs (systemd does this automatically)
sudo journalctl --vacuum-time=7d
```

### Disk Space

```bash
# Check available space
df -h

# Large directories
du -sh /home/mislav/footballvision-*
du -sh /mnt/recordings/*
du -sh /var/log/footballvision*

# Clean recordings (if needed)
rm -rf /mnt/recordings/old-match-*
```

## Best Practices

1. **Always test in development first**: Never make changes directly in production
2. **Use feature branches**: Keep dev branch stable, use feature/* for experiments
3. **Commit frequently**: Small, focused commits are easier to debug
4. **Keep backups**: Don't delete backups until new deployment is verified
5. **Monitor logs**: Check logs after deployment for warnings/errors
6. **Document changes**: Update docs when adding features or changing behavior
7. **Test mutual exclusion**: Verify preview/recording cannot run simultaneously
8. **Verify API health**: Always test `/api/v1/status` after deployment

## Quick Reference

### Common Commands

```bash
# Switch environments
~/switch-to-dev.sh                              # Activate development
~/switch-to-prod.sh                             # Return to production

# Deploy
~/deploy-to-prod.sh                             # Deploy tested code
~/rollback-prod.sh                              # Emergency rollback

# Check status
systemctl status footballvision-api-enhanced    # Production status
systemctl status footballvision-api-dev         # Development status

# View logs
journalctl -u footballvision-api-enhanced -f    # Production logs (live)
journalctl -u footballvision-api-dev -f         # Development logs (live)

# Test API
curl http://localhost:8000/api/v1/status        # Production API
curl http://localhost:8001/api/v1/status        # Development API

# Camera management
sudo systemctl restart nvargus-daemon           # Reset camera daemon
sudo lsof /dev/video*                           # Check camera usage
ls -la /var/lock/footballvision/                # Check pipeline locks
```

### URLs

| Service | Production | Development |
|---------|-----------|-------------|
| **API** | http://192.168.x.x:8000 | http://192.168.x.x:8001 |
| **Web UI** | http://192.168.x.x | http://192.168.x.x:8080 (if configured) |
| **Preview** | http://192.168.x.x:8000/preview | http://192.168.x.x:8001/preview |
| **Docs** | http://192.168.x.x:8000/docs | http://192.168.x.x:8001/docs |

### File Locations

| Item | Location |
|------|----------|
| **Production Code** | `/home/mislav/footballvision-pro` |
| **Development Code** | `/home/mislav/footballvision-dev` |
| **Web Dashboard** | `/var/www/footballvision/` |
| **Backups** | `/home/mislav/footballvision-backup-*` |
| **Production Logs** | `journalctl -u footballvision-api-enhanced` |
| **Development Logs** | `journalctl -u footballvision-api-dev` |
| **Pipeline Locks** | `/var/lock/footballvision/` |
| **Recordings** | `/mnt/recordings/` |

## Emergency Procedures

### Complete System Reset

If everything is broken:

```bash
# 1. Stop all services
sudo systemctl stop footballvision-api-enhanced
sudo systemctl stop footballvision-api-dev

# 2. Reset camera daemon
sudo systemctl restart nvargus-daemon

# 3. Clear locks
sudo rm -f /var/lock/footballvision/*.lock

# 4. Rollback to last known good
~/rollback-prod.sh

# 5. Verify
curl http://localhost:8000/api/v1/status
```

### Nuclear Option: Fresh Production Clone

If production is completely corrupted:

```bash
# 1. Stop services
sudo systemctl stop footballvision-api-enhanced

# 2. Backup current state (just in case)
mv /home/mislav/footballvision-pro /home/mislav/footballvision-broken-$(date +%Y%m%d_%H%M%S)

# 3. Fresh clone
cd /home/mislav
git clone https://github.com/Wandeon/metcam.git footballvision-pro
cd footballvision-pro
git checkout pipeline-native-60fps

# 4. Install dependencies
pip3 install -r requirements.txt
cd src/platform/web-dashboard
npm install
npm run build

# 5. Deploy web dashboard
sudo rsync -a --delete dist/ /var/www/footballvision/

# 6. Start production
sudo systemctl start footballvision-api-enhanced

# 7. Verify
curl http://localhost:8000/api/v1/status
```

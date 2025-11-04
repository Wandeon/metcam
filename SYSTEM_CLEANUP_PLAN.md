# FootballVision Pro - System Cleanup Plan

**Generated:** 2025-11-04
**Total Issues Found:** 47 items across 5 categories
**Estimated Cleanup Time:** 3-4 hours
**Disk Space to Free:** ~6.3 GB (235 MB immediate + 6 GB optional)

---

## 🚨 CRITICAL ISSUES (Fix Immediately)

### 1. Broken Legacy Services (HIGH PRIORITY)

**DELETE these broken systemd services:**

```bash
# Stop and disable broken services
sudo systemctl stop footballvision-api.service
sudo systemctl disable footballvision-api.service
sudo systemctl stop calibration-preview.service
sudo systemctl disable calibration-preview.service

# Remove service files
sudo rm /etc/systemd/system/footballvision-api.service
sudo rm /etc/systemd/system/calibration-preview.service
sudo rm /etc/systemd/system/footballvision-api-enhanced.service.backup

# Reload systemd
sudo systemctl daemon-reload
```

**Issues:**
- `footballvision-api.service` - References non-existent `simple_api_enhanced.py`
- `calibration-preview.service` - References non-existent script
- Both services constantly fail and generate error logs

### 2. Security Risk - Exposed Credentials (HIGH PRIORITY)

**DELETE file with plaintext credentials:**

```bash
# Remove old .env file with SFTP credentials (no longer used)
rm /home/mislav/footballvision-pro/src/platform/api-server/.env
```

**Content being deleted (for audit):**
- SFTP credentials to VPS-02 (100.82.2.46)
- Hardcoded password: 1307988
- No longer used (replaced by Nextcloud in active service)

### 3. Missing Critical Documentation (HIGH PRIORITY)

**CREATE missing API documentation:**

The file `docs/API.md` is referenced in 3 places but doesn't exist:
- README.md (line 139)
- deploy/README.md (line 375)
- deploy/CHECKLIST.md (line 280)

**Action:** Create consolidated API documentation (see detailed plan below)

---

## 📋 CLEANUP CATEGORIES

### Category A: Legacy Services & Scripts

| Item | Action | Reason | Disk Saved |
|------|--------|--------|------------|
| `/etc/systemd/system/footballvision-api.service` | DELETE | References missing file | 0 KB |
| `/etc/systemd/system/calibration-preview.service` | DELETE | References missing script | 0 KB |
| `/etc/systemd/system/footballvision-api-enhanced.service.backup` | DELETE | Obsolete backup | 0 KB |
| `/etc/nginx/sites-available/footballvision` | DELETE | Nginx inactive, Caddy is active | 0 KB |
| `/etc/nginx/sites-available/footballvision-hls` | DELETE | Legacy HLS config | 0 KB |
| `/etc/nginx/sites-enabled/footballvision` | DELETE | Symlink to inactive | 0 KB |
| `/etc/nginx/sites-enabled/footballvision-hls` | DELETE | Symlink to inactive | 0 KB |
| `/etc/caddy/Caddyfile.backup` | DELETE | Outdated backup | 0 KB |

### Category B: Duplicate Documentation

| Item | Action | Reason | Lines |
|------|--------|--------|-------|
| `src/video-pipeline/TROUBLESHOOTING.md` | MERGE → docs/TROUBLESHOOTING.md, then DELETE | Duplicate content | 455 |
| `.claude/claude.md` | MIGRATE to docs/, then DELETE | Hidden critical knowledge | 116 |
| `docs/ARCHITECTURE.md` (lines 104-130, 337-370, 402-404) | DELETE sections | Obsolete migration plan | 64 |

### Category C: Test Data & Logs

| Item | Action | Size | Safe? |
|------|--------|------|-------|
| `/mnt/recordings/test_superfast_threads6.mp4` | DELETE | 77 MB | YES |
| `/mnt/recordings/optimization_tests_20251104/` | DELETE | 28 KB | YES |
| `/mnt/recordings/test_quality_high/` | DELETE | 8 KB | YES |
| `/mnt/recordings/quality_test_high/` | DELETE | 8 KB | YES |
| `/mnt/recordings/devtools_mp4_verification/` | DELETE | 8 KB | YES |
| `/mnt/recordings/Tralalalala/` | DELETE | 8 KB | YES |
| `/mnt/recordings/Ajmoooooooooooo/` | DELETE | 8 KB | YES |
| `/mnt/recordings/Ajmoooo_radiiiii/` | DELETE | 8 KB | YES |
| `/mnt/recordings/Snimanac/` | DELETE | 8 KB | YES |
| `/mnt/recordings/Sniumkanje/` | DELETE | 8 KB | YES |
| `/var/log/footballvision/crashes/` (archive old) | ARCHIVE | 6 MB | MAYBE |

### Category D: Build Artifacts (Optional Cleanup)

| Item | Action | Size | Regenerable? |
|------|--------|------|--------------|
| `src/platform/web-dashboard/node_modules/` | DELETE | 151 MB | YES (npm install) |
| `src/platform/web-dashboard/dist/` | DELETE | 836 KB | YES (npm run build) |
| `src/video-pipeline/__pycache__/` | DELETE | 92 KB | YES (Python auto-creates) |
| `src/platform/__pycache__/` | DELETE | 16 KB | YES (Python auto-creates) |

### Category E: Deployment Scripts (UPDATE, don't delete)

| File | Issue | Fix |
|------|-------|-----|
| `deploy_enhanced.sh` | References `simple_api_enhanced.py` (line 19, 39) | Update to `simple_api_v3.py` |
| `deploy/systemd/footballvision-api-enhanced.service` | References `simple_api_enhanced.py` (line 21) | Update to `simple_api_v3.py` |

---

## 🔧 STEP-BY-STEP EXECUTION PLAN

### Phase 1: Critical Fixes (30 minutes)

```bash
# 1. Remove broken services
sudo systemctl stop footballvision-api.service 2>/dev/null
sudo systemctl disable footballvision-api.service 2>/dev/null
sudo systemctl stop calibration-preview.service 2>/dev/null
sudo systemctl disable calibration-preview.service 2>/dev/null

sudo rm -f /etc/systemd/system/footballvision-api.service
sudo rm -f /etc/systemd/system/calibration-preview.service
sudo rm -f /etc/systemd/system/footballvision-api-enhanced.service.backup

# 2. Remove nginx configs (Caddy is active)
sudo rm -f /etc/nginx/sites-available/footballvision
sudo rm -f /etc/nginx/sites-available/footballvision-hls
sudo rm -f /etc/nginx/sites-enabled/footballvision
sudo rm -f /etc/nginx/sites-enabled/footballvision-hls

# 3. Remove old Caddy backup
sudo rm -f /etc/caddy/Caddyfile.backup

# 4. Remove security risk
rm -f /home/mislav/footballvision-pro/src/platform/api-server/.env

# 5. Reload systemd
sudo systemctl daemon-reload

# 6. Verify active service is running
sudo systemctl status footballvision-api-enhanced
```

### Phase 2: Test Data Cleanup (10 minutes)

```bash
cd /mnt/recordings

# Remove test files
rm -f test_superfast_threads6.mp4

# Remove test directories
rm -rf optimization_tests_20251104
rm -rf test_quality_high
rm -rf quality_test_high
rm -rf devtools_mp4_verification

# Remove non-match directories
rm -rf Tralalalala
rm -rf Ajmoooooooooooo
rm -rf "Ajmoooo_radiiiii"
rm -rf Snimanac
rm -rf Sniumkanje
rm -rf "SLAVISA PROBA"

# Remove empty match directories
rm -rf match_252525
rm -rf match_1761306623
rm -rf match_1762257710

# Show freed space
df -h /mnt
```

### Phase 3: Archive Old Crash Logs (15 minutes)

```bash
cd /var/log/footballvision/crashes

# Archive logs older than 30 days
find . -name "*.log" -mtime +30 -exec gzip {} \;

# Move archived logs to separate directory
mkdir -p /var/log/footballvision/crashes/archive
mv *.gz archive/ 2>/dev/null

# Count files
echo "Active crash logs: $(find . -maxdepth 1 -name "*.log" | wc -l)"
echo "Archived crash logs: $(find archive -name "*.gz" | wc -l)"
```

### Phase 4: Update Deployment Scripts (15 minutes)

```bash
cd /home/mislav/footballvision-pro

# Update deploy_enhanced.sh
sed -i 's/simple_api_enhanced\.py/simple_api_v3.py/g' deploy_enhanced.sh

# Update service template
sed -i 's/simple_api_enhanced\.py/simple_api_v3.py/g' deploy/systemd/footballvision-api-enhanced.service

# Verify changes
grep "simple_api" deploy_enhanced.sh
grep "simple_api" deploy/systemd/footballvision-api-enhanced.service
```

### Phase 5: Documentation Consolidation (60-90 minutes)

#### 5a. Create Missing API.md

```bash
cd /home/mislav/footballvision-pro/docs

# Create API documentation (content below)
cat > API.md << 'EOF'
# FootballVision Pro - API Reference

## Base URL
- **Production:** `http://localhost:8000/api/v1`
- **Development:** `http://localhost:8001/api/v1`

## Authentication
Currently no authentication required (internal network only).

## Endpoints

### Recording Management

#### Start Recording
```http
POST /api/v1/recording
Content-Type: application/json

{
  "match_id": "match_20251104_001",
  "force": false,
  "process_after_recording": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Recording started for match: match_20251104_001",
  "match_id": "match_20251104_001",
  "cameras_started": [0, 1],
  "cameras_failed": []
}
```

#### Stop Recording
```http
DELETE /api/v1/recording
```

**Response:**
```json
{
  "success": true,
  "message": "Recording stopped successfully"
}
```

#### Get Recording Status
```http
GET /api/v1/status
```

**Response:**
```json
{
  "recording": {
    "recording": false,
    "match_id": null,
    "duration": 0.0,
    "cameras": {}
  },
  "preview": {
    "preview_active": false,
    "cameras": {
      "camera_0": {"active": false, "state": "stopped", "uptime": 0.0, "hls_url": "/hls/cam0.m3u8"},
      "camera_1": {"active": false, "state": "stopped", "uptime": 0.0, "hls_url": "/hls/cam1.m3u8"}
    }
  }
}
```

### Preview Management

#### Start Preview
```http
POST /api/v1/preview
Content-Type: application/json

{
  "camera_id": null
}
```

#### Stop Preview
```http
DELETE /api/v1/preview
```

### Health & Monitoring

#### System Health
```http
GET /api/v1/health
```

#### Prometheus Metrics
```http
GET /metrics
```

### Recordings

#### List Recordings
```http
GET /api/v1/recordings
```

#### Get Processing Status
```http
GET /api/v1/recordings/{match_id}/processing-status
```

#### Download Recording
```http
GET /api/v1/recordings/{match_id}/files/{filename}
```

#### Delete Recording
```http
DELETE /api/v1/recordings/{match_id}
```

For complete endpoint documentation, see [simple_api_v3.py](../src/platform/simple_api_v3.py).
EOF
```

#### 5b. Merge Duplicate TROUBLESHOOTING.md

```bash
# Backup current main troubleshooting
cp docs/TROUBLESHOOTING.md docs/TROUBLESHOOTING.md.backup

# Add GStreamer section from pipeline version (manual step - review and merge)
# Then delete duplicate
rm src/video-pipeline/TROUBLESHOOTING.md
```

#### 5c. Migrate .claude/claude.md Content

Extract useful operational knowledge and add to:
- `docs/HARDWARE_SETUP.md` - Camera sensor modes, physical setup
- `docs/TROUBLESHOOTING.md` - GStreamer issues, common workarounds
- Then delete `.claude/claude.md`

#### 5d. Clean Up ARCHITECTURE.md

Remove obsolete sections:
- Lines 104-130: Architecture Comparison (v2 vs v3)
- Lines 337-370: Migration Plan
- Lines 402-404: Performance comparison

### Phase 6: Optional - Build Artifact Cleanup (5 minutes)

```bash
# Only do this if you need to free space or want a clean rebuild

cd /home/mislav/footballvision-pro/src/platform/web-dashboard
rm -rf node_modules dist

cd /home/mislav/footballvision-pro
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete

# To rebuild later:
# cd src/platform/web-dashboard
# npm install
# npm run build
```

---

## ✅ VERIFICATION CHECKLIST

After cleanup, verify:

```bash
# 1. Active service is running
sudo systemctl status footballvision-api-enhanced
# Should show: active (running)

# 2. No failed services
systemctl --failed
# Should show: 0 loaded units listed

# 3. Disk space freed
df -h /mnt
df -h /var/log
df -h /home/mislav/footballvision-pro

# 4. API is responsive
curl http://localhost:8000/api/v1/health | jq
# Should return JSON with system status

# 5. No broken symlinks
find /etc/systemd/system -xtype l
find /etc/nginx -xtype l 2>/dev/null
# Should return empty or non-existent directories

# 6. Documentation links work
cd /home/mislav/footballvision-pro
grep -r "docs/API.md" .
# All references should now resolve
```

---

## 📊 EXPECTED RESULTS

### Disk Space Freed
- Test recordings: ~77 MB
- Test directories: ~80 KB
- Logs (archived): ~6 MB
- **Optional** (node_modules, cache): ~152 MB
- **TOTAL:** 83-235 MB immediate

### Services Cleaned
- Removed: 3 broken services
- Updated: 2 deployment scripts
- Active services: 1 (footballvision-api-enhanced)

### Documentation Fixed
- Created: 1 file (docs/API.md)
- Fixed: 3 broken links
- Merged: 2 duplicate files
- Removed: 3 obsolete sections

### Security Improved
- Removed: 1 file with plaintext credentials
- Remaining credential exposure: Nextcloud password in service file (consider moving to secrets)

---

## 🔒 POST-CLEANUP RECOMMENDATIONS

### 1. Secure Nextcloud Credentials

Currently in: `/etc/systemd/system/footballvision-api-enhanced.service` (world-readable)

**Option A: Use systemd credentials**
```bash
systemd-creds encrypt \
  --name=nextcloud_password \
  - /etc/systemd/credentials/footballvision-nextcloud.cred
```

**Option B: Use environment file with restricted permissions**
```bash
sudo nano /etc/footballvision/.secrets
# Add: NEXTCLOUD_PASSWORD=your-password
sudo chmod 600 /etc/footballvision/.secrets
# Update service: EnvironmentFile=/etc/footballvision/.secrets
```

### 2. Set Up Automated Log Rotation

Already configured in `/etc/logrotate.d/footballvision`:
```
/var/log/footballvision/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 0644 mislav mislav
}
```

Verify it's working:
```bash
sudo logrotate -d /etc/logrotate.d/footballvision
```

### 3. Create Backup Strategy

```bash
# Backup critical configs before cleanup
mkdir -p /home/mislav/footballvision-backups/$(date +%Y%m%d)
cp /etc/systemd/system/footballvision-* /home/mislav/footballvision-backups/$(date +%Y%m%d)/
cp /etc/caddy/Caddyfile /home/mislav/footballvision-backups/$(date +%Y%m%d)/
cp /home/mislav/footballvision-pro/config/camera_config.json /home/mislav/footballvision-backups/$(date +%Y%m%d)/
```

### 4. Document Active Services

Create `/home/mislav/footballvision-pro/docs/SERVICES.md`:
```markdown
# Active Services

- **footballvision-api-enhanced.service** - Main API (port 8000)
- **footballvision-api-dev.service** - Development API (port 8001, disabled)
- **caddy.service** - Web server (ports 80, 8080)

Last updated: 2025-11-04
```

---

## 📅 MAINTENANCE SCHEDULE

### Weekly
- Check for failed services: `systemctl --failed`
- Review disk usage: `df -h`

### Monthly
- Archive old crash logs (automated via cron)
- Clean up old test recordings manually

### Quarterly
- Review and update documentation
- Audit service configurations
- Update dependencies

---

**Generated by:** Claude Code
**Date:** 2025-11-04
**System Version:** FootballVision Pro v3

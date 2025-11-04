# FootballVision Pro - Nextcloud Integration Guide

## Overview

This document explains how to set up automatic upload of processed football match recordings from the FootballVision Pro system to a Nextcloud instance at `drive.genai.hr`.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ FootballVision Pro Recording Workflow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. User starts recording with "Process after recording" ON    │
│     ↓                                                           │
│  2. Dual cameras record @ 2880x1752, 12 Mbps, 30fps           │
│     → Segments: 10-minute files (~2.7 GB each)                 │
│     → Storage: /mnt/recordings/{match_id}/segments/            │
│     ↓                                                           │
│  3. User stops recording                                        │
│     ↓                                                           │
│  4. Automatic post-processing starts (background)              │
│     → Merges all segments per camera                           │
│     → Re-encodes to 1920x1080, CRF 28, preset slower           │
│     → Output: cam0_archive.mp4 + cam1_archive.mp4             │
│     → Size: ~2.6 GB per camera (~5.2 GB total)                │
│     → Time: ~3-4 hours for 100-minute match                    │
│     ↓                                                           │
│  5. Automatic upload to Nextcloud (via WebDAV)                 │
│     → Destination: drive.genai.hr/FootballVision/YYYY-MM/      │
│     → Uploads both archive files                               │
│     → Original segments remain on device                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Device Information

- **Device Name**: MetCam / FootballVision Pro Edge Device
- **Platform**: NVIDIA Jetson (ARM64, Ubuntu 22.04)
- **Location**: On-site at football field
- **Network**: Local network (needs access to drive.genai.hr)
- **User**: mislav
- **Base Directory**: `/home/mislav/footballvision-pro/`

## Nextcloud Requirements

### 1. Nextcloud Instance
- **URL**: `https://drive.genai.hr`
- **Protocol**: WebDAV (Nextcloud standard)
- **Endpoint**: `/remote.php/dav/files/{username}/`

### 2. User Account Needed
The FootballVision device needs a dedicated Nextcloud user account with:
- **Username**: (to be provided)
- **Password**: (to be provided)
- **Permissions**:
  - Upload files (WebDAV PUT)
  - Create folders (WebDAV MKCOL)
  - Read/write access to base folder

### 3. Recommended Setup

**Option A: Dedicated Service Account (Recommended)**
```
Username: footballvision-uploader
Password: <strong-password>
Quota: Unlimited or sufficient for expected uploads
Role: Normal user (no admin needed)
```

**Option B: Shared Folder with App Password**
```
Create a shared folder accessible via app password
Use app-specific password for better security
```

### 4. Folder Structure

The system will automatically create this structure in Nextcloud:

```
FootballVision/
├── 2025-11/
│   ├── match_20251104_001/
│   │   ├── cam0_archive.mp4 (2.6 GB)
│   │   └── cam1_archive.mp4 (2.6 GB)
│   ├── match_20251104_002/
│   │   ├── cam0_archive.mp4 (2.6 GB)
│   │   └── cam1_archive.mp4 (2.6 GB)
├── 2025-12/
│   └── ...
```

Files are organized by:
- Year-Month (YYYY-MM)
- Match ID (e.g., match_20251104_001)

## Installation & Configuration

### Prerequisites Check

SSH into the FootballVision device:
```bash
ssh mislav@<device-ip>
```

Verify curl is available (should already be installed):
```bash
curl --version
# Expected: curl 7.81.0 or newer
```

### Step 1: Configure Nextcloud Credentials

**Method 1: Environment Variables (Recommended)**

Edit the API service file:
```bash
sudo nano /etc/systemd/system/footballvision-api-enhanced.service
```

Add these lines under the `[Service]` section:
```ini
Environment="NEXTCLOUD_USERNAME=footballvision-uploader"
Environment="NEXTCLOUD_PASSWORD=your-secure-password"
```

Reload and restart the service:
```bash
sudo systemctl daemon-reload
sudo systemctl restart footballvision-api-enhanced
```

**Method 2: Configuration File**

Create a config file:
```bash
sudo nano /home/mislav/footballvision-pro/.nextcloud_config
```

Add:
```
NEXTCLOUD_USERNAME=footballvision-uploader
NEXTCLOUD_PASSWORD=your-secure-password
```

Secure the file:
```bash
sudo chmod 600 /home/mislav/footballvision-pro/.nextcloud_config
sudo chown mislav:mislav /home/mislav/footballvision-pro/.nextcloud_config
```

Update the service to load this file (modify the service file):
```bash
EnvironmentFile=/home/mislav/footballvision-pro/.nextcloud_config
```

### Step 2: Verify Configuration

Check if credentials are loaded:
```bash
cd /home/mislav/footballvision-pro/src/video-pipeline
python3 << 'EOF'
from nextcloud_upload_service import get_nextcloud_upload_service
service = get_nextcloud_upload_service()
print(f"Nextcloud upload enabled: {service.enabled}")
print(f"Nextcloud URL: {service.nextcloud_url}")
print(f"Username configured: {service.username is not None}")
EOF
```

Expected output:
```
Nextcloud upload enabled: True
Nextcloud URL: https://drive.genai.hr
Username configured: True
```

### Step 3: Test Connection

Test WebDAV connection:
```bash
# Replace with actual credentials
curl -X PROPFIND \
  -u "username:password" \
  -k \
  "https://drive.genai.hr/remote.php/dav/files/username/"
```

Expected: XML response with folder listing (not 401 Unauthorized)

### Step 4: Test Upload (Optional)

Create a test file and upload:
```bash
cd /home/mislav/footballvision-pro/src/video-pipeline
python3 << 'EOF'
from nextcloud_upload_service import get_nextcloud_upload_service
from pathlib import Path

# Create a small test file
test_file = Path("/tmp/test_upload.txt")
test_file.write_text("FootballVision upload test")

service = get_nextcloud_upload_service()
result = service.upload_file(
    test_file,
    "FootballVision/test/test_upload.txt"
)

print(f"Upload success: {result}")
EOF
```

Check in Nextcloud web interface: `FootballVision/test/test_upload.txt` should exist

## Troubleshooting

### Issue 1: "Nextcloud upload disabled (no credentials)"

**Cause**: Environment variables not loaded

**Solution**:
```bash
# Check if service loaded environment
sudo systemctl show footballvision-api-enhanced | grep NEXTCLOUD

# If empty, credentials not loaded - check service file syntax
sudo systemctl status footballvision-api-enhanced
```

### Issue 2: Upload fails with "401 Unauthorized"

**Cause**: Invalid credentials

**Solution**:
- Verify username/password are correct
- Check if password contains special characters that need escaping
- Try logging into Nextcloud web interface with same credentials
- For app passwords: ensure the app password is active

### Issue 3: Upload fails with "SSL certificate problem"

**Cause**: Self-signed SSL certificate

**Solution**:
The code uses `-k` flag in curl to allow self-signed certs. If you want proper SSL verification, remove the `-k` flag from:
```python
# In nextcloud_upload_service.py, line ~72 and ~106
# Remove: '-k',
```

### Issue 4: Upload times out

**Cause**: Slow network or large files

**Solution**:
Increase timeout in `nextcloud_upload_service.py`:
```python
# Line ~84: increase from 7200 (2 hours)
timeout: int = 14400  # 4 hours
```

### Issue 5: Folder creation fails

**Cause**: Insufficient permissions

**Solution**:
Ensure Nextcloud user has write permissions to create folders in their home directory

## Network Requirements

The FootballVision device needs:

1. **Outbound HTTPS (443)** access to `drive.genai.hr`
2. **Stable connection** during upload (2-4 hours for 5GB upload)
3. **Bandwidth**: Minimum 3 Mbps upload (recommended 10+ Mbps)

### Bandwidth Calculation
- Archive size: ~5.2 GB per match
- Upload time at 3 Mbps: ~4 hours
- Upload time at 10 Mbps: ~70 minutes
- Upload time at 50 Mbps: ~14 minutes

## File Management

### Original Files
- **Location**: `/mnt/recordings/{match_id}/segments/`
- **Size**: ~18 GB per match (100 minutes)
- **Retention**: Manual deletion (not auto-deleted)
- **Purpose**: High-quality source files for re-processing if needed

### Archive Files
- **Location**: `/mnt/recordings/{match_id}/cam*_archive.mp4`
- **Size**: ~5.2 GB per match
- **Retention**: Kept locally until manually deleted
- **Upload**: Automatic to Nextcloud after encoding

### Disk Space Planning
Device has 256 GB storage:
- 10 matches × 18 GB (originals) = 180 GB
- 10 matches × 5.2 GB (archives) = 52 GB
- **Total**: 232 GB (leaves 24 GB free)

**Recommendation**: Delete original segments after successful upload, keep only archives locally for quick access.

## Monitoring & Logs

### Check Upload Status

View API logs:
```bash
sudo journalctl -u footballvision-api-enhanced -f
```

Look for:
```
Nextcloud upload service initialized: https://drive.genai.hr/FootballVision
Starting Nextcloud upload for match_20251104_001
Uploading cam0_archive.mp4 (2621.3 MB) to FootballVision/2025-11/match_20251104_001/cam0_archive.mp4
Upload complete: cam0_archive.mp4 → FootballVision/2025-11/match_20251104_001/cam0_archive.mp4
Nextcloud upload complete: Uploaded 2/2 files
```

### Check Processing Status (via API)

```bash
curl http://localhost:8000/api/v1/recordings/match_20251104_001/processing-status | jq
```

Response:
```json
{
  "processing": false,
  "completed": true,
  "status": "done"
}
```

## Security Considerations

1. **Credentials Storage**: Use environment variables, never commit passwords to git
2. **HTTPS**: Always use HTTPS for Nextcloud (encrypted transfer)
3. **App Passwords**: Consider using Nextcloud app passwords instead of main password
4. **File Permissions**: Ensure `.nextcloud_config` is mode 600 (read/write owner only)
5. **Network**: Consider VPN if device is on public network

## Support & Maintenance

### Code Locations
- **Upload Service**: `/home/mislav/footballvision-pro/src/video-pipeline/nextcloud_upload_service.py`
- **Post-Processing**: `/home/mislav/footballvision-pro/src/video-pipeline/post_processing_service.py`
- **API Service**: `/home/mislav/footballvision-pro/src/platform/simple_api_v3.py`

### Key Configuration Points
1. Nextcloud URL: `nextcloud_upload_service.py` line 25
2. Base folder: `nextcloud_upload_service.py` line 28 (default: "FootballVision")
3. Upload timeout: `nextcloud_upload_service.py` line 84
4. Encoding settings: `post_processing_service.py` line 56-62

## Quick Start Checklist

- [ ] Nextcloud account created: `footballvision-uploader`
- [ ] Strong password generated
- [ ] Credentials added to service environment variables
- [ ] Service restarted: `sudo systemctl restart footballvision-api-enhanced`
- [ ] Configuration verified: Upload service shows `enabled: True`
- [ ] Test upload successful
- [ ] Network access confirmed (443 to drive.genai.hr)
- [ ] Base folder appears in Nextcloud: `FootballVision/`
- [ ] End-to-end test: Record → Process → Upload → Verify in Nextcloud

## Contact & Questions

For technical issues with the FootballVision system:
- Device owner: Mislav
- System location: `/home/mislav/footballvision-pro/`

For Nextcloud-specific issues:
- Nextcloud admin: (your contact info)
- Instance: https://drive.genai.hr

---

**Document Version**: 1.0
**Last Updated**: 2025-11-04
**System Version**: FootballVision Pro v3 (Enhanced API)

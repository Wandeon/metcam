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

**Parameters:**
- `match_id` (string, required): Unique identifier for the match
- `force` (boolean, optional): Force start even if recording is active (default: false)
- `process_after_recording` (boolean, optional): Automatically merge segments and re-encode to archive quality when recording stops (default: false)

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

**Note:** If `process_after_recording` was enabled when starting the recording, post-processing will automatically begin in the background after stopping.

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
      "camera_0": {
        "active": false,
        "state": "stopped",
        "uptime": 0.0,
        "hls_url": "/hls/cam0.m3u8"
      },
      "camera_1": {
        "active": false,
        "state": "stopped",
        "uptime": 0.0,
        "hls_url": "/hls/cam1.m3u8"
      }
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

**Parameters:**
- `camera_id` (integer, optional): Start preview for specific camera (0 or 1), or null for all cameras

**Response:**
```json
{
  "success": true,
  "message": "Preview started for all cameras"
}
```

#### Stop Preview
```http
DELETE /api/v1/preview
```

**Response:**
```json
{
  "success": true,
  "message": "Preview stopped"
}
```

### Health & Monitoring

#### System Health
```http
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-04T19:00:00Z",
  "version": "3.0.0",
  "cameras": {
    "camera_0": {"available": true, "sensor": "IMX462"},
    "camera_1": {"available": true, "sensor": "IMX462"}
  },
  "services": {
    "recording": "ready",
    "preview": "ready",
    "post_processing": "ready"
  }
}
```

#### Prometheus Metrics
```http
GET /metrics
```

**Response:** Prometheus-formatted metrics for monitoring

**Metrics include:**
- `recording_active` - Whether recording is currently active
- `recording_duration_seconds` - Current recording duration
- `camera_status` - Status of each camera (0=inactive, 1=active)
- `api_requests_total` - Total API requests counter
- `api_request_duration_seconds` - Request duration histogram

### Recordings

#### List Recordings
```http
GET /api/v1/recordings
```

**Response:**
```json
{
  "recordings": [
    {
      "match_id": "match_20251104_001",
      "date": "2025-11-04",
      "cameras": [
        {
          "camera_id": 0,
          "segments": [
            {
              "filename": "cam0_1730741000.mp4",
              "size_mb": 2700,
              "duration_seconds": 600
            }
          ],
          "archive": {
            "filename": "cam0_archive.mp4",
            "size_mb": 2600,
            "available": true
          }
        }
      ],
      "total_size_mb": 18000,
      "processing_status": "complete"
    }
  ]
}
```

#### Get Processing Status
```http
GET /api/v1/recordings/{match_id}/processing-status
```

**Response:**
```json
{
  "processing": false,
  "completed": true,
  "status": "done",
  "start_time": "2025-11-04T15:30:00Z",
  "end_time": "2025-11-04T19:15:00Z",
  "duration_seconds": 13500
}
```

**Status values:**
- `processing` - Currently encoding
- `done` - Processing complete
- `null` - Never processed

#### Download Recording
```http
GET /api/v1/recordings/{match_id}/files/{filename}
```

**Parameters:**
- `match_id` (string): Match identifier
- `filename` (string): File to download (e.g., `cam0_archive.mp4` or `cam0_1730741000.mp4`)

**Response:** Binary file download with appropriate headers

**Example:**
```bash
curl -O http://localhost:8000/api/v1/recordings/match_20251104_001/files/cam0_archive.mp4
```

#### Delete Recording
```http
DELETE /api/v1/recordings/{match_id}
```

**Response:**
```json
{
  "success": true,
  "message": "Recording deleted: match_20251104_001"
}
```

**Warning:** This deletes all files (segments and archives) for the match. Operation is irreversible.

## Post-Processing

### Overview

Post-processing automatically merges 10-minute recording segments and re-encodes them to archive quality:

- **Input:** Raw camera segments (~2.7 GB per 10 minutes @ 12 Mbps)
- **Output:** Single archive file per camera (~2.6 GB per camera for 100-minute match)
- **Compression:** ~80% smaller than original segments
- **Quality:** 1920x1080, H.264 CRF 28, preset slower, tune film
- **Duration:** ~3-4 hours for 100-minute match

### Workflow

1. User starts recording with `process_after_recording: true`
2. Dual cameras record segments to `/mnt/recordings/{match_id}/segments/`
3. User stops recording
4. Post-processing automatically starts in background:
   - Merges all segments per camera using ffmpeg concat demuxer
   - Re-encodes to 1920x1080 with CRF 28 (aggressive compression)
   - Outputs to `/mnt/recordings/{match_id}/cam*_archive.mp4`
5. If Nextcloud credentials configured, uploads archives to cloud storage
6. Original segments remain on device for re-processing if needed

### Upload to Nextcloud (Optional)

After successful encoding, archives can be automatically uploaded to Nextcloud:

- **Destination:** `https://drive.genai.hr/FootballVision/YYYY-MM/{match_id}/`
- **Method:** WebDAV (Nextcloud standard)
- **Configuration:** Set `NEXTCLOUD_USERNAME` and `NEXTCLOUD_PASSWORD` environment variables
- **Documentation:** See [NEXTCLOUD_INTEGRATION_GUIDE.md](NEXTCLOUD_INTEGRATION_GUIDE.md)

## Error Handling

All endpoints return errors in consistent format:

```json
{
  "success": false,
  "error": "Error message describing the issue"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `400` - Bad request (invalid parameters)
- `404` - Resource not found
- `409` - Conflict (e.g., recording already active)
- `500` - Internal server error

## Rate Limiting

No rate limiting currently implemented (internal network only).

## WebSocket Support

Currently not implemented. Status updates require polling the `/api/v1/status` endpoint.

## Camera Configuration

Camera settings are managed via `/home/mislav/footballvision-pro/config/camera_config.json`:

```json
{
  "cameras": [
    {
      "id": 0,
      "sensor_id": 0,
      "sensor": "IMX462",
      "width": 2880,
      "height": 1752,
      "fps": 30,
      "bitrate_kbps": 12000
    }
  ]
}
```

**Note:** Camera configuration changes require API service restart.

## Implementation Details

For complete endpoint implementation, see:
- API Server: [simple_api_v3.py](../src/platform/simple_api_v3.py)
- Recording Service: [recording_service.py](../src/video-pipeline/recording_service.py)
- Post-Processing: [post_processing_service.py](../src/video-pipeline/post_processing_service.py)
- Nextcloud Upload: [nextcloud_upload_service.py](../src/video-pipeline/nextcloud_upload_service.py)

---

**Document Version:** 1.0
**Last Updated:** 2025-11-04
**System Version:** FootballVision Pro v3 (Enhanced API)

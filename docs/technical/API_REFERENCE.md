# FootballVision Pro – API Reference (v3)

The FootballVision Pro API v3 exposes an in-process control surface for recording, preview, and recordings management on Jetson Orin Nano devices. All endpoints return JSON and require the `Content-Type: application/json` header for POST requests.

## Base URL

- Default: `http://<device-ip>:8000`
- Local development: `http://localhost:8000`

No authentication is enforced in the default deployment. Protect the service with network controls if exposed outside the local network.

---

## Status & Health

### GET `/`

Returns service metadata.

```json
{
  "service": "FootballVision Pro API v3",
  "version": "3.0.0",
  "status": "running",
  "features": [
    "in_process_gstreamer",
    "instant_operations",
    "recording_protection",
    "state_persistence",
    "survives_page_refresh"
  ]
}
```

### GET `/api/v1/health`

Summarises CPU, memory, and storage usage.

```json
{
  "status": "healthy",
  "system": {
    "cpu_percent": 18.2,
    "memory_percent": 42.5,
    "memory_available_gb": 3.12,
    "disk_free_gb": 215.77,
    "disk_percent": 28.4
  }
}
```

### GET `/api/v1/status`

Aggregates recording and preview state.

```json
{
  "recording": {
    "recording": true,
    "match_id": "match_20250115_123456",
    "duration": 37.4,
    "cameras": {
      "camera_0": {
        "state": "running",
        "uptime": 37.2
      },
      "camera_1": {
        "state": "running",
        "uptime": 37.2
      }
    },
    "protected": false
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

---

## Recording

### GET `/api/v1/recording`

Returns the same payload as the `recording` section of `/api/v1/status`.

### POST `/api/v1/recording`

Start dual-camera recording. Preview is automatically stopped beforehand.

**Request Body**

| Field     | Type    | Default | Description                                  |
|-----------|---------|---------|----------------------------------------------|
| match_id  | string  | auto    | Optional explicit match identifier           |
| force     | boolean | `false` | Force restart if a recording is already live |

**Example**

```bash
curl -X POST http://localhost:8000/api/v1/recording \
  -H 'Content-Type: application/json' \
  -d '{"match_id":"match_20250115_123456"}'
```

**Success Response**

```json
{
  "success": true,
  "message": "Recording started for match: match_20250115_123456",
  "match_id": "match_20250115_123456",
  "cameras_started": [0, 1],
  "cameras_failed": []
}
```

### DELETE `/api/v1/recording`

Stops recording. Use the `force` query parameter to override the 10‑second protection window.

```bash
curl -X DELETE 'http://localhost:8000/api/v1/recording?force=false'
```

**Protected Response Example**

```json
{
  "success": false,
  "message": "Recording protected for 10.0s. Current duration: 5.2s. Use force=True to override.",
  "protected": true
}
```

**Success Response**

```json
{
  "success": true,
  "message": "Recording stopped successfully"
}
```

---

## Preview

### GET `/api/v1/preview`

Returns the same payload as the `preview` section of `/api/v1/status`.

### POST `/api/v1/preview`

Starts the HLS preview pipelines. Preview is blocked while recording is active.

**Request Body**

| Field     | Type | Default | Description                              |
|-----------|------|---------|------------------------------------------|
| camera_id | int  | `null`  | Start a specific camera (0 or 1); omit to start both |

```bash
curl -X POST http://localhost:8000/api/v1/preview \
  -H 'Content-Type: application/json' \
  -d '{}'
```

**Response**

```json
{
  "success": true,
  "message": "Preview started for cameras: [0, 1]",
  "cameras_started": [0, 1],
  "cameras_failed": []
}
```

### DELETE `/api/v1/preview`

Stops preview for one or both cameras.

```bash
curl -X DELETE 'http://localhost:8000/api/v1/preview?camera_id=0'
```

```json
{
  "success": true,
  "message": "Preview stopped for cameras: [0]",
  "cameras_stopped": [0],
  "cameras_failed": []
}
```

### POST `/api/v1/preview/restart`

Stops and restarts preview in a single call.

```bash
curl -X POST http://localhost:8000/api/v1/preview/restart \
  -H 'Content-Type: application/json' \
  -d '{"camera_id": null}'
```

---

## Recordings Management

### GET `/api/v1/recordings`

Lists available recordings under `/mnt/recordings`.

```json
{
  "recordings": {
    "match_20250115_123456": [
      {
        "file": "cam0_20250115_123456_00.mp4",
        "size_mb": 1126.42,
        "path": "/mnt/recordings/match_20250115_123456/segments/cam0_20250115_123456_00.mp4"
      },
      {
        "file": "cam1_20250115_123456_00.mp4",
        "size_mb": 1119.87,
        "path": "/mnt/recordings/match_20250115_123456/segments/cam1_20250115_123456_00.mp4"
      }
    ]
  }
}
```

### GET `/api/v1/recordings/{match_id}/segments`

Returns segment metadata for a specific match (files are sorted in order).

### DELETE `/api/v1/recordings/{match_id}`

Removes the entire recording directory and reports reclaimed space.

```json
{
  "status": "deleted",
  "match_id": "match_20250115_123456",
  "files_deleted": 6,
  "size_mb_freed": 6758.21
}
```

### GET `/api/v1/recordings/{match_id}/download`

Streams a ZIP archive containing all files for the match.

---

## Error Format

All errors use the standard FastAPI schema:

```json
{
  "detail": "Human-readable error message"
}
```

Common situations:

| Message                                              | Cause                                             |
|------------------------------------------------------|---------------------------------------------------|
| `Recording protected for 10.0s...`                   | Stop requested during protection window           |
| `Already recording match: <id>`                      | Second start attempted without `force=true`       |
| `Recording is active. Stop recording before starting preview.` | Preview requested while recording is running |
| `Preview start rejected: recording is active`        | Same as above                                     |
| `Recording <id> not found`                           | Requested match directory does not exist          |

---

## Notes

- Recording and preview pipelines share the same crop and color pipeline; preview streams are available at `/hls/cam0.m3u8` and `/hls/cam1.m3u8`.
- API v3 removed mode-switching endpoints (`/modes`, `mode` request fields). Field-of-view adjustments are now handled exclusively through the camera configuration endpoints/UI.
- All recording segments are MP4 files produced every 10 minutes with timestamped filenames.

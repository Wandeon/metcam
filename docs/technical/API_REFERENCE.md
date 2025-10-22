# FootballVision Pro - API Reference

**API Version**: 2.0 (Enhanced)
**Base URL**: `http://<device-ip>/api/v1`
**Last Updated**: October 17, 2025

---

## Table of Contents
1. [Authentication](#authentication)
2. [System Endpoints](#system-endpoints)
3. [Recording Endpoints](#recording-endpoints)
4. [Preview Endpoints](#preview-endpoints)
5. [Mode Management](#mode-management)
6. [Matches and Downloads](#matches-and-downloads)
7. [Response Formats](#response-formats)
8. [Error Codes](#error-codes)

---

## Authentication

Current implementation does not require authentication for local access. For production deployments with remote access, JWT authentication can be enabled via environment variables.

**Future Authentication**:
```http
Authorization: Bearer <jwt-token>
```

---

## System Endpoints

### GET /status

Get overall system status including recording, preview, and mode information.

**Request**:
```http
GET /api/v1/status
```

**Response** (200 OK):
```json
{
  "status": "idle",
  "recording": false,
  "mode": "normal",
  "mode_description": "Native 4K recording - 2880×1620 @ 25fps, 56% FOV, no downscaling",
  "recording_details": {
    "status": "idle",
    "recording": false,
    "mode": "normal",
    "mode_description": "Native 4K recording - 2880×1620 @ 25fps, 56% FOV, no downscaling"
  },
  "preview": {
    "status": "idle",
    "streaming": false,
    "mode": "normal",
    "mode_description": "Standard preview with cropping (720p @ 15fps)"
  },
  "modes": {
    "recording": {
      "mode": "normal",
      "description": "Native 4K recording - 2880×1620 @ 25fps, 56% FOV, no downscaling",
      "available_modes": [
        {
          "mode": "normal",
          "description": "Native 4K recording - 2880×1620 @ 25fps, 56% FOV, no downscaling"
        },
        {
          "mode": "no_crop",
          "description": "Raw sensor output without transformations (for setup)"
        },
        {
          "mode": "optimized",
          "description": "Native 4K recording - 2880×1620 @ 25fps, 56% FOV, no downscaling"
        }
      ]
    },
    "preview": {
      "mode": "normal",
      "description": "Standard preview with cropping (720p @ 15fps)",
      "available_modes": [
        {
          "mode": "normal",
          "description": "Standard preview with cropping (720p @ 15fps)"
        },
        {
          "mode": "no_crop",
          "description": "Raw sensor output without transformations (for setup)"
        },
        {
          "mode": "calibration",
          "description": "Center 50% crop (25% FOV) at 30fps - native 4K sharpness"
        }
      ]
    }
  }
}
```

**Response During Recording** (200 OK):
```json
{
  "status": "recording",
  "recording": true,
  "match_id": "match_20251017_001",
  "started_at": "2025-10-17T14:30:00.123Z",
  "duration_seconds": 125.45,
  "cam0_running": true,
  "cam1_running": true,
  "mode": "normal",
  "mode_description": "Native 4K recording - 2880×1620 @ 25fps, 56% FOV, no downscaling",
  "recording_details": { ... },
  "preview": { ... },
  "modes": { ... }
}
```

**Notes**:
- Top-level fields provide backward compatibility with UI
- Nested `recording_details` provides full recording status
- Use `status === 'recording'` or `recording === true` to detect active recording
- Poll this endpoint every 1-2 seconds for real-time status updates

### GET /health

Basic health check endpoint for monitoring.

**Request**:
```http
GET /api/v1/health
```

**Response** (200 OK):
```json
{
  "status": "ok"
}
```

---

## Recording Endpoints

### POST /recording

Start a new recording session.

**Request**:
```http
POST /api/v1/recording
Content-Type: application/json

{
  "match_id": "match_20251017_001",
  "mode": "normal"
}
```

**Request Body Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `match_id` | string | Yes | Unique identifier for the recording |
| `mode` | string | No | Recording mode: "normal", "no_crop", or "optimized" (default: "normal") |

**Response** (200 OK):
```json
{
  "status": "recording",
  "recording": true,
  "match_id": "match_20251017_001",
  "started_at": "2025-10-17T14:30:00.123456Z",
  "cam0_pid": 12345,
  "cam1_pid": 12346,
  "cam0_running": true,
  "cam1_running": true,
  "mode": "normal",
  "mode_description": "Native 4K recording - 2880×1620 @ 25fps, 56% FOV, no downscaling"
}
```

**Error Responses**:

- **400 Bad Request**: Invalid parameters or recording already active
  ```json
  {
    "detail": "Recording already active"
  }
  ```

- **400 Bad Request**: Preview streaming must be stopped first
  ```json
  {
    "detail": "Preview is active, stop preview before recording"
  }
  ```

**Recording Modes**:

| Mode | Resolution | FPS | FOV | Bitrate | Use Case |
|------|------------|-----|-----|---------|----------|
| `normal` | 2880×1620 | 25 | 56% | 18 Mbps | Default match recording |
| `no_crop` | 1920×1080 | 30 | 100% | 15 Mbps | Camera setup/alignment |
| `optimized` | 2880×1620 | 25 | 56% | 18 Mbps | Alias for normal |

**Example Usage**:

```bash
# Start recording in normal mode (default)
curl -X POST http://localhost/api/v1/recording \
  -H 'Content-Type: application/json' \
  -d '{"match_id":"match_001"}'

# Start recording in no-crop mode for camera setup
curl -X POST http://localhost/api/v1/recording \
  -H 'Content-Type: application/json' \
  -d '{"match_id":"setup_test", "mode":"no_crop"}'
```

### DELETE /recording

Stop the active recording session.

**Request**:
```http
DELETE /api/v1/recording
```

**Response** (200 OK):
```json
{
  "status": "idle",
  "recording": false,
  "match_id": "match_20251017_001",
  "duration_seconds": 5425.67,
  "stopped_at": "2025-10-17T16:00:25.789Z"
}
```

**Error Responses**:

- **400 Bad Request**: No active recording
  ```json
  {
    "detail": "No recording active"
  }
  ```

### GET /recording

Get current recording status (alias for /status with recording details).

**Request**:
```http
GET /api/v1/recording
```

**Response**: Same as `GET /status` but focused on recording details.

---

## Preview Endpoints

### POST /preview/start

Start the preview stream (HLS output for web viewing).

**Request**:
```http
POST /api/v1/preview/start
Content-Type: application/json

{
  "mode": "normal"
}
```

**Request Body Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `mode` | string | No | Preview mode: "normal", "no_crop", or "calibration" (default: "normal") |

**Response** (200 OK):
```json
{
  "status": "streaming",
  "streaming": true,
  "mode": "normal",
  "mode_description": "Standard preview with cropping (720p @ 15fps)",
  "cam0_running": true,
  "cam1_running": true,
  "hls_urls": {
    "cam0": "http://<device-ip>/hls/cam0/stream.m3u8",
    "cam1": "http://<device-ip>/hls/cam1/stream.m3u8"
  }
}
```

**Preview Modes**:

| Mode | Resolution | FPS | FOV | Bitrate | Use Case |
|------|------------|-----|-----|---------|----------|
| `normal` | 1280×720 | 15 | 50% | 2 Mbps | Standard web preview |
| `no_crop` | 1920×1080 | 15 | 100% | 3 Mbps | Full FOV preview |
| `calibration` | 1920×1080 | 30 | 25% | 8 Mbps | High-quality center crop for focus calibration |

**Error Responses**:

- **400 Bad Request**: Recording is active
  ```json
  {
    "detail": "Cannot start preview while recording is active"
  }
  ```

### POST /preview/stop

Stop the preview stream.

**Request**:
```http
POST /api/v1/preview/stop
```

**Response** (200 OK):
```json
{
  "status": "idle",
  "streaming": false
}
```

### GET /preview/status

Get current preview status.

**Request**:
```http
GET /api/v1/preview/status
```

**Response** (200 OK):
```json
{
  "status": "streaming",
  "streaming": true,
  "mode": "normal",
  "mode_description": "Standard preview with cropping (720p @ 15fps)"
}
```

---

## Mode Management

### GET /modes

Get available modes for recording and preview.

**Request**:
```http
GET /api/v1/modes
```

**Response** (200 OK):
```json
{
  "recording": {
    "mode": "normal",
    "description": "Native 4K recording - 2880×1620 @ 25fps, 56% FOV, no downscaling",
    "available_modes": [
      {
        "mode": "normal",
        "description": "Native 4K recording - 2880×1620 @ 25fps, 56% FOV, no downscaling"
      },
      {
        "mode": "no_crop",
        "description": "Raw sensor output without transformations (for setup)"
      },
      {
        "mode": "optimized",
        "description": "Native 4K recording - 2880×1620 @ 25fps, 56% FOV, no downscaling"
      }
    ]
  },
  "preview": {
    "mode": "normal",
    "description": "Standard preview with cropping (720p @ 15fps)",
    "available_modes": [
      {
        "mode": "normal",
        "description": "Standard preview with cropping (720p @ 15fps)"
      },
      {
        "mode": "no_crop",
        "description": "Raw sensor output without transformations (for setup)"
      },
      {
        "mode": "calibration",
        "description": "Center 50% crop (25% FOV) at 30fps - native 4K sharpness"
      }
    ]
  }
}
```

### POST /modes/recording

Set the default recording mode (persists for future recordings).

**Request**:
```http
POST /api/v1/modes/recording
Content-Type: application/json

{
  "mode": "normal"
}
```

**Response** (200 OK):
```json
{
  "mode": "normal",
  "description": "Native 4K recording - 2880×1620 @ 25fps, 56% FOV, no downscaling"
}
```

### POST /modes/preview

Set the default preview mode (persists for future preview sessions).

**Request**:
```http
POST /api/v1/modes/preview
Content-Type: application/json

{
  "mode": "calibration"
}
```

**Response** (200 OK):
```json
{
  "mode": "calibration",
  "description": "Center 50% crop (25% FOV) at 30fps - native 4K sharpness"
}
```

---

## Matches and Downloads

### GET /recordings

List all available recordings with segment information.

**Request**:
```http
GET /api/v1/recordings
```

**Response** (200 OK):
```json
{
  "recordings": {
    "match_20251017_001": [
      {
        "file": "match_20251017_001/segments/cam0_00000.mkv",
        "filename": "match_20251017_001_cam0",
        "size_mb": 645.2,
        "created_at": 1697552000.123,
        "segment_count": 18,
        "type": "segmented"
      },
      {
        "file": "match_20251017_001/segments/cam1_00000.mkv",
        "filename": "match_20251017_001_cam1",
        "size_mb": 640.8,
        "created_at": 1697552000.456,
        "segment_count": 18,
        "type": "segmented"
      }
    ],
    "match_20251016_003": [
      {
        "file": "match_20251016_003_cam0.mp4",
        "size_mb": 12150.5,
        "created_at": 1697465600.789
      },
      {
        "file": "match_20251016_003_cam1.mp4",
        "size_mb": 12080.3,
        "created_at": 1697465601.012
      }
    ]
  }
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `recordings` | object | Map of match_id to array of recording files |
| `file` | string | Relative path to recording file |
| `filename` | string | Display name for the recording |
| `size_mb` | number | Total file size in megabytes |
| `created_at` | number | Unix timestamp of creation |
| `segment_count` | number | Number of segments (for segmented recordings) |
| `type` | string | "segmented" or omitted for merged files |

---

## Response Formats

### Recording Status Object

```typescript
interface RecordingStatus {
  status: 'idle' | 'recording';
  recording: boolean;
  match_id?: string;
  started_at?: string;  // ISO 8601 timestamp
  duration_seconds?: number;
  cam0_running?: boolean;
  cam1_running?: boolean;
  cam0_pid?: number;
  cam1_pid?: number;
  mode?: string;
  mode_description?: string;
}
```

### Preview Status Object

```typescript
interface PreviewStatus {
  status: 'idle' | 'streaming';
  streaming: boolean;
  mode?: string;
  mode_description?: string;
  cam0_running?: boolean;
  cam1_running?: boolean;
  hls_urls?: {
    cam0: string;
    cam1: string;
  };
}
```

### Mode Object

```typescript
interface Mode {
  mode: string;
  description: string;
  available_modes: Array<{
    mode: string;
    description: string;
  }>;
}
```

---

## Error Codes

All errors follow FastAPI standard error format:

```json
{
  "detail": "Error message describing the issue"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | OK | Request successful |
| 400 | Bad Request | Invalid parameters, conflicting state (e.g., recording already active) |
| 404 | Not Found | Endpoint or resource not found |
| 500 | Internal Server Error | Server-side error (check logs) |

### Common Error Messages

| Message | Cause | Solution |
|---------|-------|----------|
| "Recording already active" | Attempted to start recording while one is running | Stop current recording first |
| "No recording active" | Attempted to stop recording when none is running | Check status before stopping |
| "Cannot start preview while recording is active" | Attempted preview during recording | Stop recording first |
| "Preview is active, stop preview before recording" | Attempted recording during preview | Stop preview first |
| "Invalid mode: xyz" | Specified mode doesn't exist | Use /modes to check available modes |

---

## Usage Examples

### Complete Recording Workflow

```bash
# 1. Check system status
curl http://localhost/api/v1/status | python3 -m json.tool

# 2. Ensure 25W power mode
sudo nvpmodel -m 1

# 3. Start recording
curl -X POST http://localhost/api/v1/recording \
  -H 'Content-Type: application/json' \
  -d '{"match_id":"match_20251017_001"}'

# 4. Monitor status (poll during recording)
watch -n 2 'curl -s http://localhost/api/v1/status | python3 -m json.tool'

# 5. Stop recording after match
curl -X DELETE http://localhost/api/v1/recording

# 6. List recordings
curl http://localhost/api/v1/recordings | python3 -m json.tool
```

### Preview Stream Workflow

```bash
# 1. Start preview in calibration mode
curl -X POST http://localhost/api/v1/preview/start \
  -H 'Content-Type: application/json' \
  -d '{"mode":"calibration"}'

# 2. Access streams in browser
# Camera 0: http://<device-ip>/hls/cam0/stream.m3u8
# Camera 1: http://<device-ip>/hls/cam1/stream.m3u8

# 3. Stop preview when done
curl -X POST http://localhost/api/v1/preview/stop
```

---

## Prometheus Metrics

The API exposes Prometheus metrics at `/metrics`:

```http
GET /metrics
```

**Available Metrics**:
- `api_requests_total{endpoint, method}` - Total API requests counter
- `recording_active` - Gauge: 1 if recording, 0 if idle
- `preview_active` - Gauge: 1 if streaming, 0 if idle

---

## Related Documentation

- **[Recording Pipeline Technical Reference](./RECORDING_PIPELINE.md)** - Complete pipeline details
- **[Deployment Guide](../DEPLOYMENT_GUIDE.md)** - Installation and setup
- **[Troubleshooting Guide](../user/TROUBLESHOOTING.md)** - Common issues

---

**Document Version**: 2.0
**Last Updated**: October 17, 2025
**Compatible with**: FootballVision Pro Enhanced API (simple_api_enhanced.py)

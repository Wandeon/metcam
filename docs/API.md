# FootballVision Pro API Reference

## Base URLs
- Production: `http://localhost:8000/api/v1`
- Development: `http://localhost:8001/api/v1`

## Authentication
- No API authentication is implemented at this time.
- Intended for trusted/internal network usage.

## REST Endpoints

### Health and State

#### `GET /api/v1/health`
Returns basic host health.

Example response:
```json
{
  "status": "healthy",
  "system": {
    "cpu_percent": 7.6,
    "memory_percent": 38.5,
    "memory_available_gb": 4.58,
    "disk_free_gb": 135.61,
    "disk_percent": 38.8
  }
}
```

#### `GET /api/v1/status`
Returns top-level preview + recording state.

Example response:
```json
{
  "recording": {
    "recording": false,
    "match_id": null,
    "duration": 0.0,
    "cameras": {},
    "degraded": false,
    "degraded_cameras": {},
    "camera_recovery": {},
    "overload_guard": {
      "active": false,
      "unhealthy_streak": 0,
      "cpu_percent": null,
      "reasons": []
    }
  },
  "preview": {
    "preview_active": false,
    "transport_mode": "dual",
    "webrtc_supported": true,
    "ice_servers": [{"urls": ["stun://stun.l.google.com:19302"]}],
    "cameras": {
      "camera_0": {
        "active": false,
        "state": "stopped",
        "uptime": 0.0,
        "hls_url": "/hls/cam0.m3u8",
        "transport": "hls",
        "stream_kind": "main_cam0"
      },
      "camera_1": {
        "active": false,
        "state": "stopped",
        "uptime": 0.0,
        "hls_url": "/hls/cam1.m3u8",
        "transport": "hls",
        "stream_kind": "main_cam1"
      }
    }
  }
}
```

#### `GET /api/v1/pipeline-state`
Returns mutex state used to enforce preview/recording exclusivity.

Example response:
```json
{
  "mode": "idle",
  "holder": null,
  "lock_time": null,
  "can_preview": true,
  "can_record": true
}
```

### Recording

#### `GET /api/v1/recording`
Returns active recording state.

#### `POST /api/v1/recording`
Starts recording.

Request body:
```json
{
  "match_id": "match_20260211_001",
  "force": false,
  "process_after_recording": false
}
```

Notes:
- `match_id` is optional. If omitted, server generates one.
- `force=true` can replace an existing recording.
- Current config supports strict dual-camera startup (`recording_require_all_cameras`).

Example success response:
```json
{
  "success": true,
  "message": "Recording started for match: match_20260211_001",
  "match_id": "match_20260211_001",
  "cameras_started": [0, 1],
  "cameras_failed": [],
  "require_all_cameras": true
}
```

#### `DELETE /api/v1/recording?force=false`
Stops recording.

Notes:
- Protected-stop window is enforced by service (`protection_seconds`, currently 10s).
- If within protection window, call with `force=true`.
- `success=true` means all camera outputs finalized cleanly.
- `transport_success=true` means stop commands reached/closed pipelines, even if finalization was incomplete.
- `integrity` includes post-stop segment probe outcomes per camera.
- Integrity probing uses ffprobe metadata checks (constant-time vs segment length). Probe timeout is controlled by `recording_integrity_probe_timeout_seconds`.
- If finalization succeeds but integrity fails, response returns `success=false` with
  message `Recording pipelines stopped but integrity checks failed`.

Example success response:
```json
{
  "success": true,
  "message": "Recording stopped successfully",
  "transport_success": true,
  "graceful_stop": true,
  "camera_stop_results": {
    "camera_0": {
      "success": true,
      "eos_received": true,
      "finalized": true,
      "timed_out": false,
      "error": null,
      "segment_path": "/mnt/recordings/match_20260211_001/segments/cam0_20260211_220241_00.mp4",
      "integrity_checked": true,
      "integrity_ok": true,
      "integrity_error": null
    },
    "camera_1": {
      "success": true,
      "eos_received": true,
      "finalized": true,
      "timed_out": false,
      "error": null,
      "segment_path": "/mnt/recordings/match_20260211_001/segments/cam1_20260211_220241_00.mp4",
      "integrity_checked": true,
      "integrity_ok": true,
      "integrity_error": null
    }
  },
  "integrity": {
    "checked": true,
    "all_ok": true,
    "reason": null,
    "cameras": {
      "camera_0": {
        "segment_found": true,
        "segment_path": "/mnt/recordings/match_20260211_001/segments/cam0_20260211_220241_00.mp4",
        "integrity_checked": true,
        "integrity_ok": true,
        "integrity_error": null
      },
      "camera_1": {
        "segment_found": true,
        "segment_path": "/mnt/recordings/match_20260211_001/segments/cam1_20260211_220241_00.mp4",
        "integrity_checked": true,
        "integrity_ok": true,
        "integrity_error": null
      }
    }
  }
}
```

#### `GET /api/v1/recording-health`
Returns recording health diagnostics.

Example response:
```json
{
  "healthy": true,
  "message": "Recording healthy",
  "recovery_attempts": {
    "camera_0": 0,
    "camera_1": 0
  },
  "camera_diagnostics": {
    "camera_0": {
      "pipeline_present": true,
      "pipeline_state": "running",
      "latest_segment": "cam0_20260211_220241_00.mp4",
      "latest_segment_size": 4035962,
      "latest_segment_age_seconds": 1.8,
      "integrity_probe": {
        "checked": false,
        "ok": null,
        "error": null
      }
    }
  }
}
```

Notes:
- `camera_diagnostics` is always returned for active recordings.
- `integrity_probe.checked=true` appears only when a segment is large and stable enough to probe safely.
- If probing fails, health is reported as unhealthy with a `Segment probe failed (...)` issue.
- Runtime overload guard state is surfaced in `GET /api/v1/status` under `recording.overload_guard`.

### Preview

#### `GET /api/v1/preview`
Returns current preview state.

#### `POST /api/v1/preview`
Starts preview for one or both cameras.

Request body:
```json
{
  "camera_id": null,
  "transport": "webrtc"
}
```

- `camera_id=null` means both cameras.
- `camera_id=0` or `1` targets a single camera.
- `transport` optional: `hls` or `webrtc`.

#### `DELETE /api/v1/preview?camera_id=0`
Stops preview for one camera or all cameras.

#### `POST /api/v1/preview/restart`
Restarts preview pipeline(s) with the same `camera_id` shape as start.

### Recordings Inventory and File Access

#### `GET /api/v1/recordings`
Lists recordings with grouped segment metadata.

#### `GET /api/v1/recordings/{match_id}/segments`
Returns normalized segment lists by camera (`cam0`, `cam1`, `other`).

#### `DELETE /api/v1/recordings/{match_id}`
Deletes the recording directory.

#### `GET /api/v1/recordings/{match_id}/processing-status`
Returns post-processing status if enabled.

#### `GET /api/v1/recordings/{match_id}/download`
Downloads entire recording folder as zip.

#### `GET /api/v1/recordings/{match_id}/segments/{segment_name}`
Downloads a segment file.

#### `GET /api/v1/recordings/{match_id}/files/{file_name}`
Downloads a direct file from match directory.

### Diagnostics

#### `GET /api/v1/system-metrics`
Returns real-time system metrics used by dashboard and WS broadcasts.

#### `GET /api/v1/logs/{log_type}?lines=100`
Supported `log_type` values:
- `health`
- `alerts`
- `watchdog`

#### `GET /api/v1/diagnostics/recording-correlations`
Correlates recent `NvVIC` allocator/open errors with recording timeout and media-probe-failure signals.

Query params:
- `lookback_minutes` (default `60`, min `1`, max `1440`)
- `max_lines` (default `5000`, min `200`, max `50000`)
- `correlation_window_seconds` (default `180`, min `1`, max `3600`)

Response includes:
- `counts.nvvic_errors`
- `counts.recording_stop_timeouts`
- `counts.probe_failures`
- `counts.correlated_nvvic_events`
- recent event slices for each category and correlation entries

## WebSocket (`/ws`)

The WebSocket layer is implemented and used as the real-time status + command plane.

### Connection
- Endpoint: `ws://<host>/ws` (or `wss://` behind TLS reverse proxy)
- Protocol version: `v = 1`
- Maximum concurrent connections: `10`
- Default subscription on connect: `status`

Server sends on connect:
```json
{
  "v": 1,
  "type": "hello",
  "channels": ["status"]
}
```

### Client-to-Server Messages

#### Ping
```json
{"v": 1, "type": "ping"}
```

#### Subscribe
```json
{"v": 1, "type": "subscribe", "channels": ["status", "pipeline_state"]}
```

#### Unsubscribe
```json
{"v": 1, "type": "unsubscribe", "channels": ["pipeline_state"]}
```

#### Command
```json
{
  "v": 1,
  "type": "command",
  "id": "cmd-123",
  "action": "start_recording",
  "params": {
    "match_id": "match_20260211_001",
    "force": false,
    "process_after_recording": false
  }
}
```

### Server-to-Client Messages

#### Broadcast channel update
```json
{
  "v": 1,
  "type": "status",
  "ts": 1770837041.2668238,
  "data": {"recording": {}, "preview": {}}
}
```

#### Command ack (phase 1)
```json
{
  "v": 1,
  "type": "command_ack",
  "id": "cmd-123",
  "action": "start_recording"
}
```

#### Command result (phase 2)
```json
{
  "v": 1,
  "type": "command_result",
  "id": "cmd-123",
  "success": true,
  "data": {"success": true, "message": "..."}
}
```

#### Error
```json
{
  "v": 1,
  "type": "error",
  "code": "invalid_version",
  "message": "Expected v=1"
}
```

### Broadcast Channels and Intervals
- `status` (1.0s)
- `pipeline_state` (2.0s)
- `system_metrics` (3.0s)
- `panorama_status` (3.0s)

### Supported WS Command Actions
- `start_recording`
- `stop_recording`
- `start_preview`
- `stop_preview`
- `get_recordings`
- `get_logs`
- `get_panorama_processing`

### WebRTC Signaling Messages (over `/ws`)
Client -> Server:
- `webrtc_start` with `{stream_kind}`
- `webrtc_offer` with `{session_id, stream_kind, sdp}`
- `webrtc_ice_candidate` with `{session_id, stream_kind, candidate, sdpMLineIndex}`
- `webrtc_stop` with `{session_id, stream_kind}`

Server -> Client:
- `webrtc_session_ready`
- `webrtc_answer`
- `webrtc_ice_candidate`
- `webrtc_state`
- `webrtc_error`

### Command Idempotency
- Recent command IDs are deduplicated.
- Cache size: 200 command IDs.
- TTL: 60 seconds.
- Duplicate command ID returns cached `command_result` (or in-progress ack).

## Error Behavior

Two patterns are used:
1. FastAPI exceptions (`HTTPException`):
```json
{"detail": "..."}
```
2. Service-level operation results:
```json
{"success": false, "message": "..."}
```

## Related Files
- API server: `src/platform/simple_api_v3.py`
- WS manager: `src/platform/ws_manager.py`
- Recording service: `src/video-pipeline/recording_service.py`
- Preview service: `src/video-pipeline/preview_service.py`

---

Document version: 2.0  
Last updated: 2026-02-11  
System: FootballVision Pro v3

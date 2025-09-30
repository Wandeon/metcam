# Platform Integration Guide

This document describes how other teams integrate with the Platform layer.

## Overview

The Platform layer provides REST APIs, WebSocket events, and a web dashboard for controlling and monitoring the FootballVision Pro system.

## Integration Points

### 1. Video Pipeline Team Integration

The Platform layer needs to call Video Pipeline APIs for recording control.

#### Expected Video Pipeline APIs

```python
# Recording control
class VideoRecordingAPI:
    def start_recording(self, match_id: str, cameras: List[int]) -> str:
        """
        Start recording from specified cameras

        Args:
            match_id: Unique match identifier
            cameras: List of camera IDs (e.g., [0, 1])

        Returns:
            session_id: Recording session ID
        """
        pass

    def stop_recording(self, session_id: str) -> dict:
        """
        Stop active recording session

        Args:
            session_id: Recording session ID

        Returns:
            {
                'duration_seconds': int,
                'files': [
                    {'camera_id': 0, 'path': '/path/to/cam0.mp4', 'size_bytes': 123456},
                    {'camera_id': 1, 'path': '/path/to/cam1.mp4', 'size_bytes': 123456}
                ]
            }
        """
        pass

    def get_recording_status(self) -> dict:
        """
        Get current recording status

        Returns:
            {
                'is_recording': bool,
                'session_id': str | None,
                'cameras': [
                    {
                        'id': 0,
                        'status': 'recording',
                        'fps': 30.0,
                        'dropped_frames': 0,
                        'bitrate_mbps': 20.5
                    }
                ]
            }
        """
        pass

    def get_preview_url(self, camera_id: int) -> str:
        """Get MJPEG stream URL for camera preview"""
        return f"http://localhost:8000/stream/camera{camera_id}"
```

#### Integration Location

File: `src/platform/api-server/services/video_integration.py` (stub created)

Update with actual Video Pipeline API calls:

```python
from video_pipeline.api import VideoRecordingAPI  # Import from video team

video_api = VideoRecordingAPI()
```

### 2. Processing Team Integration

The Platform layer monitors processing progress and notifies users when complete.

#### Expected Processing APIs

```python
class ProcessingAPI:
    def start_stitching(self, match_id: str, cam0_path: str, cam1_path: str) -> str:
        """
        Start panoramic stitching

        Args:
            match_id: Match identifier
            cam0_path: Path to camera 0 video
            cam1_path: Path to camera 1 video

        Returns:
            job_id: Processing job identifier
        """
        pass

    def get_progress(self, job_id: str) -> dict:
        """
        Get processing progress

        Returns:
            {
                'status': 'processing' | 'completed' | 'failed',
                'progress_percent': 45.2,
                'current_step': 'feature_matching',
                'eta_seconds': 1800,
                'output_path': '/path/to/panorama.mp4' | None
            }
        """
        pass

    def cancel_processing(self, job_id: str) -> bool:
        """Cancel active processing job"""
        pass
```

#### Integration Location

File: `src/platform/api-server/services/processing_integration.py` (stub created)

### 3. Infrastructure Team Integration

The Platform layer reads system metrics from Infrastructure APIs.

#### Expected Infrastructure APIs

```python
class SystemMonitoringAPI:
    def get_temperature(self) -> float:
        """Get SoC temperature in Celsius"""
        pass

    def get_storage_info(self) -> dict:
        """
        Returns:
            {
                'total_gb': 256.0,
                'available_gb': 120.5,
                'used_percent': 52.9
            }
        """
        pass

    def get_network_status(self) -> dict:
        """
        Returns:
            {
                'type': 'ethernet' | 'wifi' | 'none',
                'speed_mbps': 100.0,
                'ssid': 'Network Name' | None,
                'signal_strength': -45 | None
            }
        """
        pass

    def get_camera_status(self) -> List[dict]:
        """
        Returns: [
            {
                'id': 0,
                'connected': True,
                'model': 'IMX477',
                'resolution': '4056x3040'
            }
        ]
        """
        pass
```

#### Integration Location

File: `src/platform/api-server/routers/system.py`

Replace mock implementations with actual API calls.

## WebSocket Event Broadcasting

Other teams can broadcast events to connected clients:

```python
from api_server.main import broadcast_event

# Recording started
await broadcast_event('recording.started', {
    'session_id': 'abc123',
    'match_id': 'match_001',
    'timestamp': time.time()
})

# Processing progress
await broadcast_event('processing.progress', {
    'match_id': 'match_001',
    'percent': 45.2,
    'eta': 1800
})

# Error occurred
await broadcast_event('system.error', {
    'component': 'camera',
    'error': 'Camera 1 disconnected',
    'severity': 'warning'
})
```

## Database Updates

Teams can update match status in the database:

```python
from database.db_manager import get_db_manager

db = get_db_manager()

# Update processing status
db.execute_update("""
    UPDATE matches
    SET processing_status = ?,
        file_path_panorama = ?,
        processing_completed_at = ?
    WHERE id = ?
""", ('completed', '/path/to/panorama.mp4', datetime.utcnow(), match_id))
```

## Notification Triggers

Platform automatically sends notifications for key events:

```python
from services.notifications import get_notification_service

notifier = get_notification_service()

# Notify when recording starts
notifier.notify_recording_started(match_id, home_team, away_team)

# Notify when processing completes
notifier.notify_processing_completed(match_id, panorama_path)

# Notify on errors
notifier.notify_error('camera_error', 'Camera 0 disconnected')
```

## Testing Integration

### Mock Video Pipeline for Testing

```python
# tests/test_integration.py
class MockVideoAPI:
    def start_recording(self, match_id, cameras):
        return f"session_{match_id}"

    def stop_recording(self, session_id):
        return {
            'duration_seconds': 5400,
            'files': [
                {'camera_id': 0, 'path': '/tmp/cam0.mp4', 'size_bytes': 10000000},
                {'camera_id': 1, 'path': '/tmp/cam1.mp4', 'size_bytes': 10000000}
            ]
        }

# Use in tests
video_api = MockVideoAPI()
```

## Configuration

Each team's endpoints should be configurable:

```bash
# .env
VIDEO_PIPELINE_URL=http://localhost:8000
PROCESSING_API_URL=http://localhost:8001
INFRASTRUCTURE_API_URL=http://localhost:8002
```

## API Versioning

All platform APIs use `/api/v1/` prefix. Future versions will use `/api/v2/`, etc.

## Error Handling

Platform expects consistent error responses:

```json
{
  "error": "recording_failed",
  "details": {
    "camera_id": 0,
    "reason": "device_not_found"
  },
  "recoverable": false
}
```

## Health Checks

Other services should implement health checks:

```python
GET /health
Response: {"status": "healthy", "checks": {"camera": true}}
```

Platform monitors these endpoints for system health dashboard.

## Complete Integration Example

```python
# Example: Recording workflow with all teams

# 1. Platform receives start recording request
POST /api/v1/recording
{
    "match_id": "match_001",
    "home_team": "Team A",
    "away_team": "Team B"
}

# 2. Platform calls Video Pipeline
video_session = video_api.start_recording("match_001", [0, 1])

# 3. Platform updates database
db.execute_update("""
    INSERT INTO recording_sessions (id, match_id, started_at)
    VALUES (?, ?, ?)
""", (video_session, "match_001", datetime.utcnow()))

# 4. Platform sends notification
notifier.notify_recording_started("match_001", "Team A", "Team B")

# 5. Platform broadcasts WebSocket event
await broadcast_event('recording.started', {
    'session_id': video_session,
    'match_id': 'match_001'
})

# ... recording happens ...

# 6. Platform receives stop request
DELETE /api/v1/recording

# 7. Platform calls Video Pipeline
result = video_api.stop_recording(video_session)

# 8. Platform updates database with file paths
db.execute_update("""
    UPDATE matches
    SET file_path_cam0 = ?, file_path_cam1 = ?,
        duration_seconds = ?, recording_status = 'stopped'
    WHERE id = ?
""", (result['files'][0]['path'], result['files'][1]['path'],
      result['duration_seconds'], 'match_001'))

# 9. Platform triggers Processing
processing_job = processing_api.start_stitching(
    "match_001",
    result['files'][0]['path'],
    result['files'][1]['path']
)

# 10. Platform polls processing progress
progress = processing_api.get_progress(processing_job)
await broadcast_event('processing.progress', progress)

# 11. When processing completes
if progress['status'] == 'completed':
    db.execute_update("""
        UPDATE matches
        SET file_path_panorama = ?, processing_status = 'completed'
        WHERE id = ?
    """, (progress['output_path'], 'match_001'))

    notifier.notify_processing_completed("match_001", progress['output_path'])
    await broadcast_event('processing.completed', {'match_id': 'match_001'})
```

## Contact

Platform Team Lead (W31): platform@footballvision.pro
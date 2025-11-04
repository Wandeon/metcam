# Panorama API Endpoints

## Overview

The panorama API provides endpoints for GPU-accelerated panorama stitching, including real-time preview, calibration, and post-processing of recordings.

**Base URL**: `http://localhost:8000/api/v1/panorama`

## Endpoints Summary

### Status & Configuration (4 endpoints)

1. **GET /api/v1/panorama/status** - Get panorama service status
2. **GET /api/v1/panorama/config** - Get current configuration
3. **PUT /api/v1/panorama/config** - Update configuration
4. **GET /api/v1/panorama/stats** - Get performance statistics

### Calibration (5 endpoints)

5. **GET /api/v1/panorama/calibration** - Get calibration status
6. **POST /api/v1/panorama/calibration/start** - Start calibration
7. **POST /api/v1/panorama/calibration/capture** - Capture calibration frame
8. **POST /api/v1/panorama/calibration/complete** - Complete calibration
9. **DELETE /api/v1/panorama/calibration** - Clear calibration data

### Preview (2 endpoints)

10. **POST /api/v1/panorama/preview/start** - Start panorama preview
11. **POST /api/v1/panorama/preview/stop** - Stop panorama preview

### Post-Processing (2 endpoints)

12. **POST /api/v1/panorama/process** - Process recording to panorama
13. **GET /api/v1/panorama/process/{match_id}/status** - Get processing status

## Implementation Status

**Current Status**: Stub Implementation (Phase 6)

- ✅ All 13 API endpoints created and registered
- ✅ Request/response models defined
- ✅ Error handling implemented
- ✅ Integrated with simple_api_v3.py
- ⏳ VPI stitching engine (stub - returns mock responses)
- ⏳ Calibration service (stub - not yet functional)
- ⏳ Real-time preview (stub - not yet functional)
- ⏳ Post-processing (stub - not yet functional)

## Usage Examples

### Get Status

```bash
curl http://localhost:8000/api/v1/panorama/status
```

Response:
```json
{
  "preview_active": false,
  "calibrated": false,
  "calibration_date": null,
  "quality_score": null,
  "performance": {
    "current_fps": 0.0,
    "avg_sync_drift_ms": 0.0,
    "dropped_frames": 0
  }
}
```

### Update Configuration

```bash
curl -X PUT http://localhost:8000/api/v1/panorama/config \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "preview_fps_target": 20}'
```

### Start Preview (requires calibration)

```bash
curl -X POST http://localhost:8000/api/v1/panorama/preview/start
```

Response (stub):
```json
{
  "success": true,
  "message": "Panorama preview started (stub implementation)",
  "hls_url": "/hls/panorama.m3u8",
  "resolution": "3840x1315",
  "fps_target": 15
}
```

### Process Recording

```bash
curl -X POST http://localhost:8000/api/v1/panorama/process \
  -H "Content-Type: application/json" \
  -d '{"match_id": "match_20251104_001"}'
```

## Error Responses

### Not Calibrated (503)

```json
{
  "detail": "Panorama not calibrated"
}
```

### Recording Active (409)

```json
{
  "detail": "Cannot start panorama: recording is active"
}
```

### Match Not Found (404)

```json
{
  "detail": "Match not found: match_20251104_001"
}
```

## Integration

The panorama router is integrated into `simple_api_v3.py`:

```python
# Import panorama router
from panorama_router import router as panorama_router

# Include panorama router
app.include_router(panorama_router)
```

## Next Steps

To make the endpoints functional:

1. Implement VPI stitching engine (vpi_stitcher.py)
2. Implement calibration service (calibration_service.py)
3. Complete panorama_service.py implementation
4. Add pipeline builders for preview and post-processing
5. Test all endpoints with real camera data

See PANORAMA_MASTER_GUIDE.md for complete implementation roadmap.

"""
FastAPI Router for Panorama Stitching Endpoints

Provides REST API for panorama preview, calibration, and post-processing.
Follows existing FootballVision API patterns from simple_api_v3.py.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
import logging
import sys
from pathlib import Path

# Add panorama module to path
sys.path.insert(0, str(Path(__file__).parent.parent / "panorama"))

# Import panorama service
from panorama_service import get_panorama_service

logger = logging.getLogger(__name__)

# Create router with prefix
router = APIRouter(prefix="/api/v1/panorama", tags=["panorama"])

# Get service instance
panorama_service = get_panorama_service()


# ============================================================================
# Pydantic Request/Response Models
# ============================================================================

class ConfigUpdateRequest(BaseModel):
    """Request model for configuration updates"""
    enabled: Optional[bool] = None
    output_width: Optional[int] = None
    output_height: Optional[int] = None
    preview_fps_target: Optional[int] = None
    use_vic_backend: Optional[bool] = None


class ProcessRecordingRequest(BaseModel):
    """Request model for processing a recording"""
    match_id: str


class CalibrationStartRequest(BaseModel):
    """Request model for starting calibration"""
    frame_count: Optional[int] = 15  # Target number of frame pairs


class PanoramaPreviewStartRequest(BaseModel):
    """Request model for panorama preview start."""
    transport: Optional[str] = None  # hls | webrtc (optional)


# ============================================================================
# Status & Configuration Endpoints
# ============================================================================

@router.get("/status")
async def get_status():
    """
    Get panorama service status

    Returns current state including preview status, calibration status,
    and performance metrics.
    """
    try:
        status = panorama_service.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting panorama status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_config():
    """
    Get current panorama configuration

    Returns the panorama_config.json contents including calibration data,
    output settings, and performance options.
    """
    try:
        # Get config from status (embedded in status response)
        status = panorama_service.get_status()
        config = status.get('config', {})
        return config if config else {'message': 'Configuration not available'}
    except Exception as e:
        logger.error(f"Error getting panorama config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(request: ConfigUpdateRequest):
    """
    Update panorama configuration

    Updates panorama_config.json with provided settings.
    Only updates fields that are provided in the request.

    Note: Configuration updates require direct file modification.
    This endpoint returns stub response.
    """
    try:
        # Convert request to dict, excluding None values
        config_updates = request.dict(exclude_none=True)

        if not config_updates:
            raise HTTPException(status_code=400, detail="No configuration updates provided")

        # TODO: Implement config update via config_manager
        logger.info(f"Config update requested: {config_updates}")

        return {
            'success': True,
            'message': 'Configuration update not yet implemented',
            'requested_updates': config_updates
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating panorama config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """
    Get performance statistics

    Returns real-time performance metrics including FPS, sync quality,
    and dropped frame counts.
    """
    try:
        # Get stats from status (embedded in performance section)
        status = panorama_service.get_status()
        performance = status.get('performance', {})

        # Add preview status
        stats = {
            'preview_active': status.get('preview_active', False),
            'uptime_seconds': status.get('uptime_seconds', 0.0),
            **performance
        }

        return stats
    except Exception as e:
        logger.error(f"Error getting panorama stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Calibration Endpoints
# ============================================================================

@router.get("/calibration")
async def get_calibration_status():
    """
    Get calibration status

    Returns whether the system is calibrated, when calibration was performed,
    and quality metrics.
    """
    try:
        # Get calibration info from status
        status = panorama_service.get_status()
        calibration_info = status.get('calibration_info', {})

        # Get calibration progress to include is_calibrating and frames_captured
        progress = panorama_service.get_calibration_progress()

        return {
            'calibrated': status.get('calibrated', False),
            'is_calibrating': progress.get('is_calibrating', False),
            'frames_captured': progress.get('frames_captured', 0),
            'quality_score': calibration_info.get('quality_score'),
            'calibration_date': calibration_info.get('calibration_date')
        }
    except Exception as e:
        logger.error(f"Error getting calibration status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calibration/start")
async def start_calibration(request: Optional[CalibrationStartRequest] = None):
    """
    Start camera calibration

    Begins calibration mode to capture frame pairs for homography calculation.
    User should capture 15-20 frame pairs of a scene with rich features.
    """
    try:
        result = panorama_service.start_calibration()

        if result.get('success'):
            return result
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get('message', 'Failed to start calibration')
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting calibration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calibration/capture")
async def capture_calibration_frame():
    """
    Capture a calibration frame pair

    Captures synchronized frames from both cameras for calibration.
    Repeat this 15-20 times to collect enough samples.
    """
    try:
        result = panorama_service.capture_calibration_frame()

        if result.get('success'):
            return result
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get('message', 'Failed to capture frame')
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error capturing calibration frame: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calibration/reset")
async def reset_calibration():
    """
    Reset/cancel calibration in progress

    Clears all captured calibration frames and exits calibration mode.
    Use this to start over if you captured bad frames or want to cancel.
    """
    try:
        result = panorama_service.reset_calibration()

        if result.get('success'):
            return result
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get('message', 'Failed to reset calibration')
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting calibration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calibration/complete")
async def complete_calibration():
    """
    Complete calibration and calculate homography

    Processes all captured frame pairs to calculate the homography matrix.
    Validates calibration quality and saves to panorama_config.json.
    """
    try:
        result = panorama_service.complete_calibration()

        if result.get('success'):
            return result
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get('message', 'Failed to complete calibration')
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing calibration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/calibration")
async def clear_calibration():
    """
    Clear calibration data

    Removes calibration data from configuration.
    Use this to recalibrate from scratch.
    """
    try:
        # TODO: Implement calibration clearing via config_manager
        logger.info("Calibration clear requested")

        return {
            'success': True,
            'message': 'Calibration clear not yet implemented'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing calibration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Preview Endpoints
# ============================================================================

@router.post("/preview/start")
async def start_preview(request: Optional[PanoramaPreviewStartRequest] = None):
    """
    Start panorama preview

    Starts real-time panorama stitching preview.
    Requires system to be calibrated first.
    HLS stream will be available at /hls/panorama.m3u8

    Returns 409 if recording is active (recording has priority).
    Returns 503 if not calibrated.
    """
    try:
        transport = request.transport if request else None
        result = panorama_service.start_preview(transport=transport)

        if result.get('success'):
            return result
        else:
            error_code = result.get('error_code')

            if error_code == 'NOT_CALIBRATED':
                raise HTTPException(
                    status_code=503,
                    detail=result.get('message', 'Panorama not calibrated')
                )
            elif error_code == 'RECORDING_ACTIVE':
                raise HTTPException(
                    status_code=409,
                    detail=result.get('message', 'Cannot start panorama: recording is active')
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=result.get('message', 'Failed to start preview')
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting panorama preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preview/stop")
async def stop_preview():
    """
    Stop panorama preview

    Stops the real-time panorama stitching preview.
    """
    try:
        result = panorama_service.stop_preview()

        if result.get('success'):
            return result
        else:
            raise HTTPException(
                status_code=400,
                detail=result.get('message', 'Failed to stop preview')
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping panorama preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Post-Processing Endpoint
# ============================================================================

@router.post("/process")
async def process_recording(request: ProcessRecordingRequest, background_tasks: BackgroundTasks):
    """
    Process a recording to create panorama

    Processes cam0_archive.mp4 and cam1_archive.mp4 from the specified match
    to create a stitched panorama_archive.mp4 file.

    Processing runs in the background and may take 1.5-2x the video duration.
    Use GET /api/v1/panorama/process/{match_id}/status to check progress.
    """
    try:
        result = panorama_service.process_recording(request.match_id)

        if result.get('success'):
            return result
        else:
            message = result.get('message', 'Failed to process recording')
            if 'not found' in message.lower():
                raise HTTPException(status_code=404, detail=message)
            else:
                raise HTTPException(status_code=400, detail=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/process/{match_id}/status")
async def get_processing_status(match_id: str):
    """
    Get processing status for a recording

    Returns progress information for panorama post-processing.
    """
    try:
        status = panorama_service.get_processing_status(match_id)
        return status
    except Exception as e:
        logger.error(f"Error getting processing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

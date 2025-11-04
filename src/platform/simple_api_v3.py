#!/usr/bin/env python3
"""
FootballVision Pro - API Server v3
Uses in-process GStreamer for instant, bulletproof operations
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from collections import defaultdict
from datetime import datetime
import re
import sys
import os
import psutil
import logging
import signal
import atexit
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Gauge, Counter

# Configure logging
os.makedirs('/var/log/footballvision/api', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            '/var/log/footballvision/api/api_v3.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add video-pipeline to path
sys.path.insert(0, str(Path(__file__).parent.parent / "video-pipeline"))

# Import new services
from recording_service import get_recording_service
from preview_service import get_preview_service
from pipeline_manager import pipeline_manager, PipelineMode

# Import development router
from dev_router import dev_router

app = FastAPI(
    title="FootballVision Pro API v3",
    description="In-process GStreamer for instant, bulletproof operations",
    version="3.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include development router
app.include_router(dev_router)

# Clean up any stale locks from previous runs
try:
    current_state = pipeline_manager.get_state()
    if current_state.get('mode') != 'idle':
        logger.warning(f"Found stale lock from {current_state.get('holder')}, cleaning up")
        pipeline_manager._force_release()
except Exception as e:
    logger.error(f"Failed to clean up stale locks: {e}")

# Initialize services
recording_service = get_recording_service()
preview_service = get_preview_service()

# Ensure all pipelines are stopped on startup
try:
    logger.info("Ensuring all pipelines are stopped on startup...")
    if preview_service.get_status().get('preview_active'):
        preview_service.stop_preview()
        logger.info("Stopped preview on startup")
    if recording_service.get_status().get('recording'):
        recording_service.stop_recording(force=True)
        logger.info("Stopped recording on startup")
except Exception as e:
    logger.warning(f"Pipeline cleanup on startup: {e}")

# Prometheus metrics
recording_active = Gauge('footballvision_recording_active', 'Recording status')
preview_active = Gauge('footballvision_preview_active', 'Preview status')
api_requests = Counter('footballvision_api_requests', 'API request count', ['endpoint', 'method'])

# Request models
class RecordingRequest(BaseModel):
    match_id: Optional[str] = None
    force: Optional[bool] = False

class RecordingStopRequest(BaseModel):
    force: Optional[bool] = False

class PreviewRequest(BaseModel):
    camera_id: Optional[int] = None  # None = both cameras


# ============================================================================
# Health & Status Endpoints
# ============================================================================

@app.get("/")
def root():
    api_requests.labels(endpoint='root', method='GET').inc()
    return {
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

@app.get("/api/v1/health")
def health_check():
    api_requests.labels(endpoint='health', method='GET').inc()
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/mnt/recordings')

        return {
            "status": "healthy",
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "disk_percent": disk.percent
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "error", "detail": str(e)}

@app.get("/api/v1/status")
def get_status():
    """Get overall system status"""
    api_requests.labels(endpoint='status', method='GET').inc()
    try:
        recording_status = recording_service.get_status()
        preview_status = preview_service.get_status()
        
        # Update Prometheus metrics
        recording_active.set(1 if recording_status['recording'] else 0)
        preview_active.set(1 if preview_status['preview_active'] else 0)
        
        return {
            "recording": recording_status,
            "preview": preview_status
        }
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Pipeline State Endpoint
# ============================================================================

@app.get("/api/v1/pipeline-state")
def get_pipeline_state():
    """Get current pipeline lock state"""
    api_requests.labels(endpoint='pipeline-state', method='GET').inc()
    try:
        state = pipeline_manager.get_state()
        return {
            'mode': state.get('mode', 'idle'),
            'holder': state.get('holder'),
            'lock_time': state.get('lock_time'),
            'can_preview': state.get('mode') in ['idle', 'preview'],
            'can_record': state.get('mode') == 'idle'
        }
    except Exception as e:
        logger.error(f"Failed to get pipeline state: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Recording Endpoints
# ============================================================================

@app.get("/api/v1/recording")
def get_recording_status():
    """Get current recording status"""
    api_requests.labels(endpoint='recording', method='GET').inc()
    try:
        status = recording_service.get_status()
        recording_active.set(1 if status['recording'] else 0)
        return status
    except Exception as e:
        logger.error(f"Failed to get recording status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/recording")
def start_recording(request: RecordingRequest):
    """
    Start dual-camera recording
    - Instant start (no 3s delay)
    - Returns immediately
    - Protected from accidental stops for 10s
    """
    api_requests.labels(endpoint='recording', method='POST').inc()
    try:
        # Generate match_id if not provided (do this BEFORE acquiring lock)
        if not request.match_id:
            from datetime import datetime
            request.match_id = f"match_{int(datetime.now().timestamp())}"

        # Acquire pipeline lock for recording mode
        if not pipeline_manager.acquire_lock(PipelineMode.RECORDING, f"api-recording-{request.match_id}", force=True, timeout=5.0):
            logger.error("Failed to acquire pipeline lock for recording")
            raise HTTPException(status_code=503, detail="Could not acquire camera resources for recording")

        # Check if preview is still running (shouldn't be after lock acquisition)
        preview_status = preview_service.get_status()
        if preview_status.get('preview_active'):
            logger.info("Preview still active after lock acquisition, force stopping")
            try:
                stop_result = preview_service.stop_preview()
                if not stop_result.get('success'):
                    logger.warning(f"Preview stop failed: {stop_result}, continuing anyway")
                # Give pipelines a moment to tear down
                time.sleep(1.0)
            except Exception as preview_err:
                logger.error(f"Error stopping preview: {preview_err}, continuing anyway")
        
        logger.info(f"Recording start requested: match_id={request.match_id}, force={request.force}")
        
        result = recording_service.start_recording(
            match_id=request.match_id,
            force=request.force
        )
        
        if result['success']:
            recording_active.set(1)
            logger.info(f"Recording started successfully: {result}")
        else:
            logger.warning(f"Recording start failed: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to start recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/recording")
def stop_recording(force: bool = False):
    """
    Stop dual-camera recording
    - Graceful stop with EOS (~2s, not 15s)
    - Protected: Cannot stop within first 10s unless force=True
    - Returns immediately
    """
    api_requests.labels(endpoint='recording', method='DELETE').inc()
    try:
        logger.info(f"Recording stop requested: force={force}")
        
        # Get match_id BEFORE stopping recording
        current_status = recording_service.get_status()
        match_id = current_status.get('match_id', 'unknown')

        result = recording_service.stop_recording(force=force)

        if result['success']:
            recording_active.set(0)
            # Release pipeline lock
            pipeline_manager.release_lock(f"api-recording-{match_id}")
            logger.info(f"Recording stopped successfully and lock released for match {match_id}")
        else:
            logger.warning(f"Recording stop failed: {result}")

        return result
        
    except Exception as e:
        logger.error(f"Failed to stop recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Preview Endpoints
# ============================================================================

@app.get("/api/v1/preview")
def get_preview_status():
    """Get current preview status"""
    api_requests.labels(endpoint='preview', method='GET').inc()
    try:
        status = preview_service.get_status()
        preview_active.set(1 if status['preview_active'] else 0)
        return status
    except Exception as e:
        logger.error(f"Failed to get preview status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/preview")
def start_preview(request: PreviewRequest):
    """
    Start HLS preview (one or both cameras)
    - Instant start
    - HLS available at /hls/cam{0,1}.m3u8
    """
    api_requests.labels(endpoint='preview', method='POST').inc()
    try:
        # Acquire pipeline lock for preview mode
        if not pipeline_manager.acquire_lock(PipelineMode.PREVIEW, f"api-preview-{request.camera_id or 'all'}", force=False, timeout=3.0):
            # Check current lock state to give better error message
            current_state = pipeline_manager.get_state()
            if current_state.get('mode') == 'recording':
                logger.warning("Preview start rejected: recording is active")
                raise HTTPException(
                    status_code=400,
                    detail="Recording is active. Stop recording before starting preview."
                )
            else:
                logger.error(f"Failed to acquire pipeline lock for preview, current mode: {current_state.get('mode')}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Could not acquire camera resources. Current mode: {current_state.get('mode')}"
                )

        logger.info(f"Preview start requested: camera_id={request.camera_id}")
        
        result = preview_service.start_preview(camera_id=request.camera_id)
        
        if result['success']:
            preview_active.set(1)
            logger.info(f"Preview started successfully: {result}")
        else:
            logger.warning(f"Preview start failed: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to start preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/preview")
def stop_preview(camera_id: Optional[int] = None):
    """Stop HLS preview (one or both cameras)"""
    api_requests.labels(endpoint='preview', method='DELETE').inc()
    try:
        logger.info(f"Preview stop requested: camera_id={camera_id}")
        
        result = preview_service.stop_preview(camera_id=camera_id)

        if result['success']:
            # Check if all previews stopped
            status = preview_service.get_status()
            if not status['preview_active']:
                preview_active.set(0)
                # Release pipeline lock when all previews are stopped
                pipeline_manager.release_lock(f"api-preview-{camera_id or 'all'}")
                logger.info(f"Preview stopped and lock released: {result}")
            else:
                logger.info(f"Preview stopped but some cameras still active: {result}")
        else:
            logger.warning(f"Preview stop failed: {result}")

        return result
        
    except Exception as e:
        logger.error(f"Failed to stop preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/preview/restart")
def restart_preview(request: PreviewRequest):
    """Restart HLS preview (one or both cameras)"""
    api_requests.labels(endpoint='preview_restart', method='POST').inc()
    try:
        recording_status = recording_service.get_status()
        if recording_status.get('recording'):
            logger.warning("Preview restart rejected: recording is active")
            raise HTTPException(
                status_code=400,
                detail="Recording is active. Stop recording before restarting preview."
            )

        logger.info(f"Preview restart requested: camera_id={request.camera_id}")
        result = preview_service.restart_preview(camera_id=request.camera_id)
        return result
    except Exception as e:
        logger.error(f"Failed to restart preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Cleanup on shutdown
# ============================================================================

def cleanup():
    """Cleanup on shutdown"""
    logger.info("API server shutting down, cleaning up...")
    try:
        # Release any held locks
        current_state = pipeline_manager.get_state()
        if current_state.get('mode') != 'idle':
            logger.info(f"Releasing pipeline lock held by {current_state.get('holder')}")
            pipeline_manager._force_release()

        recording_service.cleanup()
        preview_service.cleanup()
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

atexit.register(cleanup)

def signal_handler(signum, frame):
    """Handle SIGTERM and SIGINT"""
    logger.info(f"Received signal {signum}, shutting down...")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# ============================================================================
# Prometheus metrics
# ============================================================================

Instrumentator().instrument(app).expose(app)


# ============================================================================
# Static files for HLS
# ============================================================================


# ============================================================================
# Recordings Management Endpoints
# ============================================================================

VIDEO_EXTENSIONS = ['*.mkv', '*.mp4', '*.avi', '*.mov']
ARCHIVE_EXTENSIONS = ['*.zip']


def _extract_camera_from_name(filename: str) -> str:
    filename_lower = filename.lower()
    if 'cam0' in filename_lower:
        return 'cam0'
    if 'cam1' in filename_lower:
        return 'cam1'
    camera_match = re.search(r'cam(\d+)', filename_lower)
    if camera_match:
        return f"cam{camera_match.group(1)}"
    return 'unknown'


def _extract_segment_number(filename: str) -> Optional[int]:
    stem = Path(filename).stem
    match = re.search(r'(?:_|-)(\d{1,4})$', stem)
    if match:
        try:
            digits = match.group(1)
            value = int(digits)
            if digits.startswith('0') or value == 0:
                return value + 1
            return value
        except ValueError:
            return None
    # Fall back to searching anywhere in the stem
    match_any = re.search(r'(\d+)$', stem)
    if match_any:
        try:
            digits = match_any.group(1)
            value = int(digits)
            if digits.startswith('0') or value == 0:
                return value + 1
            return value
        except ValueError:
            return None
    return None


def _build_segment_info(match_id: str, file_path: Path, index: int) -> dict:
    stat_result = file_path.stat()
    size_mb = round(stat_result.st_size / (1024 * 1024), 2)
    created_at = int(stat_result.st_mtime)
    camera_key = _extract_camera_from_name(file_path.name)
    segment_number = _extract_segment_number(file_path.name)
    if segment_number is None:
        segment_number = index + 1

    return {
        "name": file_path.name,
        "path": f"/api/v1/recordings/{match_id}/segments/{file_path.name}",
        "size_mb": size_mb,
        "created_at": created_at,
        "segment_number": segment_number,
        "camera": camera_key,
    }


def _build_single_file_info(match_id: str, file_path: Path) -> dict:
    stat_result = file_path.stat()
    size_mb = round(stat_result.st_size / (1024 * 1024), 2)
    created_at = int(stat_result.st_mtime)
    return {
        "file": file_path.name,
        "size_mb": size_mb,
        "created_at": created_at,
        "type": "single",
        "path": f"/api/v1/recordings/{match_id}/files/{file_path.name}",
    }


@app.get("/api/v1/recordings")
def list_recordings():
    """List all recordings from /mnt/recordings with enhanced metadata"""
    api_requests.labels(endpoint='recordings', method='GET').inc()
    try:
        recordings_dir = Path("/mnt/recordings")
        recordings = {}

        if not recordings_dir.exists():
            return {"recordings": {}}

        for match_dir in recordings_dir.iterdir():
            if not match_dir.is_dir():
                continue

            match_id = match_dir.name
            segments_dir = match_dir / "segments"
            camera_segments = defaultdict(list)
            segments_total_size = 0.0
            first_segment_timestamp: Optional[int] = None

            if segments_dir.exists():
                for ext in VIDEO_EXTENSIONS:
                    for index, file_path in enumerate(sorted(segments_dir.glob(ext))):
                        if not file_path.is_file():
                            continue
                        segment_info = _build_segment_info(match_id, file_path, index)
                        camera_segments[segment_info["camera"]].append(segment_info)
                        segments_total_size += segment_info["size_mb"]
                        if first_segment_timestamp is None or segment_info["created_at"] < first_segment_timestamp:
                            first_segment_timestamp = segment_info["created_at"]

            files = []
            total_segments = 0

            for camera, segments in camera_segments.items():
                if not segments:
                    continue
                segments_sorted = sorted(segments, key=lambda s: s["segment_number"])
                camera_size = round(sum(s["size_mb"] for s in segments_sorted), 2)
                total_segments += len(segments_sorted)
                files.append({
                    "file": camera,
                    "type": "segmented",
                    "segment_count": len(segments_sorted),
                    "size_mb": camera_size,
                    "created_at": segments_sorted[0]["created_at"],
                })

            single_files = []
            for ext in VIDEO_EXTENSIONS + ARCHIVE_EXTENSIONS:
                for file_path in sorted(match_dir.glob(ext)):
                    if not file_path.is_file():
                        continue
                    single_files.append(_build_single_file_info(match_id, file_path))

            files.extend(single_files)

            if files:
                total_size_mb = round(
                    segments_total_size + sum(f["size_mb"] for f in single_files),
                    2,
                )
                recordings[match_id] = {
                    "files": files,
                    "total_size_mb": total_size_mb,
                    "camera_count": sum(1 for segments in camera_segments.values() if segments),
                    "segments_count": total_segments,
                    "created_at": first_segment_timestamp,
                }

        return {"recordings": recordings}

    except Exception as e:
        logger.error(f"Failed to list recordings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/recordings/{match_id}/segments")
def get_recording_segments(match_id: str):
    """Get segments for a specific recording grouped by camera"""
    api_requests.labels(endpoint='recording_segments', method='GET').inc()
    try:
        segments_dir = Path(f"/mnt/recordings/{match_id}/segments")

        if not segments_dir.exists():
            raise HTTPException(status_code=404, detail=f"Recording {match_id} not found")

        camera_segments = defaultdict(list)
        for ext in VIDEO_EXTENSIONS:
            for index, file_path in enumerate(sorted(segments_dir.glob(ext))):
                if not file_path.is_file():
                    continue
                segment_info = _build_segment_info(match_id, file_path, index)
                camera_segments[segment_info["camera"]].append(segment_info)

        total_segments = 0
        total_size = 0.0
        normalized_segments = {}

        for camera, segments in camera_segments.items():
            if not segments:
                continue
            segments_sorted = sorted(segments, key=lambda s: s["segment_number"])
            # Ensure sequential numbering for display
            for idx, segment in enumerate(segments_sorted):
                segment["segment_number"] = idx + 1
            normalized_segments[camera] = segments_sorted
            total_segments += len(segments_sorted)
            total_size += sum(segment["size_mb"] for segment in segments_sorted)

        return {
            "match_id": match_id,
            "type": "segmented" if total_segments > 1 else "single",
            "cam0": normalized_segments.get('cam0', []),
            "cam1": normalized_segments.get('cam1', []),
            "other": normalized_segments.get('unknown', []),
            "total_size_mb": round(total_size, 2),
            "segments_count": total_segments,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get segments for {match_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/recordings/{match_id}")
def delete_recording(match_id: str):
    """Delete a recording and all its files"""
    api_requests.labels(endpoint='recording_delete', method='DELETE').inc()
    try:
        import shutil
        
        match_dir = Path(f"/mnt/recordings/{match_id}")
        
        if not match_dir.exists():
            raise HTTPException(status_code=404, detail=f"Recording {match_id} not found")
        
        # Calculate total size before deletion
        total_size = 0
        file_count = 0
        for file_path in match_dir.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1
        
        size_mb_freed = total_size / (1024 * 1024)
        
        # Delete the entire recording directory
        shutil.rmtree(match_dir)
        
        logger.info(f"Deleted recording {match_id}: {file_count} files, {size_mb_freed:.2f} MB freed")
        
        return {
            "status": "deleted",
            "match_id": match_id,
            "files_deleted": file_count,
            "size_mb_freed": round(size_mb_freed, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete recording {match_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/recordings/{match_id}/download")
def download_recording(match_id: str):
    """Download entire recording as a zip file"""
    api_requests.labels(endpoint='recording_download', method='GET').inc()
    try:
        import zipfile
        import tempfile
        from fastapi.responses import FileResponse
        
        match_dir = Path(f"/mnt/recordings/{match_id}")
        
        if not match_dir.exists():
            raise HTTPException(status_code=404, detail=f"Recording {match_id} not found")
        
        # Create temporary zip file
        with tempfile.NamedTemporaryFile(mode='w+b', suffix='.zip', delete=False) as tmp_file:
            zip_path = tmp_file.name
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Add all files from match directory
                for file_path in match_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(match_dir.parent)
                        zipf.write(file_path, arcname=arcname)
        
        # Return as downloadable file
        return FileResponse(
            path=zip_path,
            media_type='application/zip',
            filename=f"{match_id}.zip",
            headers={"Content-Disposition": f"attachment; filename={match_id}.zip"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create download for {match_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/recordings/{match_id}/segments/{segment_name}")
def download_recording_segment(match_id: str, segment_name: str):
    """Download an individual recording segment"""
    api_requests.labels(endpoint='recording_segment_download', method='GET').inc()
    try:
        safe_name = Path(segment_name).name
        segment_path = Path(f"/mnt/recordings/{match_id}/segments") / safe_name

        if not segment_path.exists() or not segment_path.is_file():
            raise HTTPException(status_code=404, detail="Segment not found")

        return FileResponse(
            path=str(segment_path),
            media_type='application/octet-stream',
            filename=safe_name,
            headers={"Content-Disposition": f"attachment; filename={safe_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream recording segment {segment_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/recordings/{match_id}/files/{file_name}")
def download_recording_file(match_id: str, file_name: str):
    """Download a direct recording file from the match directory"""
    api_requests.labels(endpoint='recording_file_download', method='GET').inc()
    try:
        safe_name = Path(file_name).name
        file_path = Path(f"/mnt/recordings/{match_id}") / safe_name

        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Recording file not found")

        return FileResponse(
            path=str(file_path),
            media_type='application/octet-stream',
            filename=safe_name,
            headers={"Content-Disposition": f"attachment; filename={safe_name}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream recording file {file_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/logs/{log_type}")
def get_logs(log_type: str, lines: int = 100):
    """Get system logs - supports: health, alerts, watchdog"""
    api_requests.labels(endpoint='logs', method='GET').inc()
    try:
        log_files = {
            'health': '/var/log/footballvision/system/health_monitor.log',
            'alerts': '/var/log/footballvision/system/alerts.log',
            'watchdog': '/var/log/footballvision/system/watchdog.log'
        }

        if log_type not in log_files:
            raise HTTPException(status_code=400, detail=f"Unknown log type. Available: {', '.join(log_files.keys())}")

        log_path = Path(log_files[log_type])
        if not log_path.exists():
            return {"log_type": log_type, "lines": [], "message": "Log file does not exist yet"}

        # Read last N lines
        with open(log_path, 'r') as f:
            all_lines = f.readlines()
            last_lines = all_lines[-lines:] if lines < len(all_lines) else all_lines

        return {
            "log_type": log_type,
            "lines": [line.strip() for line in last_lines],
            "total_lines": len(last_lines)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Mount HLS directory
if Path("/tmp/hls").exists():
    app.mount("/hls", StaticFiles(directory="/tmp/hls"), name="hls")


# ============================================================================
# Run server
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    # Support API_PORT environment variable for development/production separation
    port = int(os.getenv('API_PORT', '8000'))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )

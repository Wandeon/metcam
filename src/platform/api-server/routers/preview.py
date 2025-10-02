"""Preview control endpoints"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import subprocess
import signal
import os

router = APIRouter(prefix="/api/v1/preview", tags=["Preview"])

def check_recording_active():
    """Check if recording is active"""
    # Use ps to avoid matching pgrep itself
    result = subprocess.run("ps aux | grep 'nvarguscamerasrc.*mp4mux' | grep -v grep", shell=True, capture_output=True)
    return result.returncode == 0 and len(result.stdout.strip()) > 0

def check_preview_active():
    """Check if HLS preview is active"""
    result = subprocess.run("ps aux | grep 'nvarguscamerasrc.*hlssink' | grep -v grep", shell=True, capture_output=True)
    return result.returncode == 0 and len(result.stdout.strip()) > 0

def check_calibration_active():
    """Check if calibration preview is active"""
    result = subprocess.run("ps aux | grep 'multifilesink.*cam0.jpg' | grep -v grep", shell=True, capture_output=True)
    return result.returncode == 0 and len(result.stdout.strip()) > 0

@router.post("/calibration/start")
async def start_calibration_preview():
    """
    Start calibration preview service (10% center crop for focus)
    """
    # Check for conflicts
    if check_recording_active():
        raise HTTPException(status_code=409, detail="Cannot start: Recording is active")
    if check_preview_active():
        raise HTTPException(status_code=409, detail="Cannot start: HLS preview is active")
    if check_calibration_active():
        raise HTTPException(status_code=400, detail="Calibration preview already running")

    # Start calibration preview service
    try:
        subprocess.run(["sudo", "systemctl", "start", "calibration-preview"], check=True)
        return {"status": "started", "message": "Calibration preview started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start: {str(e)}")

@router.post("/calibration/stop")
async def stop_calibration_preview():
    """
    Stop calibration preview service
    """
    try:
        # Stop systemd service
        subprocess.run(["sudo", "systemctl", "stop", "calibration-preview"], check=False)
        # Also kill any remaining processes
        subprocess.run("pkill -f 'multifilesink.*cam.*.jpg'", shell=True, check=False)
        return {"status": "stopped", "message": "Calibration preview stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop: {str(e)}")

@router.get("/calibration/status")
async def get_calibration_status():
    """
    Get status of calibration preview service

    Returns:
        Service running status
    """
    running = check_calibration_active()
    return {"running": running, "status": "active" if running else "stopped"}

@router.get("/calibration/cam0/snapshot")
async def get_cam0_snapshot():
    """
    Get latest snapshot from camera 0 (800x800 center crop for focus calibration)

    Returns:
        JPEG image from /dev/shm/cam0.jpg
    """
    snapshot_path = "/dev/shm/cam0.jpg"

    if not os.path.exists(snapshot_path):
        raise HTTPException(
            status_code=404,
            detail="Camera 0 snapshot not available. Is calibration preview running?"
        )

    return FileResponse(
        snapshot_path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@router.get("/calibration/cam1/snapshot")
async def get_cam1_snapshot():
    """
    Get latest snapshot from camera 1 (800x800 center crop for focus calibration)

    Returns:
        JPEG image from /dev/shm/cam1.jpg
    """
    snapshot_path = "/dev/shm/cam1.jpg"

    if not os.path.exists(snapshot_path):
        raise HTTPException(
            status_code=404,
            detail="Camera 1 snapshot not available. Is calibration preview running?"
        )

    return FileResponse(
        snapshot_path,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

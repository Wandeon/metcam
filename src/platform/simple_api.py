#!/usr/bin/env python3
"""
FootballVision Pro - Simple API Server
Minimal REST API for recording control
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
import os
import psutil
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Gauge, Counter
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent / "api-server" / ".env"
load_dotenv(env_path)

# Configure logging
os.makedirs('/var/log/footballvision/api', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            '/var/log/footballvision/api/api.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add video-pipeline to path
sys.path.insert(0, str(Path(__file__).parent.parent / "video-pipeline"))

from recording_manager import RecordingManager
from preview_service import PreviewService

app = FastAPI(title="FootballVision Pro API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

recording_manager = RecordingManager()
preview_service = PreviewService()

# Prometheus metrics
recording_status_gauge = Gauge('recording_status', 'Recording status (1=active, 0=idle)')
frames_captured_counter = Counter('frames_captured_total', 'Total frames captured')
frames_dropped_counter = Counter('frames_dropped_total', 'Total frames dropped')
system_temperature_gauge = Gauge('system_temperature_celsius', 'System temperature in Celsius')
storage_available_gauge = Gauge('storage_available_bytes', 'Available storage in bytes')
cpu_usage_gauge = Gauge('cpu_usage_percent', 'CPU usage percentage')
network_connected_gauge = Gauge('network_connected', 'Network connection status (1=connected, 0=disconnected)')

# Initialize Prometheus instrumentator
Instrumentator().instrument(app).expose(app)

# Import and start auto-processor
sys.path.insert(0, str(Path(__file__).parent / "api-server/services"))
from auto_processor import auto_processor
from activity_logger import activity_logger

# Add database support
sys.path.insert(0, str(Path(__file__).parent / "database"))
from db_manager import db

def update_metrics():
    """Update Prometheus metrics"""
    import threading

    def _update():
        while True:
            try:
                # Recording status
                status = recording_manager.get_status()
                recording_status_gauge.set(1 if status.get('recording') else 0)

                # System temperature (Jetson thermal zone)
                try:
                    with open('/sys/devices/virtual/thermal/thermal_zone0/temp', 'r') as f:
                        temp = float(f.read().strip()) / 1000.0
                        system_temperature_gauge.set(temp)
                except:
                    pass

                # Storage available
                stat = os.statvfs('/mnt/recordings')
                storage_available_gauge.set(stat.f_bavail * stat.f_frsize)

                # CPU usage
                cpu_usage_gauge.set(psutil.cpu_percent(interval=1))

                # Network status (check if we can reach gateway)
                import subprocess
                try:
                    subprocess.check_call(['ping', '-c', '1', '-W', '1', '8.8.8.8'],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    network_connected_gauge.set(1)
                except:
                    network_connected_gauge.set(0)

            except Exception as e:
                print(f"Metrics update error: {e}")

            import time
            time.sleep(15)  # Update every 15 seconds

    thread = threading.Thread(target=_update, daemon=True)
    thread.start()

@app.on_event("startup")
async def startup_event():
    """Start auto-processor and metrics updater on API startup"""
    auto_processor.start()
    update_metrics()

@app.on_event("shutdown")
async def shutdown_event():
    """Stop auto-processor on API shutdown"""
    auto_processor.stop()

class RecordingRequest(BaseModel):
    match_id: str
    resolution: str = "3840x2160"  # 4K UHD (sensor supports: 4032x3040@21fps, 3840x2160@30fps, 1920x1080@60fps)
    fps: int = 22  # 22fps optimal for dual 4K recording
    bitrate: int = 100000  # 100 Mbps - ~50 Mbps actual, ~162GB per 150min match

@app.get("/")
def root():
    return {"status": "FootballVision Pro API v1.0", "recording": recording_manager.get_status()}

@app.get("/api/v1/status")
def get_status():
    return recording_manager.get_status()

@app.post("/api/v1/recording")
def start_recording(request: RecordingRequest):
    try:
        result = recording_manager.start_recording(
            match_id=request.match_id,
            resolution=request.resolution,
            fps=request.fps,
            bitrate=request.bitrate
        )

        # Log recording start
        activity_logger.log_recording_started(request.match_id)
        logger.info(f"Recording started: {request.match_id}")

        # Store match in database
        try:
            db.execute(
                "INSERT OR IGNORE INTO matches (id, status) VALUES (?, 'recording')",
                (request.match_id,)
            )
            db.execute(
                """INSERT INTO recording_sessions
                   (match_id, status) VALUES (?, 'recording')""",
                (request.match_id,)
            )
        except Exception as e:
            logger.error(f"Failed to create database record: {e}")

        return result
    except RuntimeError as e:
        activity_logger.log_error('recording', str(e), 'error', request.match_id)
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/v1/recording")
def stop_recording():
    # Get current status before stopping
    status = recording_manager.get_status()
    match_id = status.get('match_id', 'unknown')

    result = recording_manager.stop_recording()

    # Log recording stop
    duration = result.get('duration', 0)
    files = result.get('files', [])
    total_size = sum([os.path.getsize(f) for f in files if os.path.exists(f)])

    activity_logger.log_recording_stopped(
        match_id,
        duration,
        total_size,
        frames_captured=0,
        frames_dropped=0
    )
    logger.info(f"Recording stopped: {match_id}, duration: {duration}s, size: {total_size/(1024**3):.2f}GB")

    # Update database
    try:
        db.execute(
            """UPDATE recording_sessions
               SET stopped_at = datetime('now'), duration_seconds = ?,
                   status = 'completed'
               WHERE match_id = ? AND stopped_at IS NULL""",
            (duration, match_id)
        )
        db.execute(
            "UPDATE matches SET status = 'completed' WHERE id = ?",
            (match_id,)
        )
    except Exception as e:
        logger.error(f"Failed to update database record: {e}")

    return result

@app.get("/api/v1/recordings")
def list_recordings():
    recordings_dir = Path("/mnt/recordings")
    files = list(recordings_dir.glob("*.mp4"))

    recordings = {}
    for f in files:
        match_id = f.stem.rsplit('_cam', 1)[0]
        if '_sidebyside' in f.stem:
            match_id = f.stem.replace('_sidebyside', '')

        if match_id not in recordings:
            recordings[match_id] = []

        stat = f.stat()
        recordings[match_id].append({
            'file': f.name,
            'size_mb': stat.st_size / 1024 / 1024,
            'created_at': stat.st_mtime  # Unix timestamp
        })

    return {"recordings": recordings}

# ============================================================================
# Preview Stream Endpoints
# ============================================================================

@app.get("/api/v1/preview/status")
def get_preview_status():
    """Get current preview stream status"""
    return preview_service.get_status()

@app.post("/api/v1/preview/start")
def start_preview():
    """Start HLS preview stream (4032x3040 @ 5fps)"""
    try:
        result = preview_service.start()
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/v1/preview/stop")
def stop_preview():
    """Stop HLS preview stream"""
    result = preview_service.stop()
    return result


# Route aliases for UI compatibility (maps /api/preview/* to /api/v1/preview/*)
@app.get("/api/preview/status")
def get_preview_status_alias():
    return get_preview_status()

@app.post("/api/preview/start")
def start_preview_alias():
    return start_preview()

@app.post("/api/preview/stop")
def stop_preview_alias():
    return stop_preview()

# Import and register routers
sys.path.insert(0, str(Path(__file__).parent / "api-server"))
from routers import preview as preview_router
from routers import processing, upload, activity

app.include_router(preview_router.router)
app.include_router(processing.router)
app.include_router(upload.router)
app.include_router(activity.router)

if __name__ == "__main__":
    import uvicorn
    print("Starting FootballVision Pro API Server...")
    print("  API: http://0.0.0.0:8000")
    print("  Docs: http://0.0.0.0:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)

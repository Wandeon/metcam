"""
Upload to nk-otok.hr via SFTP with database tracking and resume capability
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
import os
import sys
from pathlib import Path
from datetime import datetime
import time

# Import dependencies
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))
from sftp_uploader import SFTPUploader
from activity_logger import activity_logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "database"))
from db_manager import db

router = APIRouter(prefix="/api/v1/upload", tags=["Upload"])


class UploadJob(BaseModel):
    file_path: str
    remote_filename: str = None
    bandwidth_limit_mbps: int = 10  # Default 10 Mbps


@router.post("/start")
async def start_upload(job: UploadJob, background_tasks: BackgroundTasks):
    """Start SFTP upload to nk-otok.hr with database tracking"""

    # Verify file exists
    if not os.path.exists(job.file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Generate remote filename if not provided
    if not job.remote_filename:
        job.remote_filename = os.path.basename(job.file_path)

    # Read SFTP credentials from environment
    sftp_host = os.getenv('SFTP_HOST', 'nk-otok.hr')
    sftp_user = os.getenv('SFTP_USERNAME')
    sftp_pass = os.getenv('SFTP_PASSWORD')
    sftp_dir = os.getenv('SFTP_REMOTE_DIR', '/recordings')

    if not sftp_user or not sftp_pass:
        raise HTTPException(status_code=500, detail="SFTP credentials not configured")

    remote_path = f"{sftp_dir}/{job.remote_filename}"
    file_size = os.path.getsize(job.file_path)

    # Extract match_id from filename
    match_id = Path(job.file_path).stem.rsplit('_', 1)[0]

    # Create database record
    upload_id = db.insert(
        """INSERT INTO cloud_uploads
           (match_id, file_path, file_name, destination, status, total_bytes, bandwidth_limit_mbps)
           VALUES (?, ?, ?, ?, 'starting', ?, ?)""",
        (match_id, job.file_path, job.remote_filename, remote_path, file_size, job.bandwidth_limit_mbps)
    )

    # Log activity
    activity_logger.log_upload_started(match_id, job.file_path, remote_path)

    # Start upload in background
    background_tasks.add_task(
        run_upload,
        upload_id,
        match_id,
        job.file_path,
        remote_path,
        sftp_host,
        sftp_user,
        sftp_pass,
        job.bandwidth_limit_mbps
    )

    return {
        'upload_id': upload_id,
        'status': 'started',
        'remote_path': remote_path
    }


@router.get("/status/{upload_id}")
async def get_upload_status(upload_id: int):
    """Get upload status from database"""
    upload = db.execute_one(
        "SELECT * FROM cloud_uploads WHERE id = ?",
        (upload_id,)
    )

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    return upload


@router.get("/history")
async def get_upload_history(limit: int = 50):
    """Get upload history from database"""
    uploads = db.execute(
        """SELECT * FROM cloud_uploads
           ORDER BY started_at DESC LIMIT ?""",
        (limit,)
    )
    return {'uploads': uploads}


@router.post("/resume/{upload_id}")
async def resume_upload(upload_id: int, background_tasks: BackgroundTasks):
    """Resume failed upload"""
    upload = db.execute_one(
        "SELECT * FROM cloud_uploads WHERE id = ?",
        (upload_id,)
    )

    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")

    if upload['status'] == 'completed':
        raise HTTPException(status_code=400, detail="Upload already completed")

    # Read SFTP credentials
    sftp_host = os.getenv('SFTP_HOST', 'nk-otok.hr')
    sftp_user = os.getenv('SFTP_USERNAME')
    sftp_pass = os.getenv('SFTP_PASSWORD')

    # Resume upload
    background_tasks.add_task(
        run_upload,
        upload_id,
        upload['match_id'],
        upload['file_path'],
        upload['destination'],
        sftp_host,
        sftp_user,
        sftp_pass,
        upload['bandwidth_limit_mbps'],
        resume=True
    )

    return {'upload_id': upload_id, 'status': 'resuming'}


def run_upload(
    upload_id: int,
    match_id: str,
    local_path: str,
    remote_path: str,
    host: str,
    username: str,
    password: str,
    bandwidth_limit_mbps: int = 10,
    resume: bool = False
):
    """Background task for SFTP upload with database tracking"""
    start_time = time.time()

    try:
        # Update status
        db.execute(
            "UPDATE cloud_uploads SET status = 'uploading' WHERE id = ?",
            (upload_id,)
        )

        # Create uploader with bandwidth limit
        uploader = SFTPUploader(host, username, password, bandwidth_limit_mbps)

        file_size = os.path.getsize(local_path)
        resume_position = 0

        # Check for resume
        if resume:
            upload_data = db.execute_one(
                "SELECT resume_position FROM cloud_uploads WHERE id = ?",
                (upload_id,)
            )
            resume_position = upload_data.get('resume_position', 0) if upload_data else 0

        def progress_callback(transferred, total):
            percent = int((transferred / total) * 100)
            db.execute(
                """UPDATE cloud_uploads
                   SET progress_percent = ?, bytes_uploaded = ?, resume_position = ?
                   WHERE id = ?""",
                (percent, transferred, transferred, upload_id)
            )

        # Upload file
        uploader.upload_file(local_path, remote_path, progress_callback, resume_position)
        uploader.disconnect()

        # Calculate duration and speed
        duration = int(time.time() - start_time)

        # Mark as completed
        db.execute(
            """UPDATE cloud_uploads
               SET status = 'completed', progress_percent = 100,
                   bytes_uploaded = ?, completed_at = datetime('now')
               WHERE id = ?""",
            (file_size, upload_id)
        )

        # Log completion
        activity_logger.log_upload_completed(match_id, upload_id, file_size, duration)

    except Exception as e:
        # Mark as failed
        db.execute(
            """UPDATE cloud_uploads
               SET status = 'failed', error_message = ?
               WHERE id = ?""",
            (str(e), upload_id)
        )

        # Log error
        activity_logger.log_error('upload', str(e), 'error', match_id)

"""
Processing pipeline API
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
import subprocess
import os
import json
import sys
from pathlib import Path
from datetime import datetime

# Import activity logger
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))
from activity_logger import activity_logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "database"))
from db_manager import db

router = APIRouter(prefix="/api/v1/processing", tags=["Processing"])

# Store active jobs in memory (in production, use Redis or database)
active_jobs = {}

class ProcessingJob(BaseModel):
    match_id: str
    cam0_path: str = None
    cam1_path: str = None

@router.post("/start")
async def start_processing(job: ProcessingJob, background_tasks: BackgroundTasks):
    """Start side-by-side video processing"""

    # Auto-detect files if not provided
    if not job.cam0_path or not job.cam1_path:
        recordings_dir = "/mnt/recordings"
        job.cam0_path = f"{recordings_dir}/{job.match_id}_cam0.mp4"
        job.cam1_path = f"{recordings_dir}/{job.match_id}_cam1.mp4"

    # Verify files exist
    if not os.path.exists(job.cam0_path):
        raise HTTPException(status_code=404, detail=f"Camera 0 file not found: {job.cam0_path}")
    if not os.path.exists(job.cam1_path):
        raise HTTPException(status_code=404, detail=f"Camera 1 file not found: {job.cam1_path}")

    # Generate output path
    output_path = f"/mnt/recordings/{job.match_id}_sidebyside.mp4"
    job_id = f"job_{job.match_id}_{int(datetime.now().timestamp())}"

    # Create job status
    active_jobs[job_id] = {
        'status': 'starting',
        'progress': 0,
        'message': 'Initializing...',
        'output_path': output_path,
        'match_id': job.match_id,
        'started_at': datetime.now().isoformat()
    }

    # Log to database and activity log
    activity_logger.log_processing_started(job.match_id, job_id, 'sidebyside')
    try:
        db.insert(
            """INSERT INTO processing_jobs
               (job_id, match_id, job_type, status)
               VALUES (?, ?, 'sidebyside', 'starting')""",
            (job_id, job.match_id)
        )
    except Exception as e:
        print(f"Failed to create processing job record: {e}")

    # Start processing in background
    background_tasks.add_task(run_processing, job_id, job.cam0_path, job.cam1_path, output_path)

    return {
        'job_id': job_id,
        'status': 'started',
        'estimated_time_minutes': 10,  # Rough estimate for side-by-side
        'output_path': output_path
    }

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    """Get processing job status"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return active_jobs[job_id]

@router.get("/jobs")
async def list_jobs():
    """List all processing jobs"""
    return {
        'jobs': [
            {'job_id': jid, **info}
            for jid, info in active_jobs.items()
        ]
    }

def run_processing(job_id: str, cam0_path: str, cam1_path: str, output_path: str):
    """Background task to run processing"""
    try:
        active_jobs[job_id]['status'] = 'processing'
        active_jobs[job_id]['message'] = 'Creating side-by-side video...'

        # Run the processing script
        cmd = f"python3 /home/mislav/footballvision-pro/src/processing/src/processing/simple_sidebyside.py {cam0_path} {cam1_path} {output_path}"

        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )

        # Track progress from output
        for line in process.stdout:
            if '[' in line and '%]' in line:
                try:
                    percent = int(line.split('[')[1].split('%]')[0])
                    message = line.split('%]')[1].strip()
                    active_jobs[job_id]['progress'] = percent
                    active_jobs[job_id]['message'] = message
                except:
                    pass

        process.wait()

        if process.returncode == 0:
            active_jobs[job_id]['status'] = 'completed'
            active_jobs[job_id]['progress'] = 100
            active_jobs[job_id]['message'] = 'Processing complete!'
            active_jobs[job_id]['completed_at'] = datetime.now().isoformat()

            # Get output file size
            if os.path.exists(output_path):
                size_gb = os.path.getsize(output_path) / (1024**3)
                active_jobs[job_id]['output_size_gb'] = round(size_gb, 2)

            # Log completion
            match_id = active_jobs[job_id]['match_id']
            activity_logger.log_processing_completed(match_id, job_id, output_path)
            try:
                db.execute(
                    """UPDATE processing_jobs
                       SET status = 'completed', progress_percent = 100,
                           output_path = ?, completed_at = datetime('now')
                       WHERE job_id = ?""",
                    (output_path, job_id)
                )
            except Exception as e:
                print(f"Failed to update processing job: {e}")
        else:
            active_jobs[job_id]['status'] = 'failed'
            active_jobs[job_id]['message'] = 'Processing failed'

            # Log error
            match_id = active_jobs[job_id]['match_id']
            activity_logger.log_error('processing', 'Processing failed', 'error', match_id)
            try:
                db.execute(
                    """UPDATE processing_jobs
                       SET status = 'failed', error_message = 'Processing failed'
                       WHERE job_id = ?""",
                    (job_id,)
                )
            except Exception as e:
                print(f"Failed to update processing job: {e}")

    except Exception as e:
        active_jobs[job_id]['status'] = 'failed'
        active_jobs[job_id]['message'] = str(e)

        # Log error
        match_id = active_jobs[job_id].get('match_id', 'unknown')
        activity_logger.log_error('processing', str(e), 'error', match_id)

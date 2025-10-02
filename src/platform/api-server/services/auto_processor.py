"""
Automatic post-recording processor
Monitors /mnt/recordings for new recordings, creates side-by-side, and uploads to nk-otok.hr
"""

import os
import sys
import time
import threading
import logging
from pathlib import Path
from datetime import datetime

# Import processing and upload functionality
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "processing/src"))
from processing.simple_sidebyside import create_sidebyside

sys.path.insert(0, str(Path(__file__).parent))
from sftp_uploader import SFTPUploader
from activity_logger import activity_logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "database"))
from db_manager import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoProcessor:
    """Automatically process and upload completed recordings"""

    def __init__(self, recordings_dir="/mnt/recordings"):
        self.recordings_dir = Path(recordings_dir)
        self.processing_lock = threading.Lock()
        self.running = False
        self.worker_thread = None

        # SFTP configuration
        self.sftp_host = os.getenv('SFTP_HOST', 'nk-otok.hr')
        self.sftp_user = os.getenv('SFTP_USERNAME')
        self.sftp_pass = os.getenv('SFTP_PASSWORD')
        self.sftp_dir = os.getenv('SFTP_REMOTE_DIR', '/recordings')

    def start(self):
        """Start auto-processing worker"""
        if self.running:
            logger.warning("Auto-processor already running")
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("Auto-processor started")

    def stop(self):
        """Stop auto-processing worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Auto-processor stopped")

    def _worker_loop(self):
        """Main worker loop - checks for new recordings every 10 seconds"""
        while self.running:
            try:
                self._check_for_new_recordings()
            except Exception as e:
                logger.error(f"Error in auto-processor: {e}")

            time.sleep(10)  # Check every 10 seconds

    def _check_for_new_recordings(self):
        """Check for completed recordings that need processing"""
        if not self.recordings_dir.exists():
            return

        # Group files by match_id
        recordings = {}
        for f in self.recordings_dir.glob("*.mp4"):
            # Skip sidebyside files
            if "_sidebyside.mp4" in f.name:
                continue

            # Extract match_id (everything before _cam0 or _cam1)
            if "_cam0.mp4" in f.name:
                match_id = f.name.replace("_cam0.mp4", "")
            elif "_cam1.mp4" in f.name:
                match_id = f.name.replace("_cam1.mp4", "")
            else:
                continue

            if match_id not in recordings:
                recordings[match_id] = {"cam0": None, "cam1": None}

            if "_cam0.mp4" in f.name:
                recordings[match_id]["cam0"] = f
            elif "_cam1.mp4" in f.name:
                recordings[match_id]["cam1"] = f

        # Process matches that have both cameras and haven't been uploaded
        for match_id, cams in recordings.items():
            # Check if already uploaded by querying database
            if self._is_already_uploaded(match_id):
                continue

            if cams["cam0"] and cams["cam1"]:
                # Check if both files are fully written (no size change for 5 seconds)
                # This prevents processing while recording is still in progress
                if not self._is_file_stable(cams["cam0"]) or not self._is_file_stable(cams["cam1"]):
                    continue

                # Process this match
                logger.info(f"Found new recording: {match_id}")
                self._process_match(match_id, cams["cam0"], cams["cam1"])

    def _is_already_uploaded(self, match_id):
        """Check if match has already been uploaded by checking activity log"""
        try:
            # Check activity log for completed uploads
            import requests
            response = requests.get(f'http://localhost:8000/api/v1/activity/?limit=100', timeout=2)
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])

                # Count completed upload events for this match
                completed_uploads = [
                    e for e in events
                    if e.get('match_id') == match_id and e.get('event_type') == 'upload_completed'
                ]

                # Consider uploaded if we have at least 2 completed uploads (both cameras)
                return len(completed_uploads) >= 2
            return False
        except:
            return False

    def _is_file_stable(self, filepath, wait_seconds=5):
        """Check if file size is stable (not being written to)"""
        try:
            size1 = filepath.stat().st_size
            time.sleep(wait_seconds)
            size2 = filepath.stat().st_size
            return size1 == size2 and size1 > 0
        except:
            return False

    def _process_match(self, match_id, cam0_path, cam1_path):
        """Upload raw camera files to workstation for processing"""
        with self.processing_lock:
            # Double-check upload status in case it changed
            if self._is_already_uploaded(match_id):
                return

            try:
                # Skip processing - just upload raw files to workstation
                if not self.sftp_user or not self.sftp_pass:
                    logger.warning(f"[{match_id}] SFTP credentials not configured, skipping upload")
                    return

                logger.info(f"[{match_id}] Uploading raw files to {self.sftp_host} for processing...")

                # Upload both camera files
                for cam_file in [cam0_path, cam1_path]:
                    file_size = os.path.getsize(str(cam_file))
                    upload_start_time = time.time()
                    remote_path = f"{self.sftp_dir}/{cam_file.name}"

                    # Log upload start
                    activity_logger.log_upload_started(match_id, str(cam_file), remote_path)

                    # Create upload record in database
                    try:
                        upload_id = db.insert(
                            """INSERT INTO cloud_uploads
                               (match_id, file_path, file_name, destination, status, total_bytes, bandwidth_limit_mbps)
                               VALUES (?, ?, ?, ?, 'uploading', ?, 10)""",
                            (match_id, str(cam_file), cam_file.name, remote_path, file_size)
                        )
                    except Exception as e:
                        logger.error(f"Failed to create upload record: {e}")
                        upload_id = None

                    uploader = SFTPUploader(self.sftp_host, self.sftp_user, self.sftp_pass, bandwidth_limit_mbps=10)

                    def upload_progress(transferred, total):
                        percent = int((transferred / total) * 100)
                        if percent % 10 == 0:  # Log every 10%
                            logger.info(f"[{cam_file.name}] Upload: {percent}% ({transferred/(1024**3):.2f}GB / {total/(1024**3):.2f}GB)")

                        # Update database progress
                        if upload_id:
                            try:
                                db.execute(
                                    """UPDATE cloud_uploads
                                       SET progress_percent = ?, bytes_uploaded = ?
                                       WHERE id = ?""",
                                    (percent, transferred, upload_id)
                                )
                            except:
                                pass

                    uploader.upload_file(str(cam_file), remote_path, upload_progress)
                    uploader.disconnect()

                    logger.info(f"[{match_id}] Upload complete: {remote_path}")

                    # Log upload completion
                    upload_duration = int(time.time() - upload_start_time)
                    activity_logger.log_upload_completed(match_id, upload_id if upload_id else 0, file_size, upload_duration)

                    # Update database
                    if upload_id:
                        try:
                            db.execute(
                                """UPDATE cloud_uploads
                                   SET status = 'completed', progress_percent = 100,
                                       bytes_uploaded = ?, completed_at = datetime('now')
                                   WHERE id = ?""",
                                (file_size, upload_id)
                            )
                        except Exception as e:
                            logger.error(f"Failed to update upload record: {e}")

            except Exception as e:
                import traceback
                error_details = f"{str(e)}\n{traceback.format_exc()}"
                logger.error(f"[{match_id}] Processing/upload failed: {error_details}")
                activity_logger.log_error('auto_processor', str(e), 'error', match_id)
                # Don't mark as processed so it can be retried


# Global instance
auto_processor = AutoProcessor()

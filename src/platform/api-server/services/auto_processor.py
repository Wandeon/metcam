# Automatic post-recording processor
# Monitors /mnt/recordings for completed matches and uploads raw segments after a delay.

import os
import sys
import time
import json
import threading
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from sftp_uploader import SFTPUploader
from activity_logger import activity_logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "database"))
from db_manager import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoProcessor:
    """Automatically upload camera segments once they are ready"""

    def __init__(self, recordings_dir="/mnt/recordings"):
        self.recordings_dir = Path(recordings_dir)
        self.processing_lock = threading.Lock()
        self.running = False
        self.worker_thread = None

        # SFTP configuration
        self.sftp_host = os.getenv("SFTP_HOST", "nk-otok.hr")
        self.sftp_user = os.getenv("SFTP_USERNAME")
        self.sftp_pass = os.getenv("SFTP_PASSWORD")
        self.sftp_dir = os.getenv("SFTP_REMOTE_DIR", "/recordings")

        # Segment handling
        self.manifest_filename = "upload_manifest.json"
        self.segment_extension = ".mp4"
        self.upload_marker_suffix = ".uploaded"
        self.default_upload_delay_seconds = int(os.getenv("SEGMENT_UPLOAD_DELAY_SECONDS", "600"))

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
                self._check_for_ready_segments()
            except Exception as e:
                logger.error(f"Error in auto-processor: {e}")

            time.sleep(10)

    def _check_for_ready_segments(self):
        """Evaluate matches and upload segments that passed the hold-off window"""
        if not self.recordings_dir.exists():
            return

        for match_dir in sorted(p for p in self.recordings_dir.iterdir() if p.is_dir()):
            manifest_path = match_dir / self.manifest_filename
            if not manifest_path.exists():
                continue

            manifest = self._load_manifest(manifest_path)
            if not manifest:
                continue

            match_id = manifest.get("match_id") or match_dir.name

            upload_ready_at = self._determine_upload_ready_time(manifest)
            now_utc = datetime.now(timezone.utc)
            if upload_ready_at and now_utc < upload_ready_at:
                continue

            # Check for new-style whole files in manifest
            match_files = manifest.get("match_files", [])
            if match_files:
                # New system: upload whole files from /mnt/recordings root
                pending_files = []
                for filename in match_files:
                    file_path = self.recordings_dir / filename
                    if file_path.exists() and not self._marker_path(file_path).exists():
                        pending_files.append(file_path)

                if pending_files and self._segments_stable(pending_files):
                    self._upload_match_segments(match_id, pending_files)
                continue

            # Fallback to old segment-based system
            segments_dir = Path(manifest.get("segments_dir") or (match_dir / "segments"))
            if segments_dir.exists():
                pending_segments = self._collect_pending_segments(segments_dir)
                if pending_segments and self._segments_stable(pending_segments):
                    self._upload_match_segments(match_id, pending_segments)

    def _load_manifest(self, manifest_path: Path):
        try:
            with manifest_path.open("r") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to read manifest %s: %s", manifest_path, e)
            return None

    def _determine_upload_ready_time(self, manifest):
        ready_time = self._parse_iso_timestamp(manifest.get("upload_ready_at"))
        if ready_time:
            return ready_time

        stopped_time = self._parse_iso_timestamp(manifest.get("stopped_at"))
        if not stopped_time:
            return None

        delay_minutes = manifest.get("upload_delay_minutes")
        delay_seconds = self.default_upload_delay_seconds
        if delay_minutes is not None:
            try:
                delay_seconds = max(int(float(delay_minutes) * 60), 0)
            except Exception:
                pass

        return stopped_time + timedelta(seconds=delay_seconds)

    def _parse_iso_timestamp(self, value):
        if not value:
            return None
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value).astimezone(timezone.utc)
        except Exception:
            return None

    def _collect_pending_segments(self, segments_dir: Path):
        segments = sorted(p for p in segments_dir.glob(f"*{self.segment_extension}"))
        return [p for p in segments if not self._marker_path(p).exists()]

    def _segments_stable(self, segment_paths, wait_seconds=5):
        if not segment_paths:
            return False
        try:
            initial_sizes = {path: path.stat().st_size for path in segment_paths}
            time.sleep(wait_seconds)
            for path in segment_paths:
                if not path.exists():
                    return False
                size = path.stat().st_size
                if size != initial_sizes[path] or size == 0:
                    return False
            return True
        except Exception:
            return False

    def _upload_match_segments(self, match_id, pending_segments):
        with self.processing_lock:
            if not self.sftp_user or not self.sftp_pass:
                logger.warning("[%s] SFTP credentials not configured, skipping upload", match_id)
                return

            logger.info("[%s] Uploading %d segments to %s", match_id, len(pending_segments), self.sftp_host)

            uploader = SFTPUploader(self.sftp_host, self.sftp_user, self.sftp_pass, bandwidth_limit_mbps=10)
            try:
                for segment_path in pending_segments:
                    marker = self._marker_path(segment_path)
                    if marker.exists():
                        continue

                    # Verify once more before upload
                    if not self._segments_stable([segment_path], wait_seconds=1):
                        logger.debug("[%s] Segment %s not yet stable", match_id, segment_path.name)
                        continue

                    self._upload_segment(match_id, segment_path, uploader)
            finally:
                uploader.disconnect()

    def _upload_segment(self, match_id, segment_path: Path, uploader: SFTPUploader):
        try:
            file_size = segment_path.stat().st_size
            if file_size == 0:
                logger.warning("[%s] Segment %s is empty, skipping", match_id, segment_path.name)
                return

            remote_path = f"{self.sftp_dir}/{match_id}/segments/{segment_path.name}"
            upload_start_time = time.time()

            activity_logger.log_upload_started(match_id, str(segment_path), remote_path)

            try:
                upload_id = db.insert(
                    """INSERT INTO cloud_uploads
                       (match_id, file_path, file_name, destination, status, total_bytes, bandwidth_limit_mbps)
                       VALUES (?, ?, ?, ?, 'uploading', ?, 10)""",
                    (match_id, str(segment_path), segment_path.name, remote_path, file_size),
                )
            except Exception as e:
                logger.error("[%s] Failed to create upload record: %s", match_id, e)
                upload_id = None

            def upload_progress(transferred, total):
                if total <= 0:
                    return
                percent = int((transferred / total) * 100)
                if percent % 10 == 0:
                    logger.info("[%s] %s upload %d%% (%.2fGB / %.2fGB)",
                                match_id,
                                segment_path.name,
                                percent,
                                transferred / (1024 ** 3),
                                total / (1024 ** 3))

                if upload_id:
                    try:
                        db.execute(
                            """UPDATE cloud_uploads
                               SET progress_percent = ?, bytes_uploaded = ?
                               WHERE id = ?""",
                            (percent, transferred, upload_id),
                        )
                    except Exception:
                        pass

            uploader.upload_file(str(segment_path), remote_path, upload_progress)

            upload_duration = int(time.time() - upload_start_time)
            activity_logger.log_upload_completed(match_id, upload_id if upload_id else 0, file_size, upload_duration)

            if upload_id:
                try:
                    db.execute(
                        """UPDATE cloud_uploads
                           SET status = 'completed', progress_percent = 100,
                               bytes_uploaded = ?, completed_at = datetime('now')
                           WHERE id = ?""",
                        (file_size, upload_id),
                    )
                except Exception as e:
                    logger.error("[%s] Failed to finalize upload record: %s", match_id, e)

            marker = self._marker_path(segment_path)
            marker.write_text(json.dumps({
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "remote_path": remote_path,
                "size_bytes": file_size,
            }))

            logger.info("[%s] Upload complete: %s", match_id, remote_path)
        except Exception as e:
            import traceback
            error_details = f"{str(e)}\n{traceback.format_exc()}"
            logger.error("[%s] Segment upload failed: %s", match_id, error_details)
            activity_logger.log_error("auto_processor", str(e), "error", match_id)

    def _marker_path(self, segment_path: Path) -> Path:
        return segment_path.with_suffix(segment_path.suffix + self.upload_marker_suffix)


# Global instance
auto_processor = AutoProcessor()

"""
Activity logging service for FootballVision Pro
Logs all system activities to database and file
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import sys
from pathlib import Path

# Add database path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "database"))
from db_manager import db

logger = logging.getLogger(__name__)


class ActivityLogger:
    """Centralized activity logging"""

    @staticmethod
    def _log_event(
        event_type: str,
        component: str,
        severity: str = 'info',
        user_id: Optional[int] = None,
        match_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> int:
        """Internal method to log event to database"""
        try:
            details_json = json.dumps(details) if details else None
            event_id = db.insert(
                """INSERT INTO system_events
                   (event_type, component, severity, user_id, match_id, details)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (event_type, component, severity, user_id, match_id, details_json)
            )

            # Also log to file
            log_msg = f"[{event_type}] {component}: {details}"
            if severity == 'error' or severity == 'critical':
                logger.error(log_msg)
            elif severity == 'warning':
                logger.warning(log_msg)
            else:
                logger.info(log_msg)

            return event_id
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
            return -1

    @staticmethod
    def log_recording_started(match_id: str, user_id: Optional[int] = None):
        """Log recording start"""
        return ActivityLogger._log_event(
            'recording_started',
            'recording',
            'info',
            user_id,
            match_id,
            {'match_id': match_id}
        )

    @staticmethod
    def log_recording_stopped(
        match_id: str,
        duration: int,
        file_size: int,
        frames_captured: int = 0,
        frames_dropped: int = 0
    ):
        """Log recording completion"""
        return ActivityLogger._log_event(
            'recording_stopped',
            'recording',
            'info',
            None,
            match_id,
            {
                'match_id': match_id,
                'duration_seconds': duration,
                'file_size_bytes': file_size,
                'frames_captured': frames_captured,
                'frames_dropped': frames_dropped
            }
        )

    @staticmethod
    def log_processing_started(match_id: str, job_id: str, job_type: str):
        """Log processing job start"""
        return ActivityLogger._log_event(
            'processing_started',
            'processing',
            'info',
            None,
            match_id,
            {
                'match_id': match_id,
                'job_id': job_id,
                'job_type': job_type
            }
        )

    @staticmethod
    def log_processing_completed(match_id: str, job_id: str, output_file: str):
        """Log processing completion"""
        return ActivityLogger._log_event(
            'processing_completed',
            'processing',
            'info',
            None,
            match_id,
            {
                'match_id': match_id,
                'job_id': job_id,
                'output_file': output_file
            }
        )

    @staticmethod
    def log_upload_started(match_id: str, file_path: str, destination: str):
        """Log upload start"""
        return ActivityLogger._log_event(
            'upload_started',
            'upload',
            'info',
            None,
            match_id,
            {
                'match_id': match_id,
                'file_path': file_path,
                'destination': destination
            }
        )

    @staticmethod
    def log_upload_completed(match_id: str, upload_id: int, bytes_sent: int, duration: int):
        """Log upload completion"""
        return ActivityLogger._log_event(
            'upload_completed',
            'upload',
            'info',
            None,
            match_id,
            {
                'match_id': match_id,
                'upload_id': upload_id,
                'bytes_sent': bytes_sent,
                'duration_seconds': duration,
                'speed_mbps': round((bytes_sent * 8 / duration / 1_000_000), 2) if duration > 0 else 0
            }
        )

    @staticmethod
    def log_user_login(user_email: str, ip_address: str, success: bool = True):
        """Log user login attempt"""
        return ActivityLogger._log_event(
            'user_login' if success else 'user_login_failed',
            'auth',
            'info' if success else 'warning',
            None,
            None,
            {
                'email': user_email,
                'ip_address': ip_address,
                'success': success
            }
        )

    @staticmethod
    def log_error(component: str, error_message: str, severity: str = 'error', match_id: Optional[str] = None):
        """Log error"""
        return ActivityLogger._log_event(
            'error',
            component,
            severity,
            None,
            match_id,
            {
                'error': error_message
            }
        )

    @staticmethod
    def log_system_event(event_type: str, details: Dict[str, Any], severity: str = 'info'):
        """Log generic system event"""
        return ActivityLogger._log_event(
            event_type,
            'system',
            severity,
            None,
            None,
            details
        )

    @staticmethod
    def get_recent_events(limit: int = 100, event_type: Optional[str] = None) -> list:
        """Get recent activity events"""
        try:
            if event_type:
                return db.execute(
                    """SELECT * FROM system_events
                       WHERE event_type = ?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (event_type, limit)
                )
            else:
                return db.execute(
                    """SELECT * FROM system_events
                       ORDER BY timestamp DESC LIMIT ?""",
                    (limit,)
                )
        except Exception as e:
            logger.error(f"Failed to retrieve events: {e}")
            return []


# Global instance
activity_logger = ActivityLogger()

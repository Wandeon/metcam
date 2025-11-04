#!/usr/bin/env python3
"""
Nextcloud upload service for FootballVision Pro
Uploads processed archive files to Nextcloud instance via WebDAV
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class NextcloudUploadService:
    """
    Handles uploading archive files to Nextcloud
    Uses WebDAV protocol for reliable large file uploads
    """

    def __init__(
        self,
        nextcloud_url: str = "https://drive.genai.hr",
        username: Optional[str] = None,
        password: Optional[str] = None,
        base_folder: str = "FootballVision"
    ):
        """
        Initialize Nextcloud upload service

        Args:
            nextcloud_url: Nextcloud instance URL
            username: Nextcloud username (or from env: NEXTCLOUD_USERNAME)
            password: Nextcloud password (or from env: NEXTCLOUD_PASSWORD)
            base_folder: Base folder in Nextcloud for uploads
        """
        self.nextcloud_url = nextcloud_url.rstrip('/')
        self.username = username or os.getenv('NEXTCLOUD_USERNAME')
        self.password = password or os.getenv('NEXTCLOUD_PASSWORD')
        self.base_folder = base_folder

        if not self.username or not self.password:
            logger.warning("Nextcloud credentials not configured. Uploads will be skipped.")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"Nextcloud upload service initialized: {self.nextcloud_url}/{self.base_folder}")

    def _get_webdav_url(self, remote_path: str) -> str:
        """Get full WebDAV URL for a remote path"""
        # Nextcloud WebDAV endpoint: /remote.php/dav/files/USERNAME/path
        clean_path = remote_path.lstrip('/')
        return f"{self.nextcloud_url}/remote.php/dav/files/{self.username}/{clean_path}"

    def _create_folder(self, folder_path: str) -> bool:
        """Create a folder in Nextcloud (if it doesn't exist)"""
        try:
            webdav_url = self._get_webdav_url(folder_path)

            # MKCOL creates a folder
            result = subprocess.run(
                [
                    'curl',
                    '-X', 'MKCOL',
                    '-u', f'{self.username}:{self.password}',
                    '-k',  # Allow self-signed certs (remove if you have valid SSL)
                    webdav_url
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            # 201 = created, 405 = already exists (both OK)
            if result.returncode == 0:
                logger.debug(f"Folder ensured: {folder_path}")
                return True
            else:
                logger.warning(f"Could not create folder {folder_path}: {result.stderr}")
                return True  # Might already exist, continue anyway

        except Exception as e:
            logger.error(f"Failed to create folder {folder_path}: {e}")
            return False

    def upload_file(
        self,
        local_file: Path,
        remote_path: str,
        timeout: int = 7200
    ) -> bool:
        """
        Upload a file to Nextcloud via WebDAV

        Args:
            local_file: Local file path to upload
            remote_path: Remote path in Nextcloud (relative to user root)
            timeout: Upload timeout in seconds (default 2 hours)

        Returns:
            True if upload succeeded, False otherwise
        """
        if not self.enabled:
            logger.warning("Nextcloud upload disabled (no credentials)")
            return False

        if not local_file.exists():
            logger.error(f"Local file does not exist: {local_file}")
            return False

        try:
            # Ensure parent folder exists
            parent_folder = str(Path(remote_path).parent)
            if parent_folder != '.':
                self._create_folder(parent_folder)

            webdav_url = self._get_webdav_url(remote_path)
            file_size_mb = local_file.stat().st_size / (1024 * 1024)

            logger.info(f"Uploading {local_file.name} ({file_size_mb:.1f} MB) to {remote_path}")

            # Upload with curl (supports resume, progress, large files)
            result = subprocess.run(
                [
                    'curl',
                    '-X', 'PUT',
                    '-u', f'{self.username}:{self.password}',
                    '-T', str(local_file),
                    '-k',  # Allow self-signed certs
                    '--retry', '3',
                    '--retry-delay', '5',
                    '--max-time', str(timeout),
                    webdav_url
                ],
                capture_output=True,
                text=True,
                timeout=timeout + 60  # Add buffer to subprocess timeout
            )

            if result.returncode == 0:
                logger.info(f"Upload complete: {local_file.name} → {remote_path}")
                return True
            else:
                logger.error(f"Upload failed for {local_file.name}: {result.stderr[-500:]}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"Upload timeout for {local_file.name}")
            return False
        except Exception as e:
            logger.error(f"Upload error for {local_file.name}: {e}")
            return False

    def upload_match_archives(
        self,
        match_id: str,
        match_dir: Path
    ) -> Dict:
        """
        Upload all archive files for a match

        Args:
            match_id: Match identifier
            match_dir: Local match directory

        Returns:
            Dict with upload results
        """
        if not self.enabled:
            return {
                'success': False,
                'message': 'Nextcloud upload disabled (no credentials)',
                'uploaded': [],
                'failed': []
            }

        # Find archive files
        archive_files = list(match_dir.glob('cam*_archive.mp4'))

        if not archive_files:
            logger.warning(f"No archive files found for {match_id}")
            return {
                'success': False,
                'message': 'No archive files to upload',
                'uploaded': [],
                'failed': []
            }

        logger.info(f"Found {len(archive_files)} archive files to upload for {match_id}")

        uploaded = []
        failed = []

        # Create match folder in Nextcloud: FootballVision/YYYY-MM/match_id/
        try:
            # Parse date from match_id (e.g., match_20251104_001)
            import re
            date_match = re.search(r'(\d{8})', match_id)
            if date_match:
                date_str = date_match.group(1)
                year_month = f"{date_str[:4]}-{date_str[4:6]}"
            else:
                year_month = datetime.now().strftime('%Y-%m')

            remote_folder = f"{self.base_folder}/{year_month}/{match_id}"

        except Exception as e:
            logger.warning(f"Could not parse date from {match_id}, using current month: {e}")
            year_month = datetime.now().strftime('%Y-%m')
            remote_folder = f"{self.base_folder}/{year_month}/{match_id}"

        # Upload each archive file
        for archive_file in archive_files:
            remote_path = f"{remote_folder}/{archive_file.name}"

            if self.upload_file(archive_file, remote_path):
                uploaded.append(archive_file.name)
            else:
                failed.append(archive_file.name)

        success = len(failed) == 0

        return {
            'success': success,
            'message': f'Uploaded {len(uploaded)}/{len(archive_files)} files',
            'uploaded': uploaded,
            'failed': failed,
            'remote_folder': remote_folder
        }


# Global instance
_nextcloud_upload_service: Optional[NextcloudUploadService] = None


def get_nextcloud_upload_service() -> NextcloudUploadService:
    """Get or create the global NextcloudUploadService instance"""
    global _nextcloud_upload_service
    if _nextcloud_upload_service is None:
        _nextcloud_upload_service = NextcloudUploadService()
    return _nextcloud_upload_service

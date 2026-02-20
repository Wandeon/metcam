#!/usr/bin/env python3
"""
Cloudflare R2 upload service for FootballVision Pro.
Uploads processed archive files to R2 bucket via S3-compatible API.
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)

# 100 MB multipart threshold / chunk size for large uploads
_MULTIPART_THRESHOLD = 100 * 1024 * 1024
_MULTIPART_CHUNKSIZE = 100 * 1024 * 1024


class R2UploadService:
    """
    Uploads archive files to Cloudflare R2.
    Configured via environment variables:
      R2_ENDPOINT_URL   - S3-compatible endpoint
      R2_ACCESS_KEY_ID  - R2 API token access key
      R2_SECRET_ACCESS_KEY - R2 API token secret
      R2_BUCKET_NAME    - Target bucket (default: metcam-recordings)
    """

    def __init__(self) -> None:
        self.endpoint_url = os.getenv("R2_ENDPOINT_URL", "")
        self.access_key = os.getenv("R2_ACCESS_KEY_ID", "")
        self.secret_key = os.getenv("R2_SECRET_ACCESS_KEY", "")
        self.bucket = os.getenv("R2_BUCKET_NAME", "metcam-recordings")

        if not self.endpoint_url or not self.access_key or not self.secret_key:
            logger.warning("R2 credentials not configured. Uploads will be skipped.")
            self.enabled = False
            self._client = None
            return

        self.enabled = True
        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name="auto",
            config=Config(
                retries={"max_attempts": 3, "mode": "adaptive"},
                max_pool_connections=2,
            ),
        )
        logger.info(f"R2 upload service initialized: {self.bucket}")

    def _build_key(self, match_id: str, filename: str) -> str:
        """Build R2 object key: YYYY-MM/match_id/filename"""
        date_match = re.search(r"(\d{8})", match_id)
        if date_match:
            d = date_match.group(1)
            year_month = f"{d[:4]}-{d[4:6]}"
        else:
            year_month = datetime.now().strftime("%Y-%m")
        return f"{year_month}/{match_id}/{filename}"

    def upload_file(self, local_file: Path, key: str) -> bool:
        """Upload a single file to R2 with multipart for large files."""
        if not self.enabled or not self._client:
            return False

        if not local_file.exists():
            logger.error(f"Local file does not exist: {local_file}")
            return False

        file_size_mb = local_file.stat().st_size / (1024 * 1024)
        logger.info(f"Uploading {local_file.name} ({file_size_mb:.1f} MB) → r2://{self.bucket}/{key}")

        try:
            self._client.upload_file(
                str(local_file),
                self.bucket,
                key,
                Config=boto3.s3.transfer.TransferConfig(
                    multipart_threshold=_MULTIPART_THRESHOLD,
                    multipart_chunksize=_MULTIPART_CHUNKSIZE,
                    max_concurrency=2,
                ),
                ExtraArgs={"ContentType": "video/mp4"},
            )
            logger.info(f"Upload complete: {local_file.name} → {key}")
            return True
        except Exception as e:
            logger.error(f"Upload failed for {local_file.name}: {e}")
            return False

    def upload_match_archives(self, match_id: str, match_dir: Path) -> Dict:
        """Upload all archive files for a match to R2."""
        if not self.enabled:
            return {
                "success": False,
                "message": "R2 upload disabled (no credentials)",
                "uploaded": [],
                "failed": [],
            }

        archive_files = list(match_dir.glob("*_archive.mp4"))
        if not archive_files:
            logger.warning(f"No archive files found for {match_id}")
            return {
                "success": False,
                "message": "No archive files to upload",
                "uploaded": [],
                "failed": [],
            }

        logger.info(f"Found {len(archive_files)} archive files to upload for {match_id}")

        uploaded = []
        failed = []

        for archive_file in archive_files:
            key = self._build_key(match_id, archive_file.name)
            if self.upload_file(archive_file, key):
                uploaded.append(archive_file.name)
            else:
                failed.append(archive_file.name)

        remote_prefix = self._build_key(match_id, "")
        return {
            "success": len(failed) == 0,
            "message": f"Uploaded {len(uploaded)}/{len(archive_files)} files",
            "uploaded": uploaded,
            "failed": failed,
            "remote_folder": f"r2://{self.bucket}/{remote_prefix}",
        }


    def generate_presigned_url(self, key: str, expiration: int = 3600) -> Optional[str]:
        """Generate a presigned URL for direct browser access to an R2 object."""
        if not self.enabled or not self._client:
            return None
        try:
            return self._client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expiration
            )
        except Exception as e:
            logger.error(f"Presigned URL error for {key}: {e}")
            return None

    def list_match_archives(self, match_id: str) -> list:
        """List all archive files for a match in R2 with presigned URLs."""
        if not self.enabled or not self._client:
            return []

        prefix = self._build_key(match_id, "")
        try:
            response = self._client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix
            )
            files = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                if not key.endswith('.mp4'):
                    continue
                name = key.rsplit('/', 1)[-1]
                url = self.generate_presigned_url(key)
                if url:
                    files.append({
                        'name': name,
                        'key': key,
                        'size_mb': round(obj['Size'] / (1024 * 1024), 2),
                        'url': url,
                    })
            return files
        except Exception as e:
            logger.error(f"Failed to list R2 archives for {match_id}: {e}")
            return []


    def list_all_archives(self) -> list:
        """List all archive files in R2 bucket, grouped by match."""
        if not self.enabled or not self._client:
            return []

        try:
            all_objects = []
            paginator = self._client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    if not key.endswith('.mp4'):
                        continue
                    all_objects.append(obj)

            # Group by match (second path component)
            matches: dict = {}
            for obj in all_objects:
                key = obj['Key']
                parts = key.split('/')
                if len(parts) < 3:
                    continue
                year_month = parts[0]
                match_id = parts[1]
                filename = parts[2]

                if match_id not in matches:
                    matches[match_id] = {
                        'match_id': match_id,
                        'year_month': year_month,
                        'files': [],
                        'total_size_mb': 0,
                    }

                url = self.generate_presigned_url(key)
                size_mb = round(obj['Size'] / (1024 * 1024), 2)
                matches[match_id]['files'].append({
                    'name': filename,
                    'key': key,
                    'size_mb': size_mb,
                    'url': url,
                    'last_modified': obj['LastModified'].isoformat(),
                })
                matches[match_id]['total_size_mb'] = round(
                    matches[match_id]['total_size_mb'] + size_mb, 2
                )

            # Sort matches by year_month desc, then match_id desc
            result = sorted(
                matches.values(),
                key=lambda m: (m['year_month'], m['match_id']),
                reverse=True,
            )
            return result

        except Exception as e:
            logger.error(f"Failed to list all R2 archives: {e}")
            return []


_r2_upload_service: Optional[R2UploadService] = None


def get_r2_upload_service() -> R2UploadService:
    global _r2_upload_service
    if _r2_upload_service is None:
        _r2_upload_service = R2UploadService()
    return _r2_upload_service

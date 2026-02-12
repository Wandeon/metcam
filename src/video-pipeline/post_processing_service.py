#!/usr/bin/env python3
"""
Post-processing service for FootballVision Pro
Merges segments and re-encodes to archive quality using two-pass encoding
"""

import os
import subprocess
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class PostProcessingService:
    """
    Handles post-processing of recordings:
    - Merges segments into single file per camera
    - Two-pass re-encoding for optimal quality/size ratio
    - Keeps original segments intact
    """

    def __init__(self, base_recordings_dir: str = "/mnt/recordings"):
        self.base_recordings_dir = Path(base_recordings_dir)
        self.processing_lock = threading.Lock()
        self.active_jobs: Dict[str, Dict] = {}  # match_id -> job_info

    def _create_concat_file(self, segments: List[Path], output_path: Path) -> bool:
        """Create ffmpeg concat demuxer file"""
        try:
            with open(output_path, 'w') as f:
                for segment in sorted(segments):
                    # Escape single quotes in path for ffmpeg
                    safe_path = str(segment).replace("'", "'\\''")
                    f.write(f"file '{safe_path}'\n")
            return True
        except Exception as e:
            logger.error(f"Failed to create concat file: {e}")
            return False

    def _single_pass_encode(
        self,
        concat_file: Path,
        output_file: Path,
        camera_id: int,
        match_id: str
    ) -> bool:
        """
        Single-pass CRF encoding for optimal quality/size ratio

        Settings:
        - Resolution: 1920x1080 (downscale from 2880x1752)
        - CRF: 28 (good quality with aggressive compression)
        - Preset: slower (best compression, we have 12 hours!)
        - Tune: film (optimized for high quality film content)
        - Framerate: 30fps constant

        Target: 2-3 GB per camera for 100 minutes (~3-4 Mbps average bitrate)
        Expected compression: ~80% smaller than original segments
        """
        try:
            logger.info(f"Starting single-pass CRF encoding for cam{camera_id}: {match_id}")

            encode_cmd = [
                'ffmpeg',
                '-f', 'concat',
                '-safe', '0',
                '-i', str(concat_file),
                '-c:v', 'libx264',
                '-preset', 'slower',      # Best compression (slower than 'slow')
                '-crf', '28',             # Good quality with aggressive compression
                '-tune', 'film',          # Optimized for film content
                '-vf', 'scale=1920:1080', # Downscale to 1080p
                '-r', '30',               # Constant 30fps
                '-pix_fmt', 'yuv420p',    # Compatibility
                '-movflags', '+faststart', # Web optimization
                '-metadata', f'title=Match {match_id} Camera {camera_id} Archive',
                '-metadata', f'comment=CRF 28 encoded archive (optimized size)',
                '-y',                     # Overwrite output
                str(output_file)
            ]

            result = subprocess.run(
                encode_cmd,
                capture_output=True,
                text=True,
                timeout=14400  # 4 hour timeout
            )

            if result.returncode != 0:
                logger.error(f"Encoding failed for cam{camera_id}: {result.stderr[-1000:]}")
                return False

            # Verify output file was created and is valid
            if not output_file.exists():
                logger.error(f"Output file not created: {output_file}")
                return False

            output_size_mb = output_file.stat().st_size / (1024 * 1024)
            if output_size_mb == 0:
                logger.error(f"Output file is empty: {output_file}")
                return False

            logger.info(f"Encoding complete for cam{camera_id}: {output_size_mb:.1f} MB")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"Encoding timeout for cam{camera_id}")
            return False
        except Exception as e:
            logger.error(f"Encoding error for cam{camera_id}: {e}")
            return False

    def _stitch_panorama(self, cam0_file: Path, cam1_file: Path, output_file: Path, match_id: str) -> bool:
        """
        Stitch two 1920x1080 camera archives side-by-side into a 3840x1080 panorama.

        Settings:
        - CRF 26 (compensates for generation loss since inputs are already CRF 28)
        - preset medium (inputs already compressed, faster is fine)
        - 2-hour timeout (panorama is ~2x the data of one camera)

        Returns True on success, False on failure.
        """
        if not cam0_file.exists() or not cam1_file.exists():
            logger.warning(f"Cannot stitch panorama for {match_id}: missing archive(s) "
                           f"(cam0={cam0_file.exists()}, cam1={cam1_file.exists()})")
            return False

        try:
            logger.info(f"Starting panorama stitch for {match_id}: "
                        f"{cam0_file.name} + {cam1_file.name} → {output_file.name}")

            stitch_cmd = [
                'ffmpeg',
                '-i', str(cam0_file),
                '-i', str(cam1_file),
                '-filter_complex', '[0:v][1:v]hstack=inputs=2',
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '26',
                '-r', '30',
                '-pix_fmt', 'yuv420p',
                '-movflags', '+faststart',
                '-metadata', f'title=Match {match_id} Panorama Archive',
                '-metadata', f'comment=Side-by-side panorama (3840x1080), CRF 26',
                '-y',
                str(output_file)
            ]

            result = subprocess.run(
                stitch_cmd,
                capture_output=True,
                text=True,
                timeout=7200  # 2 hour timeout
            )

            if result.returncode != 0:
                logger.error(f"Panorama stitch failed for {match_id}: {result.stderr[-1000:]}")
                return False

            if not output_file.exists():
                logger.error(f"Panorama output file not created: {output_file}")
                return False

            output_size_mb = output_file.stat().st_size / (1024 * 1024)
            if output_size_mb == 0:
                logger.error(f"Panorama output file is empty: {output_file}")
                return False

            logger.info(f"Panorama stitch complete for {match_id}: {output_size_mb:.1f} MB")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"Panorama stitch timeout for {match_id}")
            return False
        except Exception as e:
            logger.error(f"Panorama stitch error for {match_id}: {e}")
            return False

    def _process_camera(
        self,
        match_id: str,
        camera_id: int,
        segments_dir: Path
    ) -> bool:
        """Process one camera's segments"""
        try:
            # Find all segments for this camera
            segments = list(segments_dir.glob(f"cam{camera_id}_*.mp4"))

            if not segments:
                logger.warning(f"No segments found for cam{camera_id} in {match_id}")
                return False

            logger.info(f"Found {len(segments)} segments for cam{camera_id} in {match_id}")

            # Create concat file
            concat_file = segments_dir / f"concat_cam{camera_id}.txt"
            if not self._create_concat_file(segments, concat_file):
                return False

            # Output file: cam0_archive.mp4
            output_file = segments_dir.parent / f"cam{camera_id}_archive.mp4"

            # Run single-pass CRF encoding
            success = self._single_pass_encode(concat_file, output_file, camera_id, match_id)

            # Cleanup concat file
            if concat_file.exists():
                concat_file.unlink()

            return success

        except Exception as e:
            logger.error(f"Failed to process cam{camera_id} for {match_id}: {e}")
            return False

    def process_recording(self, match_id: str) -> Dict:
        """
        Process recording: merge and re-encode both cameras

        Args:
            match_id: Match identifier

        Returns:
            Dict with success status and details
        """
        with self.processing_lock:
            if match_id in self.active_jobs:
                return {
                    'success': False,
                    'message': f'Processing already in progress for {match_id}'
                }

            # Mark as processing
            self.active_jobs[match_id] = {
                'start_time': datetime.now(),
                'status': 'processing'
            }

        try:
            segments_dir = self.base_recordings_dir / match_id / "segments"

            if not segments_dir.exists():
                logger.error(f"Segments directory not found: {segments_dir}")
                with self.processing_lock:
                    del self.active_jobs[match_id]
                return {
                    'success': False,
                    'message': f'Segments directory not found for {match_id}'
                }

            logger.info(f"Starting post-processing for {match_id}")

            results = {}
            for camera_id in [0, 1]:
                results[f'cam{camera_id}'] = self._process_camera(
                    match_id, camera_id, segments_dir
                )

            # Update job status
            with self.processing_lock:
                self.active_jobs[match_id]['status'] = 'complete'
                self.active_jobs[match_id]['end_time'] = datetime.now()
                duration = (self.active_jobs[match_id]['end_time'] -
                           self.active_jobs[match_id]['start_time']).total_seconds()

            success = all(results.values())

            if success:
                logger.info(f"Post-processing complete for {match_id} ({duration:.1f}s)")

                # Stitch panorama (non-blocking — failure doesn't block upload)
                cam0_archive = segments_dir.parent / "cam0_archive.mp4"
                cam1_archive = segments_dir.parent / "cam1_archive.mp4"
                panorama_archive = segments_dir.parent / "panorama_archive.mp4"

                panorama_ok = self._stitch_panorama(cam0_archive, cam1_archive, panorama_archive, match_id)
                if not panorama_ok:
                    logger.warning(f"Panorama stitch failed for {match_id}, uploading individual archives only")

                # Upload to R2 after successful processing
                upload_result = {'success': False, 'message': 'Upload not attempted'}
                try:
                    from r2_upload_service import get_r2_upload_service
                    r2_service = get_r2_upload_service()
                    if r2_service.enabled:
                        logger.info(f"Starting R2 upload for {match_id}")
                        upload_result = r2_service.upload_match_archives(
                            match_id,
                            self.base_recordings_dir / match_id
                        )
                        if upload_result['success']:
                            logger.info(f"R2 upload complete: {upload_result['message']}")
                        else:
                            logger.error(f"R2 upload failed: {upload_result['message']}")
                    else:
                        logger.info("R2 upload skipped (not configured)")
                except Exception as e:
                    logger.error(f"R2 upload error for {match_id}: {e}")
                    upload_result = {'success': False, 'message': str(e)}

                return {
                    'success': True,
                    'message': f'Processing complete for {match_id}',
                    'duration_seconds': duration,
                    'cameras_processed': [k for k, v in results.items() if v],
                    'upload': upload_result
                }
            else:
                failed = [k for k, v in results.items() if not v]
                logger.error(f"Post-processing failed for {match_id}: {failed}")
                return {
                    'success': False,
                    'message': f'Processing failed for cameras: {failed}',
                    'duration_seconds': duration
                }

        except Exception as e:
            logger.error(f"Post-processing error for {match_id}: {e}")
            with self.processing_lock:
                if match_id in self.active_jobs:
                    del self.active_jobs[match_id]
            return {
                'success': False,
                'message': f'Processing error: {str(e)}'
            }
        finally:
            # Cleanup job tracking after a delay
            with self.processing_lock:
                if match_id in self.active_jobs:
                    # Keep job info for status queries
                    self.active_jobs[match_id]['status'] = 'done'

    def process_recording_async(self, match_id: str):
        """Start processing in background thread"""
        thread = threading.Thread(
            target=self.process_recording,
            args=(match_id,),
            name=f"PostProcess-{match_id}",
            daemon=True
        )
        thread.start()
        logger.info(f"Started background post-processing for {match_id}")

    def get_status(self, match_id: str) -> Optional[Dict]:
        """Get processing status for a match"""
        with self.processing_lock:
            return self.active_jobs.get(match_id)


# Global instance
_post_processing_service: Optional[PostProcessingService] = None


def get_post_processing_service() -> PostProcessingService:
    """Get or create the global PostProcessingService instance"""
    global _post_processing_service
    if _post_processing_service is None:
        _post_processing_service = PostProcessingService()
    return _post_processing_service

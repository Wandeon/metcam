#!/usr/bin/env python3
"""
Exposure Synchronization Service

Monitors both cameras and applies synchronized exposure compensation adjustments
every 10 seconds to keep brightness consistent while avoiding flicker.

Key features:
- 10-second minimum adjustment interval
- Both cameras always use SAME exposure compensation value
- Analyzes HLS segments to measure brightness
- Gradual adjustments (max ±0.3 per update)
- Thread-safe
"""

import threading
import time
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ExposureSyncService:
    """
    Synchronizes exposure compensation across multiple cameras.

    Updates exposure compensation every 10 seconds based on brightness analysis.
    Both cameras always use the SAME value to maintain sync.
    """

    def __init__(
        self,
        gst_manager,
        adjustment_interval: float = 10.0,
        target_brightness: float = 128.0
    ):
        """
        Args:
            gst_manager: GStreamerManager instance to access pipelines
            adjustment_interval: Seconds between adjustments (default: 10)
            target_brightness: Target brightness 0-255 (default: 128)
        """
        self.gst_manager = gst_manager
        self.adjustment_interval = adjustment_interval
        self.target_brightness = target_brightness

        # Current exposure compensation (-2.0 to +2.0)
        self.current_compensation = 0.0
        self.last_adjustment = datetime.now() - timedelta(seconds=adjustment_interval)

        # Adjustment limits
        self.max_compensation = 2.0
        self.min_compensation = -2.0
        self.max_change_per_step = 0.3  # Max ±0.3 per 10 seconds

        # HLS segment locations for brightness analysis
        self.hls_base_dir = Path("/dev/shm/hls")

        # Control
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        logger.info(f"ExposureSyncService initialized (interval={adjustment_interval}s, "
                   f"target={target_brightness})")

    def start(self):
        """Start the exposure synchronization service"""
        with self.lock:
            if self.running:
                logger.warning("ExposureSyncService already running")
                return

            self.running = True
            self.thread = threading.Thread(
                target=self._adjustment_loop,
                daemon=True,
                name="ExposureSync"
            )
            self.thread.start()
            logger.info("ExposureSyncService started")

    def stop(self):
        """Stop the exposure synchronization service"""
        with self.lock:
            if not self.running:
                return

            self.running = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

        logger.info("ExposureSyncService stopped")

    def _adjustment_loop(self):
        """Main loop that checks and adjusts exposure every interval"""
        logger.info("Exposure adjustment loop starting")

        while self.running:
            try:
                # Wait for next adjustment time
                with self.lock:
                    elapsed = (datetime.now() - self.last_adjustment).total_seconds()
                    wait_time = max(0, self.adjustment_interval - elapsed)

                if wait_time > 0:
                    time.sleep(min(wait_time, 1.0))  # Check running flag regularly
                    continue

                # Perform adjustment
                logger.info(f"Attempting exposure adjustment (elapsed: {elapsed:.1f}s)")
                self._perform_adjustment()

                with self.lock:
                    self.last_adjustment = datetime.now()

            except Exception as e:
                logger.error(f"Error in exposure adjustment loop: {e}", exc_info=True)
                time.sleep(1.0)

    def _perform_adjustment(self):
        """Analyze brightness and adjust exposure compensation if needed"""
        # Check if preview is active
        preview_pipelines = [
            name for name in self.gst_manager.list_pipelines().keys()
            if name.startswith('preview_cam')
        ]

        if not preview_pipelines:
            # No preview active, skip adjustment
            logger.debug("No preview pipelines active, skipping adjustment")
            return

        logger.debug(f"Found {len(preview_pipelines)} preview pipelines active")

        # Analyze brightness from recent HLS segments
        brightness_readings = []

        for cam_id in [0, 1]:
            brightness = self._analyze_camera_brightness(cam_id)
            if brightness is not None:
                brightness_readings.append(brightness)
                logger.info(f"Camera {cam_id} brightness: {brightness:.1f}")

        if not brightness_readings:
            logger.info("No brightness readings available, skipping adjustment")
            return

        # Calculate average brightness across cameras
        avg_brightness = sum(brightness_readings) / len(brightness_readings)

        # Calculate required adjustment
        brightness_error = self.target_brightness - avg_brightness

        # Convert to exposure compensation change
        # Rough mapping: ±30 brightness units = ±0.3 compensation
        compensation_change = (brightness_error / 30.0) * 0.3

        # Clamp to max change per step
        compensation_change = max(
            -self.max_change_per_step,
            min(self.max_change_per_step, compensation_change)
        )

        # Skip if change is too small
        if abs(compensation_change) < 0.05:
            logger.debug(f"Brightness OK: {avg_brightness:.1f} (target: {self.target_brightness:.1f}), "
                        f"no adjustment needed")
            return

        # Calculate new compensation value
        new_compensation = self.current_compensation + compensation_change
        new_compensation = max(
            self.min_compensation,
            min(self.max_compensation, new_compensation)
        )

        # Apply to all cameras
        self._apply_compensation_to_cameras(new_compensation)

        logger.info(f"Exposure adjusted: brightness {avg_brightness:.1f} → "
                   f"compensation {self.current_compensation:.2f} → {new_compensation:.2f}")

        with self.lock:
            self.current_compensation = new_compensation

    def _analyze_camera_brightness(self, camera_id: int) -> Optional[float]:
        """
        Analyze brightness of most recent HLS segment for a camera.

        Args:
            camera_id: Camera ID (0 or 1)

        Returns:
            Average brightness (0-255) or None if analysis failed
        """
        try:
            # Get most recent segment (by modification time)
            segments = list(self.hls_base_dir.glob(f"cam{camera_id}_*.ts"))
            if not segments:
                return None

            latest_segment = max(segments, key=lambda p: p.stat().st_mtime)

            # Extract a downscaled grayscale frame and calculate average pixel value
            # This is much more reliable than signalstats which doesn't log properly
            cmd = [
                'ffmpeg', '-i', str(latest_segment),
                '-vf', 'scale=100:100,format=gray',  # Small grayscale frame
                '-vframes', '1',
                '-f', 'rawvideo',  # Raw pixel data
                '-'
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=2.0
            )

            if result.returncode != 0 or not result.stdout:
                return None

            # Calculate average brightness from raw pixel data
            pixels = result.stdout
            if pixels:
                avg_brightness = sum(pixels) / len(pixels)
                return avg_brightness

            return None

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout analyzing brightness for camera {camera_id}")
            return None
        except Exception as e:
            logger.debug(f"Could not analyze camera {camera_id} brightness: {e}")
            return None

    def _apply_compensation_to_cameras(self, compensation: float):
        """
        Apply exposure compensation to all active camera pipelines.

        Args:
            compensation: Exposure compensation value (-2.0 to +2.0)
        """
        applied_count = 0

        for pipeline_name in self.gst_manager.list_pipelines().keys():
            # Apply to both recording and preview pipelines
            if pipeline_name.startswith(('recording_cam', 'preview_cam')):
                if self._set_pipeline_exposure(pipeline_name, compensation):
                    applied_count += 1

        if applied_count > 0:
            logger.debug(f"Applied compensation {compensation:.2f} to {applied_count} pipelines")

    def _set_pipeline_exposure(self, pipeline_name: str, compensation: float) -> bool:
        """
        Set exposure compensation on a specific pipeline.

        Args:
            pipeline_name: Name of the pipeline
            compensation: Exposure compensation value

        Returns:
            True if successful
        """
        try:
            pipeline_info = self.gst_manager.get_pipeline_status(pipeline_name)
            if not pipeline_info:
                return False

            # Get the pipeline object
            with self.gst_manager.pipelines_lock:
                if pipeline_name not in self.gst_manager.pipelines:
                    return False

                pipeline = self.gst_manager.pipelines[pipeline_name]['pipeline']

                # Find the nvarguscamerasrc element
                src = pipeline.get_by_name('src')
                if not src:
                    logger.warning(f"No 'src' element in pipeline {pipeline_name}")
                    return False

                # Set exposurecompensation property
                src.set_property('exposurecompensation', float(compensation))

            return True

        except Exception as e:
            logger.error(f"Failed to set exposure on {pipeline_name}: {e}")
            return False

    def get_status(self) -> Dict:
        """Get current service status"""
        with self.lock:
            elapsed = (datetime.now() - self.last_adjustment).total_seconds()

            return {
                'running': self.running,
                'current_compensation': self.current_compensation,
                'target_brightness': self.target_brightness,
                'adjustment_interval': self.adjustment_interval,
                'seconds_since_last_adjustment': elapsed,
                'next_adjustment_in': max(0, self.adjustment_interval - elapsed)
            }


# Global singleton instance
_exposure_sync_service: Optional[ExposureSyncService] = None
_service_lock = threading.Lock()


def get_exposure_sync_service(gst_manager=None) -> Optional[ExposureSyncService]:
    """Get or create the global ExposureSyncService instance"""
    global _exposure_sync_service

    if _exposure_sync_service is None and gst_manager is not None:
        with _service_lock:
            if _exposure_sync_service is None:
                _exposure_sync_service = ExposureSyncService(gst_manager)

    return _exposure_sync_service

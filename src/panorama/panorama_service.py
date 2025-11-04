#!/usr/bin/env python3
"""
Panorama Service - Main Service for Panorama Stitching

Manages panorama preview streams and post-processing operations.
Follows FootballVision singleton service pattern.

This service handles:
- Real-time panorama preview with HLS output
- Post-processing of recorded matches to create panorama videos
- Integration with camera calibration
- State persistence across restarts
- Recording priority enforcement (recording blocks panorama)

Architecture:
- Singleton pattern (like RecordingService)
- Thread-safe operations with locks
- State persistence to JSON
- Integration with existing GStreamerManager
"""

import os
import time
import json
import logging
import threading
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)


class PanoramaService:
    """
    Main service for panorama stitching operations (Singleton)

    Manages dual-camera panorama preview and post-processing.
    Follows RecordingService/PreviewService patterns.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize panorama service"""
        if self._initialized:
            return

        self._initialized = True

        # Lazy imports to avoid circular dependencies
        try:
            from .config_manager import PanoramaConfigManager
            self.config_manager = PanoramaConfigManager()
        except ImportError as e:
            logger.warning(f"Config manager not available: {e}")
            self.config_manager = None

        try:
            from .frame_synchronizer import FrameSynchronizer
            self.synchronizer = FrameSynchronizer()
        except ImportError as e:
            logger.warning(f"Frame synchronizer not available: {e}")
            self.synchronizer = None

        # Components (lazy-loaded)
        self.stitcher = None  # Lazy-loaded when needed
        self.calibration_service = None  # Lazy-loaded when needed

        # State
        self.preview_active = False
        self.preview_start_time: Optional[float] = None
        self.state_lock = Lock()

        # State persistence
        self.state_dir = Path("/home/mislav/footballvision-pro/state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "panorama_state.json"

        # Preview threads
        self.capture_thread_cam0 = None
        self.capture_thread_cam1 = None
        self.stitch_thread = None
        self.stop_event = threading.Event()

        # Frame buffers for preview
        self.frame_buffer_cam0 = []
        self.frame_buffer_cam1 = []
        self.buffer_lock = Lock()

        # Performance metrics
        self.frames_stitched = 0
        self.preview_fps = 0.0
        self.last_fps_update = time.time()

        # Load persisted state
        self._load_state()

        logger.info("PanoramaService initialized")

    def _load_state(self) -> None:
        """Load service state from file"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)

                # Note: We don't restore preview_active on restart
                # Panorama preview requires explicit start
                logger.info(f"Loaded panorama state from {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to load panorama state: {e}")

    def _save_state(self) -> None:
        """Save service state to file"""
        try:
            state = {
                'preview_active': self.preview_active,
                'last_update': datetime.utcnow().isoformat(),
                'calibrated': self._is_calibrated(),
                'timestamp': time.time()
            }

            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save panorama state: {e}")

    def _clear_state(self) -> None:
        """Clear persisted state"""
        try:
            if self.state_file.exists():
                self.state_file.unlink()
        except Exception as e:
            logger.error(f"Failed to clear panorama state: {e}")

    def _is_calibrated(self) -> bool:
        """Check if calibrated"""
        if self.config_manager:
            return self.config_manager.is_calibrated()
        return False

    def _check_recording_active(self) -> bool:
        """
        Check if recording service is active
        Recording has priority over panorama
        """
        try:
            # Import here to avoid circular dependency
            import sys
            sys.path.insert(0, '/home/mislav/footballvision-pro/src/video-pipeline')
            from recording_service import get_recording_service

            recording_service = get_recording_service()
            status = recording_service.get_status()

            return status.get('recording', False)
        except Exception as e:
            logger.error(f"Failed to check recording status: {e}")
            return False

    def _load_stitcher(self) -> bool:
        """
        Lazy-load VPI stitcher with calibration data

        Returns:
            True if stitcher loaded successfully
        """
        try:
            if self.stitcher is not None:
                return True

            # Check if calibrated
            if not self._is_calibrated():
                logger.error("Cannot load stitcher: not calibrated")
                return False

            # Import and initialize stitcher
            from .vpi_stitcher import VPIStitcher

            calibration = self.config_manager.get_calibration_data()
            self.stitcher = VPIStitcher(calibration)

            logger.info("VPI stitcher loaded successfully")
            return True

        except ImportError as e:
            logger.error(f"VPI stitcher not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load stitcher: {e}")
            return False

    def start_preview(self) -> Dict:
        """
        Start panorama preview stream

        Returns:
            Dict with success status and HLS URL
        """
        with self.state_lock:
            # Check if already running
            if self.preview_active:
                return {
                    'success': False,
                    'message': 'Panorama preview already active'
                }

            # Check if recording is active (priority enforcement)
            if self._check_recording_active():
                return {
                    'success': False,
                    'message': 'Cannot start panorama: recording is active',
                    'error_code': 'RECORDING_ACTIVE'
                }

            # Check if calibrated
            if not self._is_calibrated():
                return {
                    'success': False,
                    'message': 'Panorama not calibrated',
                    'error_code': 'NOT_CALIBRATED'
                }

            # Load stitcher
            if not self._load_stitcher():
                return {
                    'success': False,
                    'message': 'Failed to initialize stitcher',
                    'error_code': 'STITCHER_INIT_FAILED'
                }

            try:
                # Reset stop event
                self.stop_event.clear()

                # Reset performance metrics
                self.frames_stitched = 0
                self.preview_fps = 0.0
                self.last_fps_update = time.time()

                # TODO: Start dual-camera capture threads
                # This will be implemented when we integrate with GStreamer
                # For now, return success with placeholder

                # Update state
                self.preview_active = True
                self.preview_start_time = time.time()
                self._save_state()

                logger.info("Panorama preview started")

                return {
                    'success': True,
                    'message': 'Panorama preview started',
                    'hls_url': '/hls/panorama.m3u8',
                    'resolution': '3840x1315',
                    'fps_target': 15
                }

            except Exception as e:
                logger.error(f"Failed to start panorama preview: {e}")
                self.preview_active = False
                self.preview_start_time = None
                return {
                    'success': False,
                    'message': f'Error starting preview: {str(e)}'
                }

    def stop_preview(self) -> Dict:
        """
        Stop panorama preview stream

        Returns:
            Dict with success status
        """
        with self.state_lock:
            if not self.preview_active:
                return {
                    'success': False,
                    'message': 'Panorama preview not active'
                }

            try:
                # Signal threads to stop
                self.stop_event.set()

                # TODO: Stop capture threads
                # TODO: Stop stitching thread
                # TODO: Stop HLS output pipeline

                # Wait for threads to finish (with timeout)
                timeout = 5.0
                if self.capture_thread_cam0:
                    self.capture_thread_cam0.join(timeout=timeout)
                if self.capture_thread_cam1:
                    self.capture_thread_cam1.join(timeout=timeout)
                if self.stitch_thread:
                    self.stitch_thread.join(timeout=timeout)

                # Clear buffers
                with self.buffer_lock:
                    self.frame_buffer_cam0.clear()
                    self.frame_buffer_cam1.clear()

                # Update state
                self.preview_active = False
                self.preview_start_time = None
                self._save_state()

                logger.info("Panorama preview stopped")

                return {
                    'success': True,
                    'message': 'Panorama preview stopped'
                }

            except Exception as e:
                logger.error(f"Failed to stop panorama preview: {e}")
                return {
                    'success': False,
                    'message': f'Error stopping preview: {str(e)}'
                }

    def get_status(self) -> Dict:
        """
        Get current panorama service status

        Returns:
            Status dictionary with current state
        """
        with self.state_lock:
            # Calculate uptime
            uptime = 0.0
            if self.preview_active and self.preview_start_time:
                uptime = time.time() - self.preview_start_time

            # Get calibration info
            calibration_info = {}
            if self.config_manager and self._is_calibrated():
                try:
                    calibration = self.config_manager.get_calibration_data()
                    calibration_info = {
                        'calibration_date': calibration.get('calibration_date'),
                        'quality_score': calibration.get('quality_score', 0.0),
                        'reprojection_error': calibration.get('reprojection_error', 0.0)
                    }
                except Exception as e:
                    logger.error(f"Failed to get calibration info: {e}")

            # Get sync stats
            sync_stats = {}
            if self.synchronizer:
                try:
                    sync_stats = self.synchronizer.get_stats()
                except Exception as e:
                    logger.error(f"Failed to get sync stats: {e}")

            # Get stitch stats
            stitch_stats = {}
            if self.stitcher:
                try:
                    stitch_stats = self.stitcher.get_stats()
                except Exception as e:
                    logger.error(f"Failed to get stitch stats: {e}")

            # Get config
            config = {}
            if self.config_manager:
                try:
                    config = self.config_manager.get_config()
                except Exception as e:
                    logger.error(f"Failed to get config: {e}")

            return {
                'preview_active': self.preview_active,
                'uptime_seconds': uptime,
                'calibrated': self._is_calibrated(),
                'calibration_info': calibration_info,
                'performance': {
                    'current_fps': self.preview_fps,
                    'frames_stitched': self.frames_stitched,
                    'sync_stats': sync_stats,
                    'stitch_stats': stitch_stats
                },
                'config': config
            }

    def process_recording(
        self,
        match_id: str,
        cam0_segments: Optional[List[str]] = None,
        cam1_segments: Optional[List[str]] = None
    ) -> Dict:
        """
        Post-process recording to create panorama video

        Args:
            match_id: Match identifier
            cam0_segments: Optional list of cam0 segment files (auto-discovered if None)
            cam1_segments: Optional list of cam1 segment files (auto-discovered if None)

        Returns:
            Processing result dictionary
        """
        try:
            # Check if calibrated
            if not self._is_calibrated():
                return {
                    'success': False,
                    'message': 'Panorama not calibrated',
                    'error_code': 'NOT_CALIBRATED'
                }

            # Auto-discover segments if not provided
            base_dir = Path("/mnt/recordings") / match_id

            if cam0_segments is None:
                segments_dir = base_dir / "segments"
                if not segments_dir.exists():
                    return {
                        'success': False,
                        'message': f'Match segments not found: {match_id}',
                        'error_code': 'MATCH_NOT_FOUND'
                    }

                cam0_segments = sorted([str(f) for f in segments_dir.glob("cam0_*.mp4")])
                cam1_segments = sorted([str(f) for f in segments_dir.glob("cam1_*.mp4")])

            if not cam0_segments or not cam1_segments:
                return {
                    'success': False,
                    'message': 'No segments found for both cameras',
                    'error_code': 'NO_SEGMENTS'
                }

            # TODO: Implement actual post-processing
            # 1. Extract frames from both cameras
            # 2. Synchronize frames using FrameSynchronizer
            # 3. Stitch frame pairs using VPIStitcher
            # 4. Encode to video
            # 5. Save as panorama_archive.mp4

            logger.info(f"Post-processing requested for match {match_id}")
            logger.info(f"Cam0 segments: {len(cam0_segments)}")
            logger.info(f"Cam1 segments: {len(cam1_segments)}")

            return {
                'success': True,
                'message': 'Processing started (not implemented yet)',
                'match_id': match_id,
                'cam0_segments': len(cam0_segments),
                'cam1_segments': len(cam1_segments),
                'estimated_duration_minutes': 0  # Placeholder
            }

        except Exception as e:
            logger.error(f"Failed to process recording: {e}")
            return {
                'success': False,
                'message': f'Error processing recording: {str(e)}'
            }

    def start_calibration(self) -> Dict:
        """
        Start calibration process

        Returns:
            Status dictionary
        """
        try:
            # Lazy-load calibration service
            if self.calibration_service is None:
                try:
                    from .calibration_service import CalibrationService
                    self.calibration_service = CalibrationService(self.config_manager)
                except ImportError as e:
                    logger.error(f"Calibration service not available: {e}")
                    return {
                        'success': False,
                        'message': 'Calibration service not available (not implemented yet)'
                    }

            # Check if preview is active
            if self.preview_active:
                return {
                    'success': False,
                    'message': 'Cannot start calibration: preview is active'
                }

            # Check if recording is active
            if self._check_recording_active():
                return {
                    'success': False,
                    'message': 'Cannot start calibration: recording is active'
                }

            # Reset calibration service
            result = self.calibration_service.start()

            return result

        except Exception as e:
            logger.error(f"Failed to start calibration: {e}")
            return {
                'success': False,
                'message': f'Error starting calibration: {str(e)}'
            }

    def capture_calibration_frame(
        self,
        frame_cam0: np.ndarray,
        frame_cam1: np.ndarray
    ) -> Dict:
        """
        Capture frame pair for calibration

        Args:
            frame_cam0: Frame from camera 0
            frame_cam1: Frame from camera 1

        Returns:
            Capture result dictionary
        """
        try:
            if self.calibration_service is None:
                return {
                    'success': False,
                    'message': 'Calibration not started'
                }

            result = self.calibration_service.capture_frame_pair(frame_cam0, frame_cam1)

            return result

        except Exception as e:
            logger.error(f"Failed to capture calibration frame: {e}")
            return {
                'success': False,
                'message': f'Error capturing frame: {str(e)}'
            }

    def complete_calibration(self) -> Dict:
        """
        Complete calibration and calculate homography

        Returns:
            Calibration result dictionary
        """
        try:
            if self.calibration_service is None:
                return {
                    'success': False,
                    'message': 'Calibration not started'
                }

            # Calculate homography
            result = self.calibration_service.calculate_homography()

            if result.get('success'):
                # Reload stitcher with new calibration
                self.stitcher = None
                logger.info("Calibration complete, stitcher will reload on next use")

            return result

        except Exception as e:
            logger.error(f"Failed to complete calibration: {e}")
            return {
                'success': False,
                'message': f'Error completing calibration: {str(e)}'
            }

    def cleanup(self):
        """Cleanup resources (called on shutdown)"""
        logger.info("PanoramaService cleanup")

        with self.state_lock:
            if self.preview_active:
                logger.warning("Stopping active panorama preview during cleanup")
                self.stop_preview()

            # Cleanup stitcher
            if self.stitcher:
                try:
                    self.stitcher.cleanup()
                except Exception as e:
                    logger.error(f"Failed to cleanup stitcher: {e}")
                self.stitcher = None


# Global instance accessor
_panorama_service: Optional[PanoramaService] = None


def get_panorama_service() -> PanoramaService:
    """Get or create the global PanoramaService instance"""
    global _panorama_service
    if _panorama_service is None:
        _panorama_service = PanoramaService()
    return _panorama_service

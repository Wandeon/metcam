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
import sys
import time
import json
import logging
import threading
import uuid
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable
from datetime import datetime
from threading import Lock

# Add video-pipeline to path for GStreamer imports
sys.path.insert(0, '/home/mislav/footballvision-pro/src/video-pipeline')
from gstreamer_manager import GStreamerManager
from pipeline_builders import build_panorama_capture_pipeline, build_panorama_output_webrtc_pipeline

# Import GStreamer and frame utilities
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Import panorama utilities
from gst_frame_utils import gst_sample_to_numpy, numpy_to_gst_buffer

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
            from config_manager import PanoramaConfigManager
            self.config_manager = PanoramaConfigManager()
        except ImportError as e:
            logger.warning(f"Config manager not available: {e}")
            self.config_manager = None

        try:
            from frame_synchronizer import FrameSynchronizer
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
        self.preview_transport = os.getenv("PANORAMA_PREVIEW_TRANSPORT_MODE", os.getenv("PREVIEW_TRANSPORT_MODE", "hls")).strip().lower()
        if self.preview_transport not in {"hls", "webrtc", "dual"}:
            self.preview_transport = "hls"
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

        # GStreamer components
        self.gst_manager = GStreamerManager()
        self.capture_pipelines = {}  # {camera_id: pipeline_name}
        self.output_pipeline = None
        self.webrtc_session: Optional[Dict[str, Any]] = None
        self.webrtc_emitter: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self.webrtc_callbacks_registered = False
        self.stun_server = os.getenv("WEBRTC_STUN_SERVER", "stun://stun.l.google.com:19302").strip()
        self.turn_server = os.getenv("WEBRTC_TURN_SERVER", "").strip() or None

        # Post-processing state tracking
        self.processing_state = {}  # {match_id: {processing, progress, completed, error, eta_seconds}}

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
            from vpi_stitcher import VPIStitcher

            # Get homography matrix and output dimensions
            homography = self.config_manager.get_homography()
            if homography is None:
                logger.error("Failed to get homography matrix")
                return False

            output_config = self.config_manager.config['output']
            performance_config = self.config_manager.config['performance']
            calibration_config = self.config_manager.config['calibration']

            # Create stitcher with calibration
            self.stitcher = VPIStitcher(
                output_width=output_config['width'],
                output_height=output_config['height'],
                use_vic=performance_config.get('use_vic_backend', True),
                use_cuda=performance_config.get('use_cuda_backend', True),
                homography=homography,
                blend_width=calibration_config.get('blend_width', 150)
            )

            logger.info("VPI stitcher loaded successfully")
            return True

        except ImportError as e:
            logger.error(f"VPI stitcher not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load stitcher: {e}", exc_info=True)
            return False

    def _resolve_transport(self, requested_transport: Optional[str]) -> str:
        requested = (requested_transport or "").strip().lower()
        if requested in {"hls", "webrtc"}:
            return requested
        if self.preview_transport == "webrtc":
            return "webrtc"
        # dual defaults to hls for conservative rollout unless caller opts in.
        return "hls"

    def _ice_servers(self) -> List[Dict[str, Any]]:
        servers: List[Dict[str, Any]] = []
        if self.stun_server:
            servers.append({"urls": [self.stun_server]})
        if self.turn_server:
            servers.append({"urls": [self.turn_server]})
        return servers

    def start_preview(self, transport: Optional[str] = None) -> Dict:
        """
        Start panorama preview stream

        Returns:
            Dict with success status and HLS URL
        """
        with self.state_lock:
            resolved_transport = self._resolve_transport(transport)

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

                # 1. Create capture pipelines for both cameras
                logger.info("Creating capture pipelines for both cameras")
                for cam_id in [0, 1]:
                    pipeline_name = f'panorama_capture_cam{cam_id}'
                    pipeline_str = build_panorama_capture_pipeline(cam_id)

                    # Create pipeline
                    created = self.gst_manager.create_pipeline(
                        name=pipeline_name,
                        pipeline_description=pipeline_str,
                        on_eos=self._on_capture_eos,
                        on_error=self._on_capture_error,
                        metadata={'camera_id': cam_id}
                    )

                    if not created:
                        raise Exception(f"Failed to create capture pipeline for cam{cam_id}")

                    # Connect appsink callback
                    with self.gst_manager.pipelines_lock:
                        pipeline = self.gst_manager.pipelines[pipeline_name]['pipeline']
                        appsink = pipeline.get_by_name('appsink')
                        if appsink:
                            appsink.connect('new-sample', self._on_new_frame, cam_id)
                            logger.info(f"Connected appsink callback for cam{cam_id}")
                        else:
                            raise Exception(f"Failed to find appsink in pipeline for cam{cam_id}")

                    # Start pipeline
                    if not self.gst_manager.start_pipeline(pipeline_name):
                        raise Exception(f"Failed to start capture pipeline for cam{cam_id}")

                    self.capture_pipelines[cam_id] = pipeline_name
                    logger.info(f"Started capture pipeline for cam{cam_id}")

                # 2. Create output pipeline
                logger.info("Creating output pipeline for stitched panorama")
                output_pipeline_str = self._build_output_pipeline(resolved_transport)
                created = self.gst_manager.create_pipeline(
                    name='panorama_output',
                    pipeline_description=output_pipeline_str,
                    on_eos=self._on_output_eos,
                    on_error=self._on_output_error,
                    metadata={
                        "transport": resolved_transport,
                    }
                )

                if not created:
                    raise Exception("Failed to create output pipeline")

                # GStreamer 1.20 bug: turn-server property validates but doesn't
                # register with the ICE agent.  Use add-turn-server signal.
                if resolved_transport == "webrtc" and self.turn_server:
                    webrtcbin = self._get_webrtcbin()
                    if webrtcbin:
                        webrtcbin.emit("add-turn-server", self.turn_server)

                if not self.gst_manager.start_pipeline('panorama_output'):
                    raise Exception("Failed to start output pipeline")

                self.output_pipeline = 'panorama_output'
                logger.info("Started output pipeline")

                # 3. Start stitching thread
                logger.info("Starting stitching thread")
                self.stop_event.clear()
                self.stitch_thread = threading.Thread(
                    target=self._stitch_loop,
                    daemon=True,
                    name="PanoramaStitch"
                )
                self.stitch_thread.start()

                # 4. Update state
                self.preview_active = True
                self.preview_start_time = time.time()
                self.preview_transport = resolved_transport
                self._save_state()

                logger.info("Panorama preview started successfully")

                return {
                    'success': True,
                    'message': 'Panorama preview started',
                    'transport': resolved_transport,
                    'stream_kind': 'panorama',
                    'hls_url': '/hls/panorama.m3u8',
                    'ice_servers': self._ice_servers(),
                    'resolution': f"{self.config_manager.config['output']['width']}x{self.config_manager.config['output']['height']}",
                    'fps_target': self.config_manager.config['performance']['preview_fps_target']
                }

            except Exception as e:
                logger.error(f"Failed to start panorama preview: {e}", exc_info=True)
                self._cleanup_preview()
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
                logger.info("Stopping panorama preview")

                # 1. Signal stitching thread to stop
                self.stop_event.set()

                # 2. Wait for stitching thread to finish
                if self.stitch_thread and self.stitch_thread.is_alive():
                    logger.info("Waiting for stitching thread to stop")
                    self.stitch_thread.join(timeout=5.0)
                    if self.stitch_thread.is_alive():
                        logger.warning("Stitching thread did not stop cleanly")

                # 3. Stop and remove capture pipelines
                for cam_id, pipeline_name in list(self.capture_pipelines.items()):
                    logger.info(f"Stopping capture pipeline for cam{cam_id}")
                    try:
                        self.gst_manager.stop_pipeline(pipeline_name, wait_for_eos=True, timeout=3.0)
                        self.gst_manager.remove_pipeline(pipeline_name)
                        logger.info(f"Removed capture pipeline for cam{cam_id}")
                    except Exception as e:
                        logger.error(f"Error stopping capture pipeline cam{cam_id}: {e}")

                self.capture_pipelines.clear()

                # 4. Stop and remove output pipeline
                if self.output_pipeline:
                    logger.info("Stopping output pipeline")
                    try:
                        self.gst_manager.stop_pipeline(self.output_pipeline, wait_for_eos=True, timeout=3.0)
                        self.gst_manager.remove_pipeline(self.output_pipeline)
                        logger.info("Removed output pipeline")
                    except Exception as e:
                        logger.error(f"Error stopping output pipeline: {e}")
                    self.output_pipeline = None

                # 5. Clear frame buffers
                if self.synchronizer:
                    self.synchronizer.cam0_buffer.clear()
                    self.synchronizer.cam1_buffer.clear()

                # 6. Update state
                self.preview_active = False
                self.preview_start_time = None
                self.webrtc_session = None
                self.webrtc_callbacks_registered = False
                self._save_state()

                logger.info("Panorama preview stopped successfully")

                return {
                    'success': True,
                    'message': 'Panorama preview stopped'
                }

            except Exception as e:
                logger.error(f"Failed to stop panorama preview: {e}", exc_info=True)
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

            # Flatten performance metrics for frontend compatibility
            performance = {
                'current_fps': self.preview_fps,
                'frames_stitched': self.frames_stitched,
                'avg_sync_drift_ms': sync_stats.get('avg_drift_ms', 0.0),
                'dropped_frames': sync_stats.get('dropped_frames', 0),
                'sync_stats': sync_stats,
                'stitch_stats': stitch_stats
            }

            return {
                'preview_active': self.preview_active,
                'transport': self.preview_transport if self.preview_active else self._resolve_transport(None),
                'stream_kind': 'panorama',
                'hls_url': '/hls/panorama.m3u8',
                'ice_servers': self._ice_servers(),
                'uptime_seconds': uptime,
                'calibrated': self._is_calibrated(),
                'calibration_info': calibration_info,
                'performance': performance,
                'config': config
            }

    def get_calibration_progress(self) -> Dict:
        """
        Get calibration progress information

        Returns:
            Dictionary with calibration progress details
        """
        try:
            if self.calibration_service:
                return self.calibration_service.get_calibration_progress()
            else:
                return {
                    'is_calibrating': False,
                    'frames_captured': 0,
                    'frames_needed': 10,
                    'frames_target': 15,
                    'ready_to_calculate': False,
                    'progress_percent': 0
                }
        except Exception as e:
            logger.error(f"Error getting calibration progress: {e}")
            return {
                'is_calibrating': False,
                'frames_captured': 0,
                'frames_needed': 10,
                'frames_target': 15,
                'ready_to_calculate': False,
                'progress_percent': 0
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

            # Load stitcher if not loaded
            if not self._load_stitcher():
                return {
                    'success': False,
                    'message': 'Failed to initialize stitcher',
                    'error_code': 'STITCHER_INIT_FAILED'
                }

            logger.info(f"Starting post-processing for match {match_id}")
            logger.info(f"Cam0 segments: {len(cam0_segments)}")
            logger.info(f"Cam1 segments: {len(cam1_segments)}")

            # Start post-processing in background thread
            processing_thread = threading.Thread(
                target=self._process_recording_thread,
                args=(match_id, cam0_segments, cam1_segments),
                daemon=False,
                name=f"PanoramaProcess-{match_id}"
            )
            processing_thread.start()

            # Estimate duration (rough: 1 minute per 5 minutes of footage)
            total_segments = len(cam0_segments) + len(cam1_segments)
            estimated_minutes = max(1, total_segments // 10)

            return {
                'success': True,
                'message': 'Processing started',
                'match_id': match_id,
                'cam0_segments': len(cam0_segments),
                'cam1_segments': len(cam1_segments),
                'estimated_duration_minutes': estimated_minutes
            }

        except Exception as e:
            logger.error(f"Failed to process recording: {e}")
            return {
                'success': False,
                'message': f'Error processing recording: {str(e)}'
            }

    def get_processing_status(self, match_id: str) -> Dict:
        """
        Get processing status for a match

        Args:
            match_id: Match identifier

        Returns:
            Status dictionary with progress information
        """
        if match_id not in self.processing_state:
            return {
                'processing': False,
                'progress': 0,
                'eta_seconds': None,
                'completed': False,
                'error': None,
                'message': f'No processing found for match {match_id}'
            }

        state = self.processing_state[match_id]
        return {
            'processing': state.get('processing', False),
            'progress': state.get('progress', 0),
            'eta_seconds': state.get('eta_seconds'),
            'completed': state.get('completed', False),
            'error': state.get('error'),
            'total_frames': state.get('total_frames', 0),
            'message': 'Processing in progress' if state.get('processing') else 'Processing completed'
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
                    from calibration_service import CalibrationService
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

            # Start calibration service
            success = self.calibration_service.start()

            if success:
                return {
                    'success': True,
                    'message': 'Calibration started successfully'
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to start calibration'
                }

        except Exception as e:
            logger.error(f"Failed to start calibration: {e}")
            return {
                'success': False,
                'message': f'Error starting calibration: {str(e)}'
            }

    def _capture_single_frame(self, camera_id: int) -> Optional[np.ndarray]:
        """
        Capture a single frame from a camera using GStreamer

        Creates a one-shot GStreamer pipeline to capture a single frame from
        the specified camera. To reduce calibration drift from startup exposure
        swings, it captures a short warmup burst and keeps the final frame.

        Args:
            camera_id: Camera sensor ID (0 or 1)

        Returns:
            BGR frame as NumPy array (H, W, 3) uint8, or None if failed

        Example:
            >>> frame = self._capture_single_frame(0)
            >>> if frame is not None:
            ...     print(f"Captured frame: {frame.shape}")
        """
        try:
            logger.info(f"Capturing single frame from camera {camera_id}...")
            exposure_settle_frames = 60
            total_frames = exposure_settle_frames + 1

            # Build one-shot GStreamer pipeline
            # Capture a short warmup burst and keep the last frame for better
            # auto-exposure stability during calibration.
            pipeline_str = (
                f"nvarguscamerasrc sensor-id={camera_id} num-buffers={total_frames} ! "
                f"video/x-raw(memory:NVMM),width=3840,height=2160,framerate=30/1 ! "
                f"nvvidconv ! "
                f"video/x-raw,format=BGRx ! "
                f"videoconvert ! "
                f"video/x-raw,format=BGR ! "
                f"appsink name=sink emit-signals=true max-buffers=1 drop=true"
            )

            logger.debug(f"Creating pipeline: {pipeline_str}")

            # Create and configure pipeline
            pipeline = Gst.parse_launch(pipeline_str)
            appsink = pipeline.get_by_name('sink')

            if appsink is None:
                logger.error("Failed to get appsink from pipeline")
                return None

            # Keep replacing with newest sample so we return the final frame.
            captured_frame = None
            frame_count = 0

            def on_new_sample(sink):
                """Callback when new frame is available"""
                nonlocal captured_frame, frame_count
                try:
                    sample = sink.emit('pull-sample')
                    if sample:
                        frame, timestamp_ns, metadata = gst_sample_to_numpy(sample)
                        if frame is not None:
                            frame_count += 1
                            captured_frame = frame
                            if frame_count == total_frames:
                                logger.debug(
                                    f"Final warm frame captured: {frame.shape}, timestamp={timestamp_ns}"
                                )
                        else:
                            logger.error("Failed to convert sample to numpy")
                    else:
                        logger.error("Failed to pull sample from appsink")
                except Exception as e:
                    logger.error(f"Error in on_new_sample callback: {e}", exc_info=True)
                return Gst.FlowReturn.OK

            # Connect callback
            appsink.connect('new-sample', on_new_sample)

            # Start pipeline
            logger.debug("Starting pipeline...")
            ret = pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                logger.error("Failed to set pipeline to PLAYING state")
                pipeline.set_state(Gst.State.NULL)
                return None

            # Wait for EOS (after warmup burst) or error.
            bus = pipeline.get_bus()
            timeout = 10 * Gst.SECOND
            msg = bus.timed_pop_filtered(
                timeout,
                Gst.MessageType.EOS | Gst.MessageType.ERROR
            )

            # Check what message we got
            if msg is None:
                logger.error("Timeout waiting for frame capture")
                captured_frame = None
            elif msg.type == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                logger.error(f"GStreamer error: {err.message}, debug: {debug}")
                captured_frame = None
            elif msg.type == Gst.MessageType.EOS:
                logger.debug("Frame capture completed successfully (EOS received)")

            # Cleanup
            pipeline.set_state(Gst.State.NULL)

            if captured_frame is not None:
                logger.info(f"Successfully captured frame from camera {camera_id}: shape={captured_frame.shape}")
            else:
                logger.error(f"Failed to capture frame from camera {camera_id}")

            return captured_frame

        except Exception as e:
            logger.error(f"Failed to capture frame from camera {camera_id}: {e}", exc_info=True)
            return None

    def capture_calibration_frame(self) -> Dict:
        """
        Capture frame pair from cameras for calibration

        This method captures a single frame from both cameras and adds it to
        the calibration dataset. Call this 10-20 times during calibration.

        Returns:
            Capture result dictionary with frames_captured count
        """
        try:
            if self.calibration_service is None:
                return {
                    'success': False,
                    'message': 'Calibration not started'
                }

            if not self.calibration_service.is_calibrating:
                return {
                    'success': False,
                    'message': 'Calibration not active. Call start_calibration first.'
                }

            # Capture frames from both cameras
            logger.info("Capturing calibration frame pair...")
            frame_cam0 = self._capture_single_frame(camera_id=0)
            frame_cam1 = self._capture_single_frame(camera_id=1)

            if frame_cam0 is None or frame_cam1 is None:
                return {
                    'success': False,
                    'message': 'Failed to capture frames from cameras'
                }

            # Pass to calibration service
            timestamp = time.time()
            success = self.calibration_service.capture_frame_pair(
                frame_cam0, frame_cam1, timestamp
            )

            if not success:
                return {
                    'success': False,
                    'message': 'Failed to store calibration frames'
                }

            # Get updated count
            progress = self.get_calibration_progress()
            frames_captured = progress['frames_captured']

            logger.info(f"Calibration frame {frames_captured} captured successfully")

            return {
                'success': True,
                'message': f'Frame pair {frames_captured} captured successfully',
                'frames_captured': frames_captured,
                'frames_needed': progress['frames_needed'],
                'frames_target': progress['frames_target'],
                'ready_to_calculate': progress['ready_to_calculate']
            }

        except Exception as e:
            logger.error(f"Failed to capture calibration frame: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Error capturing frame: {str(e)}'
            }

    def reset_calibration(self) -> Dict:
        """
        Reset/cancel calibration in progress

        Clears all captured calibration frames and exits calibration mode.
        Use this to start over if you captured bad frames.

        Returns:
            Result dictionary with success status
        """
        try:
            if self.calibration_service is None:
                return {
                    'success': False,
                    'message': 'Calibration service not available'
                }

            # Reset calibration service (clears frames and exits calibration mode)
            self.calibration_service.reset()

            logger.info("Calibration reset successfully")

            return {
                'success': True,
                'message': 'Calibration reset successfully. You can start a new calibration.'
            }

        except Exception as e:
            logger.error(f"Failed to reset calibration: {e}", exc_info=True)
            return {
                'success': False,
                'message': f'Error resetting calibration: {str(e)}'
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

    def set_webrtc_emitter(self, emitter: Callable[[str, Dict[str, Any]], None]) -> None:
        self.webrtc_emitter = emitter

    def _emit_webrtc(self, connection_id: str, message: Dict[str, Any]) -> None:
        if self.webrtc_emitter is None:
            return
        try:
            self.webrtc_emitter(connection_id, message)
        except Exception as e:
            logger.error(f"Failed to emit panorama WebRTC message: {e}")

    def _get_webrtcbin(self):
        if not self.output_pipeline:
            return None
        with self.gst_manager.pipelines_lock:
            entry = self.gst_manager.pipelines.get(self.output_pipeline)
            if not entry:
                return None
            pipeline = entry.get("pipeline")
            if pipeline is None:
                return None
            return pipeline.get_by_name("webrtc")

    def _register_webrtc_callbacks(self) -> None:
        if self.webrtc_callbacks_registered:
            return
        webrtcbin = self._get_webrtcbin()
        if webrtcbin is None:
            raise RuntimeError("webrtcbin not found in panorama output pipeline")

        def on_ice_candidate(_element, mlineindex, candidate):
            session = self.webrtc_session
            if not session:
                return
            self._emit_webrtc(
                session["connection_id"],
                {
                    "v": 1,
                    "type": "webrtc_ice_candidate",
                    "data": {
                        "session_id": session["session_id"],
                        "stream_kind": "panorama",
                        "candidate": candidate,
                        "sdpMLineIndex": mlineindex,
                    },
                },
            )

        webrtcbin.connect("on-ice-candidate", on_ice_candidate)
        self.webrtc_callbacks_registered = True

    def create_webrtc_session(self, connection_id: str) -> Dict[str, Any]:
        should_start_preview = False
        with self.state_lock:
            if self.webrtc_session and self.webrtc_session.get("active"):
                if self.webrtc_session.get("connection_id") == connection_id:
                    return {
                        "success": True,
                        "session_id": self.webrtc_session["session_id"],
                        "stream_kind": "panorama",
                        "ice_servers": self._ice_servers(),
                    }
                return {
                    "success": False,
                    "message": "Panorama WebRTC already in use by another connection",
                }

            should_start_preview = not self.preview_active or self.preview_transport != "webrtc"

        if should_start_preview:
            start = self.start_preview(transport="webrtc")
            if not start.get("success"):
                return {"success": False, "message": start.get("message", "Failed to start panorama preview")}

        with self.state_lock:
            self._register_webrtc_callbacks()

            session_id = str(uuid.uuid4())
            self.webrtc_session = {
                "session_id": session_id,
                "connection_id": connection_id,
                "active": True,
                "created_at": time.time(),
            }
            return {
                "success": True,
                "session_id": session_id,
                "stream_kind": "panorama",
                "ice_servers": self._ice_servers(),
            }

    def _parse_offer(self, sdp_offer: str):
        gi.require_version("GstWebRTC", "1.0")
        gi.require_version("GstSdp", "1.0")
        from gi.repository import GstWebRTC, GstSdp

        _, sdpmsg = GstSdp.SDPMessage.new()
        GstSdp.sdp_message_parse_buffer(bytes(sdp_offer.encode("utf-8")), sdpmsg)
        return GstWebRTC.WebRTCSessionDescription.new(GstWebRTC.WebRTCSDPType.OFFER, sdpmsg)

    def handle_webrtc_offer(self, connection_id: str, session_id: str, sdp_offer: str) -> Dict[str, Any]:
        with self.state_lock:
            session = self.webrtc_session
            if not session or session.get("session_id") != session_id:
                return {"success": False, "message": "Unknown session_id"}
            if session.get("connection_id") != connection_id:
                return {"success": False, "message": "Session does not belong to this connection"}

            webrtcbin = self._get_webrtcbin()
            if webrtcbin is None:
                return {"success": False, "message": "webrtcbin not found"}

            try:
                offer = self._parse_offer(sdp_offer)

                set_remote = Gst.Promise.new()
                webrtcbin.emit("set-remote-description", offer, set_remote)
                set_remote.interrupt()

                create_answer = Gst.Promise.new()
                webrtcbin.emit("create-answer", None, create_answer)
                create_answer.wait()
                reply = create_answer.get_reply()
                answer = reply.get_value("answer")

                set_local = Gst.Promise.new()
                webrtcbin.emit("set-local-description", answer, set_local)
                set_local.interrupt()

                return {
                    "success": True,
                    "session_id": session_id,
                    "stream_kind": "panorama",
                    "sdp": answer.sdp.as_text(),
                }
            except Exception as e:
                logger.error(f"Failed handling panorama WebRTC offer: {e}")
                return {"success": False, "message": str(e)}

    def add_webrtc_ice_candidate(
        self,
        connection_id: str,
        session_id: str,
        candidate: str,
        sdp_mline_index: int,
    ) -> Dict[str, Any]:
        with self.state_lock:
            session = self.webrtc_session
            if not session or session.get("session_id") != session_id:
                return {"success": False, "message": "Unknown session_id"}
            if session.get("connection_id") != connection_id:
                return {"success": False, "message": "Session does not belong to this connection"}

            webrtcbin = self._get_webrtcbin()
            if webrtcbin is None:
                return {"success": False, "message": "webrtcbin not found"}

            try:
                webrtcbin.emit("add-ice-candidate", int(sdp_mline_index), candidate)
                return {"success": True}
            except Exception as e:
                logger.error(f"Failed adding panorama ICE candidate: {e}")
                return {"success": False, "message": str(e)}

    def stop_webrtc_session(self, connection_id: str, session_id: str) -> Dict[str, Any]:
        should_stop_preview = False
        with self.state_lock:
            session = self.webrtc_session
            if not session or session.get("session_id") != session_id:
                return {"success": False, "message": "Unknown session_id"}
            if session.get("connection_id") != connection_id:
                return {"success": False, "message": "Session does not belong to this connection"}

            self.webrtc_session = None
            # Panorama preview is single-stream; stop it when session ends.
            should_stop_preview = True
        if should_stop_preview:
            self.stop_preview()
        return {"success": True}

    def clear_connection_sessions(self, connection_id: str) -> None:
        should_stop_preview = False
        with self.state_lock:
            if self.webrtc_session and self.webrtc_session.get("connection_id") == connection_id:
                self.webrtc_session = None
                should_stop_preview = True
        if should_stop_preview:
            self.stop_preview()

    def _build_output_pipeline(self, transport: str = "hls") -> str:
        """
        Build panorama output pipeline.

        Returns:
            GStreamer pipeline string
        """
        output_config = self.config_manager.config['output']
        width = output_config['width']
        height = output_config['height']
        fps = self.config_manager.config['performance']['preview_fps_target']

        if transport == "webrtc":
            pipeline = build_panorama_output_webrtc_pipeline(
                width=width,
                height=height,
                fps=fps,
                stun_server=self.stun_server,
                turn_server=self.turn_server,
            )
            logger.debug("Built panorama WebRTC output pipeline: %sx%s@%sfps", width, height, fps)
            return pipeline

        hls_location = "/dev/shm/hls/panorama.m3u8"

        pipeline = (
            # Source: appsrc for stitched frames
            f"appsrc name=panorama_source is-live=true do-timestamp=true "
            f"format=time stream-type=stream "
            f"caps=video/x-raw,format=I420,width={width},height={height},"
            f"framerate={fps}/1 ! "

            # Encoder: x264enc for HLS
            "x264enc name=enc speed-preset=ultrafast tune=zerolatency threads=0 "
            "bitrate=8000 key-int-max=60 b-adapt=false bframes=0 "
            "byte-stream=true aud=true intra-refresh=false "
            "option-string=repeat-headers=1:scenecut=0:open-gop=0 ! "

            # Parser and muxer
            "h264parse config-interval=1 disable-passthrough=true ! "
            "video/x-h264,stream-format=byte-stream ! "

            # HLS sink
            "hlssink2 name=sink "
            f"playlist-location={hls_location} "
            f"location={hls_location.replace('.m3u8', '_%05d.ts')} "
            "target-duration=2 "
            "playlist-length=8 "
            "max-files=8 "
            "send-keyframe-requests=true"
        )

        logger.debug(f"Built HLS output pipeline: {width}x{height}@{fps}fps")
        return pipeline

    def _on_new_frame(self, sink, camera_id: int):
        """
        Callback when new frame available from camera appsink

        Args:
            sink: GStreamer appsink element
            camera_id: Camera identifier (0 or 1)

        Returns:
            Gst.FlowReturn.OK
        """
        try:
            # Pull sample from appsink
            sample = sink.emit('pull-sample')
            if sample is None:
                logger.warning(f"Received None sample from cam{camera_id}")
                return Gst.FlowReturn.OK

            # Convert to numpy
            frame, timestamp_ns, metadata = gst_sample_to_numpy(sample)
            if frame is None:
                logger.warning(f"Failed to convert sample to numpy for cam{camera_id}")
                return Gst.FlowReturn.OK

            # Add to synchronizer
            if self.synchronizer:
                self.synchronizer.add_frame(camera_id, frame, timestamp_ns)
                logger.debug(f"Added frame from cam{camera_id}: ts={timestamp_ns}, shape={frame.shape}")

            return Gst.FlowReturn.OK

        except Exception as e:
            logger.error(f"Error in frame callback for cam{camera_id}: {e}", exc_info=True)
            return Gst.FlowReturn.ERROR

    def _stitch_loop(self):
        """
        Thread that continuously stitches synchronized frames

        This thread:
        1. Gets synchronized frame pairs from FrameSynchronizer
        2. Stitches them using VPIStitcher
        3. Pushes result to output pipeline appsrc
        """
        logger.info("Stitching thread started")
        fps_target = self.config_manager.config['performance']['preview_fps_target']
        target_frame_time = 1.0 / fps_target if fps_target > 0 else 0.0

        last_frame_time = time.time()

        while not self.stop_event.is_set():
            try:
                loop_start = time.time()

                # Get synchronized frame pair
                result = self.synchronizer.get_synchronized_pair()
                if result is None:
                    # No frames available, sleep briefly
                    time.sleep(0.001)
                    continue

                frame0, frame1, metadata = result
                timestamp_ns = metadata['timestamp_ns']

                # Stitch frames
                stitch_start = time.time()
                panorama = self.stitcher.stitch(frame0, frame1)
                stitch_time = (time.time() - stitch_start) * 1000.0

                if panorama is None:
                    logger.warning("Stitching failed, skipping frame")
                    continue

                # Push to output
                self._push_panorama_frame(panorama, timestamp_ns)

                # Update metrics
                self.frames_stitched += 1
                current_time = time.time()
                frame_time = current_time - last_frame_time
                last_frame_time = current_time

                # Update FPS every second
                if current_time - self.last_fps_update >= 1.0:
                    self.preview_fps = 1.0 / frame_time if frame_time > 0 else 0.0
                    self.last_fps_update = current_time
                    logger.info(
                        f"Panorama stitching: {self.preview_fps:.1f} FPS, "
                        f"stitch_time={stitch_time:.1f}ms, frames={self.frames_stitched}"
                    )

                # Frame rate limiting
                loop_time = time.time() - loop_start
                if target_frame_time > 0 and loop_time < target_frame_time:
                    sleep_time = target_frame_time - loop_time
                    time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error in stitching loop: {e}", exc_info=True)
                # Continue running even if one frame fails
                time.sleep(0.1)

        logger.info("Stitching thread stopped")

    def _push_panorama_frame(self, frame: np.ndarray, timestamp_ns: int):
        """
        Push stitched panorama frame to output pipeline appsrc

        Args:
            frame: Panorama frame (BGR numpy array)
            timestamp_ns: Frame timestamp in nanoseconds
        """
        try:
            # Get appsrc from output pipeline
            with self.gst_manager.pipelines_lock:
                if self.output_pipeline not in self.gst_manager.pipelines:
                    logger.error("Output pipeline not found")
                    return

                pipeline = self.gst_manager.pipelines[self.output_pipeline]['pipeline']
                appsrc = pipeline.get_by_name('panorama_source')
                if not appsrc:
                    logger.error("Failed to find appsrc in output pipeline")
                    return

            # Convert frame to GStreamer buffer
            buffer = numpy_to_gst_buffer(frame, timestamp_ns)
            if buffer is None:
                logger.error("Failed to convert frame to GStreamer buffer")
                return

            # Push buffer to appsrc
            ret = appsrc.emit('push-buffer', buffer)
            if ret != Gst.FlowReturn.OK:
                logger.warning(f"Failed to push buffer to appsrc: {ret}")

        except Exception as e:
            logger.error(f"Error pushing panorama frame: {e}", exc_info=True)

    def _process_recording_thread(self, match_id: str, cam0_segments: List[str], cam1_segments: List[str]):
        """
        Background thread for post-processing recorded match

        Extracts frames from segments, stitches them, and encodes to video.

        Args:
            match_id: Match identifier
            cam0_segments: List of cam0 segment file paths
            cam1_segments: List of cam1 segment file paths
        """
        try:
            logger.info(f"Post-processing thread started for {match_id}")
            output_path = Path("/mnt/recordings") / match_id / "panorama_archive.mp4"

            # Initialize processing state
            self.processing_state[match_id] = {
                'processing': True,
                'progress': 0,
                'completed': False,
                'error': None,
                'eta_seconds': None,
                'start_time': time.time()
            }

            total_frames = 0
            processed_frames = 0

            # Create output encoder pipeline
            output_width = self.config_manager.config['output']['width']
            output_height = self.config_manager.config['output']['height']
            output_fps = 30  # Target output FPS

            encoder_pipeline_str = (
                f"appsrc name=panorama_source is-live=false do-timestamp=true "
                f"format=time stream-type=stream "
                f"caps=video/x-raw,format=I420,width={output_width},height={output_height},"
                f"framerate={output_fps}/1 ! "
                f"nvv4l2h264enc bitrate=8000000 ! "
                f"h264parse ! "
                f"mp4mux ! "
                f"filesink location={output_path}"
            )

            # Create encoder pipeline
            encoder_created = self.gst_manager.create_pipeline(
                name=f'panorama_encode_{match_id}',
                pipeline_description=encoder_pipeline_str,
                on_eos=lambda name: logger.info(f"Encoder EOS: {name}"),
                on_error=lambda name, err: logger.error(f"Encoder error: {name} - {err}"),
                metadata={'match_id': match_id}
            )

            if not encoder_created:
                raise Exception("Failed to create encoder pipeline")

            if not self.gst_manager.start_pipeline(f'panorama_encode_{match_id}'):
                raise Exception("Failed to start encoder pipeline")

            logger.info("Encoder pipeline started")

            # Get appsrc from encoder
            with self.gst_manager.pipelines_lock:
                encoder_pipeline = self.gst_manager.pipelines[f'panorama_encode_{match_id}']['pipeline']
                appsrc = encoder_pipeline.get_by_name('panorama_source')

            # Process each segment pair
            min_segments = min(len(cam0_segments), len(cam1_segments))

            for seg_idx in range(min_segments):
                cam0_seg = cam0_segments[seg_idx]
                cam1_seg = cam1_segments[seg_idx]

                logger.info(f"Processing segment {seg_idx+1}/{min_segments}: {Path(cam0_seg).name}, {Path(cam1_seg).name}")

                # Extract and stitch frames from this segment pair
                frames_in_segment = self._process_segment_pair(cam0_seg, cam1_seg, appsrc, output_fps)

                processed_frames += frames_in_segment
                progress = int((seg_idx + 1) / min_segments * 100)

                # Update progress
                self.processing_state[match_id]['progress'] = progress
                elapsed = time.time() - self.processing_state[match_id]['start_time']
                if progress > 0:
                    eta = (elapsed / progress) * (100 - progress)
                    self.processing_state[match_id]['eta_seconds'] = int(eta)

                logger.info(f"Progress: {progress}%, processed {processed_frames} frames")

            # Send EOS to encoder
            logger.info("Sending EOS to encoder pipeline")
            appsrc.emit('end-of-stream')

            # Wait for encoding to finish (max 60 seconds)
            time.sleep(2)
            self.gst_manager.stop_pipeline(f'panorama_encode_{match_id}')

            # Update final state
            self.processing_state[match_id].update({
                'processing': False,
                'progress': 100,
                'completed': True,
                'total_frames': processed_frames
            })

            logger.info(f"Post-processing complete for {match_id}: {processed_frames} frames, output: {output_path}")

        except Exception as e:
            logger.error(f"Post-processing failed for {match_id}: {e}", exc_info=True)
            self.processing_state[match_id].update({
                'processing': False,
                'completed': False,
                'error': str(e)
            })

    def _process_segment_pair(self, cam0_path: str, cam1_path: str, appsrc, output_fps: int) -> int:
        """
        Extract frames from segment pair, stitch, and push to encoder

        Args:
            cam0_path: Path to cam0 segment
            cam1_path: Path to cam1 segment
            appsrc: GStreamer appsrc element for encoder
            output_fps: Target output framerate

        Returns:
            Number of frames processed
        """
        import cv2

        frames_processed = 0

        try:
            # Open both videos
            cap0 = cv2.VideoCapture(cam0_path)
            cap1 = cv2.VideoCapture(cam1_path)

            if not cap0.isOpened() or not cap1.isOpened():
                logger.error(f"Failed to open segment videos: {cam0_path}, {cam1_path}")
                return 0

            # Get frame counts
            total_frames = int(min(cap0.get(cv2.CAP_PROP_FRAME_COUNT), cap1.get(cv2.CAP_PROP_FRAME_COUNT)))
            logger.info(f"Segment has {total_frames} frames")

            # Process frames
            frame_idx = 0
            while True:
                # Read frames
                ret0, frame0 = cap0.read()
                ret1, frame1 = cap1.read()

                if not ret0 or not ret1:
                    break

                # Stitch frames
                panorama = self.stitcher.stitch(frame0, frame1)
                if panorama is None:
                    logger.warning(f"Stitching failed for frame {frame_idx}")
                    continue

                # Convert to I420 for encoder
                panorama_yuv = cv2.cvtColor(panorama, cv2.COLOR_BGR2YUV_I420)

                # Create GStreamer buffer
                timestamp_ns = int(frame_idx * (1000000000 / output_fps))
                buffer = Gst.Buffer.new_allocate(None, len(panorama_yuv.tobytes()), None)

                success, map_info = buffer.map(Gst.MapFlags.WRITE)
                if success:
                    map_info.data[:] = panorama_yuv.tobytes()
                    buffer.unmap(map_info)
                    buffer.pts = timestamp_ns
                    buffer.dts = Gst.CLOCK_TIME_NONE
                    buffer.duration = Gst.CLOCK_TIME_NONE

                    # Push to encoder
                    ret = appsrc.emit('push-buffer', buffer)
                    if ret != Gst.FlowReturn.OK:
                        logger.warning(f"Failed to push buffer: {ret}")

                frames_processed += 1
                frame_idx += 1

            cap0.release()
            cap1.release()

            logger.info(f"Processed {frames_processed} frames from segment")
            return frames_processed

        except Exception as e:
            logger.error(f"Error processing segment pair: {e}", exc_info=True)
            return frames_processed

    def _cleanup_preview(self):
        """
        Clean up all preview resources (called on error during startup)
        """
        logger.info("Cleaning up preview resources")

        try:
            # Stop stitching thread
            self.stop_event.set()
            if self.stitch_thread and self.stitch_thread.is_alive():
                self.stitch_thread.join(timeout=2.0)

            # Stop capture pipelines
            for cam_id, pipeline_name in list(self.capture_pipelines.items()):
                try:
                    self.gst_manager.stop_pipeline(pipeline_name, wait_for_eos=False, timeout=1.0)
                    self.gst_manager.remove_pipeline(pipeline_name)
                except Exception as e:
                    logger.error(f"Error cleaning up capture pipeline cam{cam_id}: {e}")

            self.capture_pipelines.clear()

            # Stop output pipeline
            if self.output_pipeline:
                try:
                    self.gst_manager.stop_pipeline(self.output_pipeline, wait_for_eos=False, timeout=1.0)
                    self.gst_manager.remove_pipeline(self.output_pipeline)
                except Exception as e:
                    logger.error(f"Error cleaning up output pipeline: {e}")
                self.output_pipeline = None

            # Clear buffers
            if self.synchronizer:
                self.synchronizer.cam0_buffer.clear()
                self.synchronizer.cam1_buffer.clear()

            # Update state
            self.preview_active = False
            self.preview_start_time = None
            self.webrtc_session = None
            self.webrtc_callbacks_registered = False

        except Exception as e:
            logger.error(f"Error during preview cleanup: {e}", exc_info=True)

    def _on_capture_eos(self, name: str, metadata: Dict):
        """
        EOS callback for capture pipelines

        Args:
            name: Pipeline name
            metadata: Pipeline metadata
        """
        camera_id = metadata.get('camera_id', -1)
        logger.info(f"Capture pipeline {name} (cam{camera_id}) received EOS")

    def _on_capture_error(self, name: str, error: str, debug: str, metadata: Dict):
        """
        Error callback for capture pipelines

        Args:
            name: Pipeline name
            error: Error message
            debug: Debug information
            metadata: Pipeline metadata
        """
        camera_id = metadata.get('camera_id', -1)
        logger.error(f"Capture pipeline {name} (cam{camera_id}) error: {error}")
        logger.debug(f"Debug info: {debug}")

        # If capture pipeline fails during preview, stop preview
        if self.preview_active:
            logger.warning("Stopping preview due to capture pipeline error")
            self.stop_preview()

    def _on_output_eos(self, name: str, metadata: Dict):
        """
        EOS callback for output pipeline

        Args:
            name: Pipeline name
            metadata: Pipeline metadata
        """
        logger.info(f"Output pipeline {name} received EOS")

    def _on_output_error(self, name: str, error: str, debug: str, metadata: Dict):
        """
        Error callback for output pipeline

        Args:
            name: Pipeline name
            error: Error message
            debug: Debug information
            metadata: Pipeline metadata
        """
        logger.error(f"Output pipeline {name} error: {error}")
        logger.debug(f"Debug info: {debug}")

        # If output pipeline fails during preview, stop preview
        if self.preview_active:
            logger.warning("Stopping preview due to output pipeline error")
            self.stop_preview()

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

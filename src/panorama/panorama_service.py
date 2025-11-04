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
import numpy as np
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from threading import Lock

# Add video-pipeline to path for GStreamer imports
sys.path.insert(0, '/home/mislav/footballvision-pro/src/video-pipeline')
from gstreamer_manager import GStreamerManager
from pipeline_builders import build_panorama_capture_pipeline

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

        # GStreamer components
        self.gst_manager = GStreamerManager()
        self.capture_pipelines = {}  # {camera_id: pipeline_name}
        self.output_pipeline = None

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

                # 2. Create output pipeline (appsrc -> encoder -> hlssink2)
                logger.info("Creating output pipeline for stitched panorama")
                output_pipeline_str = self._build_output_pipeline()
                created = self.gst_manager.create_pipeline(
                    name='panorama_output',
                    pipeline_description=output_pipeline_str,
                    on_eos=self._on_output_eos,
                    on_error=self._on_output_error,
                    metadata={}
                )

                if not created:
                    raise Exception("Failed to create output pipeline")

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
                self._save_state()

                logger.info("Panorama preview started successfully")

                return {
                    'success': True,
                    'message': 'Panorama preview started',
                    'hls_url': '/hls/panorama.m3u8',
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

    def _build_output_pipeline(self) -> str:
        """
        Build appsrc -> encoder -> hlssink2 pipeline for panorama output

        Returns:
            GStreamer pipeline string
        """
        output_config = self.config_manager.config['output']
        width = output_config['width']
        height = output_config['height']
        fps = self.config_manager.config['performance']['preview_fps_target']

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

        logger.debug(f"Built output pipeline: {width}x{height}@{fps}fps")
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

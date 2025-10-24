#!/usr/bin/env python3
"""
Recording service for FootballVision Pro
Uses in-process GStreamer for instant, bulletproof recording operations
"""

import os
import time
import json
import logging
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
from threading import Lock

from gstreamer_manager import GStreamerManager
from pipeline_builders import build_recording_pipeline

logger = logging.getLogger(__name__)


class RecordingService:
    """
    Manages dual-camera recording using in-process GStreamer
    - Instant start/stop (no 3s/15s delays)
    - Survives page refreshes and API restarts
    - Recording protection (lock file prevents accidental stops)
    """
    
    def __init__(self, base_recordings_dir: str = "/mnt/recordings"):
        self.base_recordings_dir = Path(base_recordings_dir)
        self.gst_manager = GStreamerManager()
        
        # Recording state
        self.current_match_id: Optional[str] = None
        self.recording_start_time: Optional[float] = None
        self.state_lock = Lock()
        
        # Recording protection
        self.protection_seconds = 10.0  # Don't allow stop within first 10s
        
        # State persistence file
        self.state_file = Path("/tmp/footballvision_recording_state.json")
        
        # Camera IDs
        self.camera_ids = [0, 1]
        
        # Load persisted state on startup
        self._load_state()
    
    def _load_state(self):
        """Load persisted recording state from disk"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    
                if state.get('recording', False):
                    match_id = state.get('match_id')
                    start_time = state.get('start_time')
                    
                    logger.info(f"Restored recording state: match_id={match_id}, start_time={start_time}")
                    
                    # Check if pipelines still exist
                    cam0_exists = self.gst_manager.get_pipeline_status('recording_cam0') is not None
                    cam1_exists = self.gst_manager.get_pipeline_status('recording_cam1') is not None
                    
                    if cam0_exists and cam1_exists:
                        self.current_match_id = match_id
                        self.recording_start_time = start_time
                        logger.info("Recording pipelines still active after restart")
                    else:
                        logger.warning("Recording state file exists but pipelines not found, clearing state")
                        self._clear_state()
                        
        except Exception as e:
            logger.error(f"Failed to load recording state: {e}")
            self._clear_state()
    
    def _save_state(self):
        """Persist recording state to disk"""
        try:
            state = {
                'recording': self.current_match_id is not None,
                'match_id': self.current_match_id,
                'start_time': self.recording_start_time,
                'timestamp': time.time()
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save recording state: {e}")
    
    def _clear_state(self):
        """Clear persisted state"""
        try:
            if self.state_file.exists():
                self.state_file.unlink()
        except Exception as e:
            logger.error(f"Failed to clear recording state: {e}")
    
    def get_status(self) -> Dict:
        """
        Get current recording status
        Returns instantly (no delays)
        """
        with self.state_lock:
            if self.current_match_id is None:
                return {
                    'recording': False,
                    'match_id': None,
                    'duration': 0.0,
                    'cameras': {}
                }
            
            # Calculate duration
            duration = time.time() - self.recording_start_time if self.recording_start_time else 0.0
            
            # Get pipeline info
            cameras = {}
            for cam_id in self.camera_ids:
                pipeline_name = f'recording_cam{cam_id}'
                info = self.gst_manager.get_pipeline_status(pipeline_name)
                
                if info:
                    cameras[f'camera_{cam_id}'] = {
                        "state": info.state.value,
                        "uptime": (datetime.utcnow() - info.start_time).total_seconds() if info.start_time else 0.0
                    }
            
            return {
                'recording': True,
                'match_id': self.current_match_id,
                'duration': duration,
                'cameras': cameras,
                'protected': duration < self.protection_seconds
            }
    
    def start_recording(self, match_id: str, force: bool = False) -> Dict:
        """
        Start dual-camera recording
        
        Args:
            match_id: Unique match identifier
            force: Force start even if already recording
            
        Returns:
            Dict with status and message
        """
        with self.state_lock:
            # Check if already recording
            if self.current_match_id is not None:
                if not force:
                    return {
                        'success': False,
                        'message': f'Already recording match: {self.current_match_id}'
                    }
                else:
                    logger.warning(f"Force stopping existing recording: {self.current_match_id}")
                    self._stop_recording_internal(force=True)
            
            # Create output directory
            match_dir = self.base_recordings_dir / match_id / "segments"
            match_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Starting recording for match: {match_id}")
            
            # Start both cameras
            started_cameras = []
            failed_cameras = []
            
            for cam_id in self.camera_ids:
                try:
                    # Build output pattern
                    # Generate timestamp-based filename pattern for segments
                    from datetime import datetime
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    output_pattern = str(match_dir / f"cam{cam_id}_{timestamp}_%02d.mp4")
                    
                    # Build pipeline
                    pipeline_str = build_recording_pipeline(cam_id, output_pattern)
                    
                    # Create pipeline
                    pipeline_name = f'recording_cam{cam_id}'
                    
                    def on_eos(name, metadata):
                        logger.info(f"Pipeline {name} received EOS")
                    
                    def on_error(name, error, debug, metadata):
                        logger.error(f"Pipeline {name} error: {error}, debug: {debug}")
                        # TODO: Add auto-recovery logic here
                    
                    created = self.gst_manager.create_pipeline(
                        name=pipeline_name,
                        pipeline_description=pipeline_str,
                        on_eos=on_eos,
                        on_error=on_error,
                        metadata={'camera_id': cam_id, 'match_id': match_id}
                    )
                    
                    if not created:
                        logger.error(f"Failed to create recording pipeline for camera {cam_id}")
                        failed_cameras.append(cam_id)
                        continue
                    
                    # Start pipeline (instant, no delay)
                    started = self.gst_manager.start_pipeline(pipeline_name)
                    if not started:
                        logger.error(f"Failed to start recording pipeline for camera {cam_id}")
                        self.gst_manager.remove_pipeline(pipeline_name)
                        failed_cameras.append(cam_id)
                        continue
                    
                    started_cameras.append(cam_id)
                    logger.info(f"Camera {cam_id} recording started")
                    
                except Exception as e:
                    logger.error(f"Failed to start camera {cam_id}: {e}")
                    failed_cameras.append(cam_id)
            
            # Check if at least one camera started
            if not started_cameras:
                return {
                    'success': False,
                    'message': 'Failed to start any cameras',
                    'failed_cameras': failed_cameras
                }
            
            # Update state
            self.current_match_id = match_id
            self.recording_start_time = time.time()
            
            # Persist state
            self._save_state()
            
            return {
                'success': True,
                'message': f'Recording started for match: {match_id}',
                'match_id': match_id,
                'cameras_started': started_cameras,
                'cameras_failed': failed_cameras
            }
    
    def _stop_recording_internal(self, force: bool = False) -> bool:
        """
        Internal method to stop recording
        
        Args:
            force: Skip protection check
            
        Returns:
            True if stopped successfully
        """
        if self.current_match_id is None:
            return False
        
        # Check recording protection
        if not force:
            duration = time.time() - self.recording_start_time if self.recording_start_time else 0.0
            if duration < self.protection_seconds:
                raise ValueError(
                    f"Recording protected for {self.protection_seconds}s. "
                    f"Current duration: {duration:.1f}s. Use force=True to override."
                )
        
        logger.info(f"Stopping recording for match: {self.current_match_id}")
        
        # Stop both cameras
        for cam_id in self.camera_ids:
            pipeline_name = f'recording_cam{cam_id}'
            try:
                # Graceful stop with EOS (takes ~2s, not 15s)
                self.gst_manager.stop_pipeline(pipeline_name, wait_for_eos=True, timeout=5.0)
                logger.info(f"Camera {cam_id} recording stopped")
                # Remove pipeline from memory to allow fresh start next time
                self.gst_manager.remove_pipeline(pipeline_name)
            except Exception as e:
                logger.error(f"Failed to stop camera {cam_id}: {e}")
        
        # Clear state
        self.current_match_id = None
        self.recording_start_time = None
        self._clear_state()
        
        return True
    
    def stop_recording(self, force: bool = False) -> Dict:
        """
        Stop dual-camera recording
        
        Args:
            force: Skip protection check and force stop
            
        Returns:
            Dict with status and message
        """
        with self.state_lock:
            if self.current_match_id is None:
                return {
                    'success': False,
                    'message': 'Not currently recording'
                }
            
            try:
                self._stop_recording_internal(force=force)
                
                return {
                    'success': True,
                    'message': 'Recording stopped successfully'
                }
                
            except ValueError as e:
                # Protection error
                return {
                    'success': False,
                    'message': str(e),
                    'protected': True
                }
                
            except Exception as e:
                logger.error(f"Failed to stop recording: {e}")
                return {
                    'success': False,
                    'message': f'Error stopping recording: {str(e)}'
                }
    
    def cleanup(self):
        """Cleanup resources (called on shutdown)"""
        logger.info("RecordingService cleanup")
        if self.current_match_id:
            logger.warning(f"Stopping active recording during cleanup: {self.current_match_id}")
            self._stop_recording_internal(force=True)


# Global instance
_recording_service: Optional[RecordingService] = None


def get_recording_service() -> RecordingService:
    """Get or create the global RecordingService instance"""
    global _recording_service
    if _recording_service is None:
        _recording_service = RecordingService()
    return _recording_service

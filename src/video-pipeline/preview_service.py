#!/usr/bin/env python3
"""
Preview service for FootballVision Pro
Uses in-process GStreamer for instant, reliable HLS preview
"""

import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
from threading import Lock

from gstreamer_manager import GStreamerManager, PipelineState
from pipeline_builders import build_preview_pipeline
from exposure_sync_service import get_exposure_sync_service

logger = logging.getLogger(__name__)


class PreviewService:
    """
    Manages dual-camera HLS preview using in-process GStreamer
    - Instant start/stop
    - Independent from recording (can run simultaneously)
    - Survives page refreshes
    """
    
    def __init__(self, hls_base_dir: str = "/dev/shm/hls"):
        self.hls_base_dir = Path(hls_base_dir)
        self.hls_base_dir.mkdir(parents=True, exist_ok=True)
        
        self.gst_manager = GStreamerManager()
        self.state_lock = Lock()
        
        # Camera IDs
        self.camera_ids = [0, 1]
        
        # Track preview state
        self.preview_active = {cam_id: False for cam_id in self.camera_ids}
    
    def get_status(self) -> Dict:
        """Get current preview status"""
        with self.state_lock:
            cameras: Dict[str, Dict] = {}

            for cam_id in self.camera_ids:
                pipeline_name = f'preview_cam{cam_id}'
                info = self.gst_manager.get_pipeline_status(pipeline_name)

                active = bool(info and info.state == PipelineState.RUNNING)
                uptime = 0.0
                if info and info.start_time:
                    uptime = (datetime.utcnow() - info.start_time).total_seconds()

                cameras[f'camera_{cam_id}'] = {
                    'active': active,
                    'state': info.state.value if info else 'stopped',
                    'uptime': uptime,
                    'hls_url': f'/hls/cam{cam_id}.m3u8'
                }
                self.preview_active[cam_id] = active

            return {
                'preview_active': any(cam['active'] for cam in cameras.values()),
                'cameras': cameras
            }
    
    def start_preview(self, camera_id: Optional[int] = None) -> Dict:
        """
        Start HLS preview for one or both cameras
        
        Args:
            camera_id: Specific camera to start (0 or 1), or None for both
            
        Returns:
            Dict with status and message
        """
        with self.state_lock:
            # Recreate HLS directory in case tmpfs was cleared while service kept running.
            self.hls_base_dir.mkdir(parents=True, exist_ok=True)
            cameras_to_start = [camera_id] if camera_id is not None else self.camera_ids
            
            started_cameras = []
            failed_cameras = []
            
            for cam_id in cameras_to_start:
                if cam_id not in self.camera_ids:
                    failed_cameras.append(cam_id)
                    continue
                
                # Check if already running
                pipeline_name = f'preview_cam{cam_id}'
                status = self.gst_manager.get_pipeline_status(pipeline_name)
                if status and status.state == PipelineState.RUNNING:
                    logger.info(f"Preview camera {cam_id} already running")
                    started_cameras.append(cam_id)
                    continue

                # If pipeline exists but not running, remove it first
                if status:
                    logger.info(f"Preview camera {cam_id} exists but not running (state={status.state.value}), removing")
                    self.gst_manager.remove_pipeline(pipeline_name)
                
                try:
                    # Build HLS location
                    hls_location = str(self.hls_base_dir / f"cam{cam_id}.m3u8")
                    
                    # Build pipeline
                    pipeline_str = build_preview_pipeline(cam_id, hls_location)
                    
                    # Create pipeline
                    def on_eos(name, metadata):
                        logger.info(f"Preview pipeline {name} received EOS")
                    
                    def on_error(name, error, debug, metadata):
                        logger.error(f"Preview pipeline {name} error: {error}, debug: {debug}")
                    
                    created = self.gst_manager.create_pipeline(
                        name=pipeline_name,
                        pipeline_description=pipeline_str,
                        on_eos=on_eos,
                        on_error=on_error,
                        metadata={'camera_id': cam_id}
                    )
                    
                    if not created:
                        logger.error(f"Failed to create preview pipeline for camera {cam_id}")
                        failed_cameras.append(cam_id)
                        continue

                    # Start pipeline
                    started = self.gst_manager.start_pipeline(pipeline_name)
                    if not started:
                        logger.error(f"Failed to start preview pipeline for camera {cam_id}")
                        self.gst_manager.remove_pipeline(pipeline_name)
                        failed_cameras.append(cam_id)
                        continue
                    
                    self.preview_active[cam_id] = True
                    started_cameras.append(cam_id)
                    logger.info(f"Preview camera {cam_id} started")
                    
                except Exception as e:
                    logger.error(f"Failed to start preview camera {cam_id}: {e}")
                    failed_cameras.append(cam_id)
            
            if not started_cameras:
                return {
                    'success': False,
                    'message': 'Failed to start any preview cameras',
                    'failed_cameras': failed_cameras
                }

            # Start exposure synchronization service
            exposure_service = get_exposure_sync_service(self.gst_manager)
            if exposure_service:
                exposure_service.start()
                logger.info("Exposure synchronization service started")

            return {
                'success': True,
                'message': f'Preview started for cameras: {started_cameras}',
                'cameras_started': started_cameras,
                'cameras_failed': failed_cameras
            }
    
    def stop_preview(self, camera_id: Optional[int] = None) -> Dict:
        """
        Stop HLS preview for one or both cameras
        
        Args:
            camera_id: Specific camera to stop (0 or 1), or None for both
            
        Returns:
            Dict with status and message
        """
        with self.state_lock:
            cameras_to_stop = [camera_id] if camera_id is not None else self.camera_ids

            # Stop exposure sync before tearing down pipelines to avoid concurrent
            # access while sinks are being dismantled.
            stop_exposure_sync = camera_id is None
            if stop_exposure_sync:
                exposure_service = get_exposure_sync_service()
                if exposure_service:
                    exposure_service.stop()
                    logger.info("Exposure synchronization service stopped")
            
            stopped_cameras = []
            failed_cameras = []
            
            for cam_id in cameras_to_stop:
                if cam_id not in self.camera_ids:
                    failed_cameras.append(cam_id)
                    continue
                
                pipeline_name = f'preview_cam{cam_id}'
                
                try:
                    # For preview, avoid EOS teardown with hlssink2/splitmuxsink.
                    # Fast NULL transition is more stable than EOS on rapid stop.
                    stopped = self.gst_manager.stop_pipeline(pipeline_name, wait_for_eos=False, timeout=1.0)
                    if not stopped:
                        logger.warning(f"Preview pipeline {pipeline_name} stop request returned False")
                        failed_cameras.append(cam_id)
                        continue

                    self.preview_active[cam_id] = False
                    stopped_cameras.append(cam_id)
                    logger.info(f"Preview camera {cam_id} stopped")
                    
                except Exception as e:
                    logger.error(f"Failed to stop preview camera {cam_id}: {e}")
                    failed_cameras.append(cam_id)
            
            if not stopped_cameras:
                return {
                    'success': False,
                    'message': 'No preview cameras were stopped',
                    'failed_cameras': failed_cameras
                }

            return {
                'success': True,
                'message': f'Preview stopped for cameras: {stopped_cameras}',
                'cameras_stopped': stopped_cameras,
                'cameras_failed': failed_cameras
            }
    
    def restart_preview(self, camera_id: Optional[int] = None) -> Dict:
        """
        Restart HLS preview for one or both cameras
        
        Args:
            camera_id: Specific camera to restart (0 or 1), or None for both
            
        Returns:
            Dict with status and message
        """
        # Stop first
        stop_result = self.stop_preview(camera_id)
        
        # Start again
        start_result = self.start_preview(camera_id)
        
        return {
            'success': start_result['success'],
            'message': f"Restart: {stop_result['message']} -> {start_result['message']}",
            'stop_result': stop_result,
            'start_result': start_result
        }
    
    def cleanup(self):
        """Cleanup resources (called on shutdown)"""
        logger.info("PreviewService cleanup")
        for cam_id in self.camera_ids:
            if self.preview_active[cam_id]:
                try:
                    self.stop_preview(cam_id)
                except Exception as e:
                    logger.error(f"Error stopping preview camera {cam_id} during cleanup: {e}")


# Global instance
_preview_service: Optional[PreviewService] = None


def get_preview_service() -> PreviewService:
    """Get or create the global PreviewService instance"""
    global _preview_service
    if _preview_service is None:
        _preview_service = PreviewService()
    return _preview_service

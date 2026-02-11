#!/usr/bin/env python3
"""
Recording service for FootballVision Pro
Uses in-process GStreamer for instant, bulletproof recording operations
"""

import os
import time
import json
import re
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from threading import Lock, Thread

from gstreamer_manager import GStreamerManager
from pipeline_builders import build_recording_pipeline, load_camera_config

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

        # Recording policy (loaded from camera config with safe defaults)
        self.require_all_cameras = True
        self.max_recovery_attempts = 2
        self.recovery_backoff_seconds = 1.0
        self.stop_eos_timeout_seconds = 5.0

        # Recording state
        self.current_match_id: Optional[str] = None
        self.recording_start_time: Optional[float] = None
        self.process_after_recording: bool = False  # Post-processing flag
        self.state_lock = Lock()

        # Camera-level recovery and degraded-state tracking
        self.camera_recovery_state: Dict[int, Dict[str, Any]] = {}
        self.degraded_cameras: Dict[str, str] = {}
        self.health_last_segment_snapshot: Dict[int, Dict[str, Any]] = {}
        
        # Recording protection
        self.protection_seconds = 10.0  # Don't allow stop within first 10s
        
        # State persistence file
        self.state_file = Path("/tmp/footballvision_recording_state.json")
        
        # Camera IDs
        self.camera_ids = [0, 1]

        self._init_recovery_state()

        # Load persisted state on startup
        self._load_recording_policy()
        self._load_state()

    def _load_recording_policy(self):
        """Load runtime recording policy from camera config."""
        try:
            config = load_camera_config()
            self.require_all_cameras = bool(config.get('recording_require_all_cameras', True))
            self.max_recovery_attempts = max(0, int(config.get('recording_recovery_max_attempts', 2)))
            self.recovery_backoff_seconds = max(0.0, float(config.get('recording_recovery_backoff_seconds', 1.0)))
            self.stop_eos_timeout_seconds = max(1.0, float(config.get('recording_stop_eos_timeout_seconds', 5.0)))
        except Exception as e:
            logger.warning(
                "Failed to load recording policy from config: %s. Using defaults.",
                e,
            )
            self.require_all_cameras = True
            self.max_recovery_attempts = 2
            self.recovery_backoff_seconds = 1.0
            self.stop_eos_timeout_seconds = 5.0

    def _init_recovery_state(self):
        """Reset per-camera recovery state for the current recording session."""
        self.camera_recovery_state = {
            cam_id: {
                'attempts': 0,
                'recovering': False,
                'last_error': None,
                'last_recovery_ts': None,
                'failed_permanently': False,
            }
            for cam_id in self.camera_ids
        }
        self.degraded_cameras = {}
        self.health_last_segment_snapshot = {}

    @staticmethod
    def _build_output_pattern(match_dir: Path, cam_id: int) -> str:
        """Build timestamped splitmux output pattern for a camera."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return str(match_dir / f"cam{cam_id}_{timestamp}_%02d.mp4")

    def _get_recording_quality_preset(self) -> str:
        """Get configured recording quality preset with safe fallback."""
        try:
            config = load_camera_config()
            return config.get('recording_quality', 'high')
        except Exception as e:
            logger.warning("Failed to load quality preset from config: %s, using 'high'", e)
            return 'high'

    def _handle_pipeline_error(self, camera_id: int, match_id: str, error: Any, debug: Any):
        """Schedule bounded camera pipeline recovery after an asynchronous pipeline error."""
        error_message = str(error)
        if debug:
            error_message = f"{error_message} (debug={debug})"

        with self.state_lock:
            if self.current_match_id != match_id:
                logger.info(
                    "Ignoring pipeline error for camera %s because match %s is no longer active",
                    camera_id,
                    match_id,
                )
                return

            state = self.camera_recovery_state.setdefault(
                camera_id,
                {
                    'attempts': 0,
                    'recovering': False,
                    'last_error': None,
                    'last_recovery_ts': None,
                    'failed_permanently': False,
                },
            )
            state['last_error'] = error_message

            if state.get('recovering'):
                logger.warning(
                    "Camera %s already recovering; suppressing duplicate error signal",
                    camera_id,
                )
                return

            if state['attempts'] >= self.max_recovery_attempts:
                state['failed_permanently'] = True
                self.degraded_cameras[f"camera_{camera_id}"] = error_message
                logger.error(
                    "Camera %s exhausted recovery attempts (%s). Marking degraded.",
                    camera_id,
                    self.max_recovery_attempts,
                )
                return

            next_attempt = state['attempts'] + 1
            state['attempts'] = next_attempt
            state['recovering'] = True

        logger.warning(
            "Scheduling recovery for camera %s (attempt %s/%s)",
            camera_id,
            next_attempt,
            self.max_recovery_attempts,
        )
        Thread(
            target=self._recover_camera_pipeline,
            args=(camera_id, match_id, next_attempt),
            daemon=True,
        ).start()

    def _recover_camera_pipeline(self, camera_id: int, match_id: str, attempt: int):
        """Attempt to recover a single recording camera pipeline."""
        delay = min(5.0, self.recovery_backoff_seconds * max(1, attempt))
        if delay > 0:
            time.sleep(delay)

        pipeline_name = f"recording_cam{camera_id}"
        with self.state_lock:
            if self.current_match_id != match_id:
                state = self.camera_recovery_state.get(camera_id)
                if state:
                    state['recovering'] = False
                return

        try:
            match_dir = self.base_recordings_dir / match_id / "segments"
            output_pattern = self._build_output_pattern(match_dir, camera_id)
            quality_preset = self._get_recording_quality_preset()
            pipeline_str = build_recording_pipeline(camera_id, output_pattern, quality_preset=quality_preset)

            def on_eos(name, metadata):
                logger.info("Recovered pipeline %s received EOS", name)

            def on_error(name, error, debug, metadata, camera_id=camera_id, match_id=match_id):
                logger.error("Recovered pipeline %s error: %s, debug: %s", name, error, debug)
                self._handle_pipeline_error(camera_id, match_id, error, debug)

            # Best-effort cleanup of the broken pipeline before recreation.
            try:
                self.gst_manager.stop_pipeline(pipeline_name, wait_for_eos=False, timeout=1.0)
            except Exception as stop_error:
                logger.warning("Failed to stop pipeline %s during recovery: %s", pipeline_name, stop_error)
            try:
                self.gst_manager.remove_pipeline(pipeline_name)
            except Exception as remove_error:
                logger.warning("Failed to remove pipeline %s during recovery: %s", pipeline_name, remove_error)

            created = self.gst_manager.create_pipeline(
                name=pipeline_name,
                pipeline_description=pipeline_str,
                on_eos=on_eos,
                on_error=on_error,
                metadata={'camera_id': camera_id, 'match_id': match_id},
            )
            started = created and self.gst_manager.start_pipeline(pipeline_name)
            failure_reason = None
            if not created:
                failure_reason = "create_pipeline returned False"
            elif not started:
                failure_reason = "start_pipeline returned False"
        except Exception as e:
            started = False
            failure_reason = str(e)

        with self.state_lock:
            state = self.camera_recovery_state.setdefault(
                camera_id,
                {
                    'attempts': 0,
                    'recovering': False,
                    'last_error': None,
                    'last_recovery_ts': None,
                    'failed_permanently': False,
                },
            )
            state['recovering'] = False
            state['last_recovery_ts'] = time.time()

            if started:
                state['last_error'] = None
                state['failed_permanently'] = False
                self.degraded_cameras.pop(f"camera_{camera_id}", None)
                logger.info("Camera %s recovery succeeded on attempt %s", camera_id, attempt)
                return

            state['last_error'] = failure_reason
            if state['attempts'] >= self.max_recovery_attempts:
                state['failed_permanently'] = True
                self.degraded_cameras[f"camera_{camera_id}"] = failure_reason
                logger.error(
                    "Camera %s recovery failed after %s attempts: %s",
                    camera_id,
                    state['attempts'],
                    failure_reason,
                )
                return

        logger.warning(
            "Camera %s recovery attempt %s failed (%s); retrying.",
            camera_id,
            attempt,
            failure_reason,
        )
        self._handle_pipeline_error(camera_id, match_id, failure_reason, None)
    
    def _load_state(self):
        """Load persisted recording state from disk"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    
                if state.get('recording', False):
                    match_id = state.get('match_id')
                    start_time = state.get('start_time')
                    process_after = state.get('process_after_recording', False)

                    logger.info(f"Restored recording state: match_id={match_id}, start_time={start_time}, process_after={process_after}")

                    # Check if pipelines still exist
                    cam0_exists = self.gst_manager.get_pipeline_status('recording_cam0') is not None
                    cam1_exists = self.gst_manager.get_pipeline_status('recording_cam1') is not None

                    if cam0_exists and cam1_exists:
                        self.current_match_id = match_id
                        self.recording_start_time = start_time
                        self.process_after_recording = process_after
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
                'process_after_recording': self.process_after_recording,
                'timestamp': time.time()
            }
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_state_file = self.state_file.with_name(f"{self.state_file.name}.tmp")

            with open(tmp_state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_state_file, self.state_file)

        except Exception as e:
            logger.error(f"Failed to save recording state: {e}")
            try:
                tmp_state_file = self.state_file.with_name(f"{self.state_file.name}.tmp")
                if tmp_state_file.exists():
                    tmp_state_file.unlink()
            except Exception:
                pass
    
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
                    'cameras': {},
                    'degraded': False,
                    'degraded_cameras': {},
                    'camera_recovery': {},
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

            camera_recovery = {
                f"camera_{cam_id}": {
                    "attempts": state.get('attempts', 0),
                    "recovering": state.get('recovering', False),
                    "failed_permanently": state.get('failed_permanently', False),
                    "last_error": state.get('last_error'),
                    "last_recovery_ts": state.get('last_recovery_ts'),
                }
                for cam_id, state in self.camera_recovery_state.items()
            }
            
            return {
                'recording': True,
                'match_id': self.current_match_id,
                'duration': duration,
                'cameras': cameras,
                'protected': duration < self.protection_seconds,
                'require_all_cameras': self.require_all_cameras,
                'degraded': bool(self.degraded_cameras),
                'degraded_cameras': self.degraded_cameras.copy(),
                'camera_recovery': camera_recovery,
            }
    
    def start_recording(self, match_id: str, force: bool = False, process_after_recording: bool = False) -> Dict:
        """
        Start dual-camera recording

        Args:
            match_id: Unique match identifier
            force: Force start even if already recording
            process_after_recording: Enable post-processing (merge + re-encode) when stopped

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

            self._init_recovery_state()
            
            # Start both cameras
            started_cameras = []
            failed_cameras = []
            
            for cam_id in self.camera_ids:
                try:
                    output_pattern = self._build_output_pattern(match_dir, cam_id)
                    quality_preset = self._get_recording_quality_preset()

                    # Build pipeline with quality preset
                    pipeline_str = build_recording_pipeline(cam_id, output_pattern, quality_preset=quality_preset)
                    logger.info(f"Building recording pipeline for cam{cam_id} with quality preset: {quality_preset}")
                    
                    # Create pipeline
                    pipeline_name = f'recording_cam{cam_id}'
                    
                    def on_eos(name, metadata):
                        logger.info(f"Pipeline {name} received EOS")
                    
                    def on_error(name, error, debug, metadata, camera_id=cam_id, match_id=match_id):
                        logger.error(f"Pipeline {name} error: {error}, debug: {debug}")
                        self._handle_pipeline_error(camera_id, match_id, error, debug)
                    
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
            
            # Strict dual-camera mode: rollback partial start to avoid asymmetric recordings.
            if self.require_all_cameras and failed_cameras:
                logger.error(
                    "Strict dual-camera mode enabled: rolling back partial start "
                    "(started=%s, failed=%s)",
                    started_cameras,
                    failed_cameras,
                )
                for cam_id in started_cameras:
                    pipeline_name = f'recording_cam{cam_id}'
                    try:
                        self.gst_manager.stop_pipeline(pipeline_name, wait_for_eos=False, timeout=1.0)
                    except Exception as stop_error:
                        logger.warning(
                            "Failed to stop partially started camera %s during rollback: %s",
                            cam_id,
                            stop_error,
                        )
                    finally:
                        self.gst_manager.remove_pipeline(pipeline_name)

                return {
                    'success': False,
                    'message': 'Failed to start all required cameras',
                    'cameras_started': [],
                    'cameras_failed': failed_cameras,
                    'require_all_cameras': True
                }

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
            self.process_after_recording = process_after_recording

            # Persist state
            self._save_state()
            
            return {
                'success': True,
                'message': f'Recording started for match: {match_id}',
                'match_id': match_id,
                'cameras_started': started_cameras,
                'cameras_failed': failed_cameras,
                'require_all_cameras': self.require_all_cameras
            }
    
    def _stop_recording_internal(self, force: bool = False) -> Dict[str, Any]:
        """
        Internal method to stop recording
        
        Args:
            force: Skip protection check
            
        Returns:
            Dict with stop details
        """
        if self.current_match_id is None:
            return {
                "success": False,
                "message": "No active recording",
                "graceful_stop": False,
                "camera_stop_results": {},
            }
        
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
        camera_stop_results = {}
        for cam_id in self.camera_ids:
            pipeline_name = f'recording_cam{cam_id}'
            try:
                # Graceful stop with EOS, forcing NULL state after configured timeout.
                if hasattr(self.gst_manager, "stop_pipeline_with_details"):
                    details = self.gst_manager.stop_pipeline_with_details(
                        pipeline_name,
                        wait_for_eos=True,
                        timeout=self.stop_eos_timeout_seconds,
                    )
                else:
                    # Backward-compatibility path for tests/stubs without the new API.
                    success = self.gst_manager.stop_pipeline(
                        pipeline_name,
                        wait_for_eos=True,
                        timeout=self.stop_eos_timeout_seconds,
                    )
                    details = {
                        "success": bool(success),
                        "eos_received": bool(success),
                        "timed_out": False,
                        "error": None if success else "stop_pipeline returned False",
                    }
                logger.info(f"Camera {cam_id} recording stopped")
                camera_stop_results[f"camera_{cam_id}"] = details
                # Remove pipeline from memory to allow fresh start next time
                self.gst_manager.remove_pipeline(pipeline_name)
            except Exception as e:
                logger.error(f"Failed to stop camera {cam_id}: {e}")
                camera_stop_results[f"camera_{cam_id}"] = {
                    "success": False,
                    "eos_received": False,
                    "timed_out": False,
                    "error": str(e),
                }
        
        # Trigger post-processing if enabled
        should_process = self.process_after_recording
        match_id_for_processing = self.current_match_id

        # Clear state
        self.current_match_id = None
        self.recording_start_time = None
        self.process_after_recording = False
        self._init_recovery_state()
        self._clear_state()

        # Start post-processing in background (after state is cleared)
        if should_process:
            logger.info(f"Triggering post-processing for {match_id_for_processing}")
            try:
                from post_processing_service import get_post_processing_service
                post_service = get_post_processing_service()
                post_service.process_recording_async(match_id_for_processing)
            except Exception as e:
                logger.error(f"Failed to start post-processing: {e}")

        graceful_stop = bool(camera_stop_results) and all(
            details.get("success") and details.get("eos_received", False)
            for details in camera_stop_results.values()
        )
        success = bool(camera_stop_results) and all(
            details.get("success")
            for details in camera_stop_results.values()
        )

        return {
            "success": success,
            "message": "Recording stopped successfully" if success else "Recording stop completed with camera errors",
            "graceful_stop": graceful_stop,
            "camera_stop_results": camera_stop_results,
        }

    def check_recording_health(self) -> Dict:
        """Check whether the active recording is producing healthy segment files."""
        if not self.current_match_id:
            return {"healthy": True, "message": "No active recording"}

        try:
            segments_dir = self.base_recordings_dir / self.current_match_id / "segments"
            if not segments_dir.exists():
                return {"healthy": False, "message": "Segments directory does not exist"}

            segments = list(segments_dir.glob("*.mp4")) + list(segments_dir.glob("*.mkv"))
            recording_age = time.time() - self.recording_start_time if self.recording_start_time else 0
            recovery_attempts = {
                f"camera_{cam_id}": self.camera_recovery_state.get(cam_id, {}).get("attempts", 0)
                for cam_id in self.camera_ids
            }

            if not segments:
                if recording_age > 10:
                    return {
                        "healthy": False,
                        "message": "No segments after 10 seconds",
                        "recovery_attempts": recovery_attempts,
                    }
                return {
                    "healthy": True,
                    "message": "Recording just started",
                    "recovery_attempts": recovery_attempts,
                }

            issues = []
            now = time.time()
            for cam_id in self.camera_ids:
                pipeline_name = f"recording_cam{cam_id}"
                pipeline_info = self.gst_manager.get_pipeline_status(pipeline_name)
                if pipeline_info is None:
                    issues.append(f"cam{cam_id}: Pipeline missing")
                elif pipeline_info.state.value != "running":
                    issues.append(f"cam{cam_id}: Pipeline state {pipeline_info.state.value}")

                cam_segments = [segment for segment in segments if f"cam{cam_id}_" in segment.name]
                if not cam_segments:
                    if recording_age > 20:
                        issues.append(f"cam{cam_id}: No segment files after 20 seconds")
                    continue

                latest = max(cam_segments, key=lambda path: path.stat().st_mtime)
                size = latest.stat().st_size
                age = time.time() - latest.stat().st_mtime

                if size == 0 and age > 10:
                    issues.append(f"cam{cam_id}: Zero-byte file")
                elif size < 1024 * 1024 and age > 30:
                    issues.append(f"cam{cam_id}: File too small ({size} bytes)")

                index_match = re.search(r"_(\d+)\.(?:mp4|mkv)$", latest.name)
                latest_index = int(index_match.group(1)) if index_match else None
                previous = self.health_last_segment_snapshot.get(cam_id)
                if previous:
                    prev_index = previous.get("index")
                    if (
                        latest.name != previous.get("name")
                        and latest_index is not None
                        and prev_index is not None
                        and latest_index < prev_index
                    ):
                        issues.append(
                            f"cam{cam_id}: Segment index regressed ({latest_index} < {prev_index})"
                        )

                    if (
                        latest.name == previous.get("name")
                        and (now - previous.get("checked_at", now)) > 20
                        and size <= previous.get("size", 0)
                        and age > 20
                    ):
                        issues.append(f"cam{cam_id}: Segment not growing (size={size})")

                self.health_last_segment_snapshot[cam_id] = {
                    "name": latest.name,
                    "size": size,
                    "mtime": latest.stat().st_mtime,
                    "index": latest_index,
                    "checked_at": now,
                }

                recovery_state = self.camera_recovery_state.get(cam_id, {})
                if recovery_state.get("failed_permanently"):
                    issues.append(f"cam{cam_id}: Recovery exhausted")

            if issues:
                return {
                    "healthy": False,
                    "message": ", ".join(issues),
                    "issues": issues,
                    "recovery_attempts": recovery_attempts,
                }

            return {
                "healthy": True,
                "message": "Recording healthy",
                "recovery_attempts": recovery_attempts,
            }
        except Exception as e:
            logger.error(f"Error checking recording health: {e}")
            return {"healthy": False, "message": f"Health check error: {e}"}
    
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
                stop_result = self._stop_recording_internal(force=force)

                if stop_result.get("success"):
                    return {
                        'success': True,
                        'message': 'Recording stopped successfully',
                        'graceful_stop': stop_result.get("graceful_stop", False),
                        'camera_stop_results': stop_result.get("camera_stop_results", {}),
                    }

                return {
                    'success': False,
                    'message': stop_result.get("message", "Recording stop completed with errors"),
                    'graceful_stop': stop_result.get("graceful_stop", False),
                    'camera_stop_results': stop_result.get("camera_stop_results", {}),
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

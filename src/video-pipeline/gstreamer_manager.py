"""
Thread-safe GStreamer pipeline manager.

Runs GLib.MainLoop in a background thread to handle all GStreamer operations.
Provides thread-safe interface for pipeline control from API threads.
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import threading
import logging
import time
from typing import Optional, Dict, Callable, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

# Initialize GStreamer
Gst.init(None)

logger = logging.getLogger(__name__)


class PipelineState(Enum):
    """Pipeline state enum"""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class PipelineStatus:
    """Pipeline status information"""
    state: PipelineState
    start_time: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class GStreamerManager:
    """
    Singleton manager for all GStreamer pipelines.

    Runs a single GLib.MainLoop in a dedicated thread to handle all pipeline events.
    Provides thread-safe methods to control pipelines from API threads.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.loop = None
        self.loop_thread = None
        self.running = False

        # Pipeline registry: name -> (pipeline, state, callbacks)
        self.pipelines: Dict[str, Dict] = {}
        self.pipelines_lock = threading.Lock()

        # Start the GLib main loop
        self._start_mainloop()

        logger.info("GStreamerManager initialized")

    def _start_mainloop(self):
        """Start GLib.MainLoop in background thread"""
        def run_loop():
            self.loop = GLib.MainLoop()
            logger.info("GLib.MainLoop starting")
            self.running = True
            try:
                self.loop.run()
            except Exception as e:
                logger.error(f"MainLoop error: {e}")
            finally:
                self.running = False
                logger.info("GLib.MainLoop stopped")

        self.loop_thread = threading.Thread(target=run_loop, daemon=True, name="GStreamer-MainLoop")
        self.loop_thread.start()

        # Wait for loop to be ready
        timeout = 5
        start = time.time()
        while not self.running and (time.time() - start) < timeout:
            time.sleep(0.01)

        if not self.running:
            raise RuntimeError("Failed to start GLib.MainLoop")

    def create_pipeline(
        self,
        name: str,
        pipeline_description: str,
        on_eos: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Create and register a pipeline.

        Args:
            name: Unique pipeline identifier
            pipeline_description: GStreamer pipeline string
            on_eos: Callback for EOS events
            on_error: Callback for error events
            metadata: Additional pipeline metadata

        Returns:
            True if pipeline created successfully
        """
        with self.pipelines_lock:
            if name in self.pipelines:
                logger.warning(f"Pipeline '{name}' already exists")
                return False

            try:
                # Parse pipeline
                pipeline = Gst.parse_launch(pipeline_description)
                if not pipeline:
                    logger.error(f"Failed to create pipeline '{name}'")
                    return False

                # Set up bus watch
                bus = pipeline.get_bus()
                bus.add_signal_watch()

                def on_message(bus, message):
                    t = message.type
                    if t == Gst.MessageType.EOS:
                        logger.info(f"Pipeline '{name}': EOS received")
                        if on_eos:
                            metadata_ref = self.pipelines.get(name, {}).get('metadata', {})
                            try:
                                on_eos(name, metadata_ref)
                            except TypeError:
                                on_eos(name)
                    elif t == Gst.MessageType.ERROR:
                        err, debug = message.parse_error()
                        logger.error(f"Pipeline '{name}': {err.message}")
                        logger.debug(f"Pipeline '{name}': Debug info: {debug}")
                        if on_error:
                            metadata_ref = self.pipelines.get(name, {}).get('metadata', {})
                            try:
                                on_error(name, str(err), debug, metadata_ref)
                            except TypeError:
                                try:
                                    on_error(name, str(err))
                                except TypeError:
                                    on_error(name)
                        self._update_pipeline_state(name, PipelineState.ERROR, str(err))
                    elif t == Gst.MessageType.WARNING:
                        warn, debug = message.parse_warning()
                        logger.warning(f"Pipeline '{name}': {warn.message}")
                    elif t == Gst.MessageType.STATE_CHANGED:
                        if message.src == pipeline:
                            old, new, pending = message.parse_state_changed()
                            logger.debug(f"Pipeline '{name}': State changed {old.value_nick} -> {new.value_nick}")

                bus.connect("message", on_message)

                # Register pipeline
                self.pipelines[name] = {
                    'pipeline': pipeline,
                    'state': PipelineState.IDLE,
                    'start_time': None,
                    'error': None,
                    'metadata': metadata or {},
                    'on_eos': on_eos,
                    'on_error': on_error
                }

                logger.info(f"Pipeline '{name}' created successfully")
                return True

            except Exception as e:
                logger.error(f"Failed to create pipeline '{name}': {e}")
                return False

    def _update_pipeline_state(self, name: str, state: PipelineState, error: Optional[str] = None):
        """Update pipeline state (internal)"""
        with self.pipelines_lock:
            if name in self.pipelines:
                self.pipelines[name]['state'] = state
                if error:
                    self.pipelines[name]['error'] = error

    def start_pipeline(self, name: str) -> bool:
        """Start a pipeline"""
        with self.pipelines_lock:
            if name not in self.pipelines:
                logger.error(f"Pipeline '{name}' not found")
                return False

            pipe_data = self.pipelines[name]
            pipeline = pipe_data['pipeline']

            if pipe_data['state'] == PipelineState.RUNNING:
                logger.warning(f"Pipeline '{name}' already running")
                return True

            try:
                logger.info(f"Starting pipeline '{name}'")
                pipe_data['state'] = PipelineState.STARTING
                pipe_data['start_time'] = datetime.utcnow()
                pipe_data['error'] = None

                ret = pipeline.set_state(Gst.State.PLAYING)
                if ret == Gst.StateChangeReturn.FAILURE:
                    logger.error(f"Failed to start pipeline '{name}'")
                    pipe_data['state'] = PipelineState.ERROR
                    pipe_data['error'] = "State change to PLAYING failed"
                    return False

                pipe_data['state'] = PipelineState.RUNNING
                logger.info(f"Pipeline '{name}' started successfully")
                return True

            except Exception as e:
                logger.error(f"Exception starting pipeline '{name}': {e}")
                pipe_data['state'] = PipelineState.ERROR
                pipe_data['error'] = str(e)
                return False

    def _stop_pipeline_internal(self, name: str, wait_for_eos: bool = True, timeout: float = 5.0) -> Dict[str, Any]:
        """Stop a pipeline and return detailed stop metadata."""
        with self.pipelines_lock:
            if name not in self.pipelines:
                logger.error(f"Pipeline '{name}' not found")
                return {
                    "success": False,
                    "eos_received": False,
                    "timed_out": False,
                    "error": "pipeline_not_found",
                }

            pipe_data = self.pipelines[name]
            pipeline = pipe_data['pipeline']

            if pipe_data['state'] == PipelineState.IDLE:
                logger.warning(f"Pipeline '{name}' already stopped")
                return {
                    "success": True,
                    "eos_received": False,
                    "timed_out": False,
                    "error": None,
                }

            eos_received = False
            timed_out = False
            try:
                logger.info(f"Stopping pipeline '{name}' (wait_for_eos={wait_for_eos})")
                pipe_data['state'] = PipelineState.STOPPING

                if wait_for_eos:
                    # Send EOS to pipeline for clean shutdown
                    pipeline.send_event(Gst.Event.new_eos())

                    # Wait for EOS or timeout
                    start = time.time()
                    bus = pipeline.get_bus()
                    while (time.time() - start) < timeout:
                        msg = bus.timed_pop_filtered(
                            int(0.1 * Gst.SECOND),
                            Gst.MessageType.EOS | Gst.MessageType.ERROR
                        )
                        if msg:
                            if msg.type == Gst.MessageType.EOS:
                                logger.info(f"Pipeline '{name}': EOS received during stop")
                                eos_received = True
                                break
                            if msg.type == Gst.MessageType.ERROR:
                                err, _ = msg.parse_error()
                                logger.warning(f"Pipeline '{name}': Error during EOS: {err.message}")
                                break

                    if wait_for_eos and not eos_received:
                        timed_out = True
                        logger.warning(
                            "Pipeline '%s': EOS wait timed out after %.2fs; forcing NULL state",
                            name,
                            timeout,
                        )

                # Set to NULL state
                ret = pipeline.set_state(Gst.State.NULL)
                if ret == Gst.StateChangeReturn.FAILURE:
                    logger.warning(f"Failed to set pipeline '{name}' to NULL state")

                pipe_data['state'] = PipelineState.IDLE
                pipe_data['start_time'] = None
                logger.info(f"Pipeline '{name}' stopped successfully")
                return {
                    "success": True,
                    "eos_received": eos_received,
                    "timed_out": timed_out,
                    "error": None,
                }

            except Exception as e:
                logger.error(f"Exception stopping pipeline '{name}': {e}")
                # Force to NULL on error
                try:
                    pipeline.set_state(Gst.State.NULL)
                except Exception:
                    pass
                pipe_data['state'] = PipelineState.ERROR
                pipe_data['error'] = str(e)
                return {
                    "success": False,
                    "eos_received": False,
                    "timed_out": False,
                    "error": str(e),
                }

    def stop_pipeline(self, name: str, wait_for_eos: bool = True, timeout: float = 5.0) -> bool:
        """
        Stop a pipeline gracefully.

        Args:
            name: Pipeline name
            wait_for_eos: Send EOS and wait for clean shutdown
            timeout: Max time to wait for EOS (seconds)

        Returns:
            True if stopped successfully
        """
        details = self._stop_pipeline_internal(name, wait_for_eos=wait_for_eos, timeout=timeout)
        return bool(details.get("success"))

    def stop_pipeline_with_details(self, name: str, wait_for_eos: bool = True, timeout: float = 5.0) -> Dict[str, Any]:
        """Stop a pipeline gracefully and return EOS/timeout details."""
        return self._stop_pipeline_internal(name, wait_for_eos=wait_for_eos, timeout=timeout)

    def remove_pipeline(self, name: str) -> bool:
        """Remove and cleanup a pipeline"""
        with self.pipelines_lock:
            if name not in self.pipelines:
                logger.warning(f"Pipeline '{name}' not found for removal")
                return False

            pipe_data = self.pipelines[name]
            pipeline = pipe_data['pipeline']

            # Stop if running
            if pipe_data['state'] in (PipelineState.RUNNING, PipelineState.STARTING):
                self.stop_pipeline(name, wait_for_eos=False, timeout=1.0)

            # Cleanup
            try:
                bus = pipeline.get_bus()
                bus.remove_signal_watch()
                pipeline.set_state(Gst.State.NULL)
            except Exception as e:
                logger.warning(f"Error during pipeline '{name}' cleanup: {e}")

            # Remove from registry
            del self.pipelines[name]
            logger.info(f"Pipeline '{name}' removed")
            return True

    def get_pipeline_status(self, name: str) -> Optional[PipelineStatus]:
        """Get pipeline status"""
        with self.pipelines_lock:
            if name not in self.pipelines:
                return None

            pipe_data = self.pipelines[name]
            return PipelineStatus(
                state=pipe_data['state'],
                start_time=pipe_data['start_time'],
                error_message=pipe_data['error'],
                metadata=pipe_data['metadata'].copy()
            )

    def list_pipelines(self) -> Dict[str, PipelineStatus]:
        """List all registered pipelines"""
        with self.pipelines_lock:
            return {
                name: PipelineStatus(
                    state=pipe_data['state'],
                    start_time=pipe_data['start_time'],
                    error_message=pipe_data['error'],
                    metadata=pipe_data['metadata'].copy()
                )
                for name, pipe_data in self.pipelines.items()
            }

    def is_running(self, name: str) -> bool:
        """Check if pipeline is running"""
        status = self.get_pipeline_status(name)
        return status and status.state == PipelineState.RUNNING

    def shutdown(self):
        """Shutdown the manager and all pipelines"""
        logger.info("Shutting down GStreamerManager")

        # Stop all pipelines
        with self.pipelines_lock:
            pipeline_names = list(self.pipelines.keys())

        for name in pipeline_names:
            self.remove_pipeline(name)

        # Stop main loop
        if self.loop and self.running:
            self.loop.quit()

        # Wait for loop thread
        if self.loop_thread and self.loop_thread.is_alive():
            self.loop_thread.join(timeout=2.0)

        logger.info("GStreamerManager shutdown complete")


# Global singleton instance
_manager_instance = None

def get_manager() -> GStreamerManager:
    """Get the global GStreamerManager instance"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = GStreamerManager()
    return _manager_instance

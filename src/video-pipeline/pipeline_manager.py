#!/usr/bin/env python3
"""
Pipeline Manager - System-level mutex for camera resources.

Ensures absolute mutual exclusion between recording and preview modes.
Uses file-based locking for persistence across crashes and restarts.
"""

import os
import fcntl
import json
import time
import logging
from enum import Enum
from typing import Optional, Dict
from datetime import datetime
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


class PipelineMode(Enum):
    """Pipeline operation modes"""
    IDLE = "idle"
    PREVIEW = "preview"
    RECORDING = "recording"
    CALIBRATION = "calibration"  # Special preview mode


class PipelineManager:
    """
    Singleton manager for pipeline resource allocation.

    Provides system-level mutex to ensure only one mode can use cameras at a time.
    Lock state persists across process restarts and crashes.
    """

    _instance = None
    _lock = threading.Lock()

    LOCK_DIR = Path("/var/lock/footballvision")
    LOCK_FILE = LOCK_DIR / "camera.lock"
    STATE_FILE = LOCK_DIR / "pipeline_state.json"

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
        self._ensure_lock_dir()
        self._file_lock = None
        self._current_mode = PipelineMode.IDLE
        self._lock_holder = None
        self._lock_time = None

        # Clean up any stale state on startup
        self._cleanup_stale_locks()

        logger.info("PipelineManager initialized")

    def _ensure_lock_dir(self):
        """Create lock directory if it doesn't exist"""
        try:
            self.LOCK_DIR.mkdir(parents=True, exist_ok=True)
            # Set permissions to allow all users (for www-data/mislav)
            os.chmod(self.LOCK_DIR, 0o777)
        except Exception as e:
            logger.error(f"Failed to create lock directory: {e}")
            # Fall back to /tmp if /var/lock is not writable
            self.LOCK_DIR = Path("/tmp/footballvision")
            self.LOCK_FILE = self.LOCK_DIR / "camera.lock"
            self.STATE_FILE = self.LOCK_DIR / "pipeline_state.json"
            self.LOCK_DIR.mkdir(parents=True, exist_ok=True)
            os.chmod(self.LOCK_DIR, 0o777)

    def _cleanup_stale_locks(self):
        """Clean up stale locks from previous runs"""
        try:
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE, 'r') as f:
                    state = json.load(f)

                # Check if lock is stale (older than 5 minutes)
                if 'lock_time' in state:
                    lock_time = datetime.fromisoformat(state['lock_time'])
                    age = (datetime.now() - lock_time).total_seconds()
                    if age > 300:  # 5 minutes
                        logger.warning(f"Cleaning up stale lock from {state.get('holder', 'unknown')} (age: {age:.0f}s)")
                        self._release_lock_internal()

        except Exception as e:
            logger.error(f"Error cleaning up stale locks: {e}")
            # Remove corrupted state file
            if self.STATE_FILE.exists():
                self.STATE_FILE.unlink()

    def acquire_lock(self, mode: PipelineMode, holder: str, force: bool = False, timeout: float = 5.0) -> bool:
        """
        Acquire exclusive lock for pipeline mode.

        Args:
            mode: The pipeline mode requesting the lock
            holder: Identifier for who is requesting the lock
            force: If True, forcefully take the lock even if held
            timeout: Maximum time to wait for lock (seconds)

        Returns:
            True if lock acquired, False otherwise
        """
        if mode == PipelineMode.IDLE:
            logger.error("Cannot acquire lock for IDLE mode")
            return False

        # First check current state to see if lock is held
        current_state = self.get_state()

        # If not idle and not force, check if we can acquire
        if current_state.get('mode') != 'idle' and not force:
            # Check if same holder trying to re-acquire (idempotent)
            if current_state.get('mode') == mode.value and current_state.get('holder') == holder:
                logger.info(f"Lock already held for same mode/holder: {mode.value}/{holder}")
                return True

            # Different holder or mode - cannot acquire without force
            logger.warning(f"Cannot acquire lock for {mode.value}/{holder} - currently held by {current_state.get('holder')} in {current_state.get('mode')} mode")
            return False

        # If force, release existing lock first
        if force and current_state.get('mode') != 'idle':
            logger.warning(f"Force releasing lock from {current_state.get('holder')}")
            self._force_release()

        # Now try to acquire the lock
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Ensure lock file exists
                if not self.LOCK_FILE.exists():
                    self.LOCK_FILE.touch(mode=0o666)

                # Open for exclusive access
                lock_fd = os.open(str(self.LOCK_FILE), os.O_RDWR)

                # Try non-blocking lock
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

                    # Got the lock! Keep the file descriptor open
                    if self._file_lock:
                        try:
                            os.close(self._file_lock)
                        except:
                            pass

                    self._file_lock = lock_fd
                    self._current_mode = mode
                    self._lock_holder = holder
                    self._lock_time = datetime.now()

                    # Write state
                    self._write_state()

                    logger.info(f"Lock acquired for {mode.value} by {holder}")
                    return True

                except IOError:
                    # Lock is held by someone else - shouldn't happen if state check was correct
                    os.close(lock_fd)
                    logger.debug(f"Lock file is held by another process")
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error acquiring lock: {e}")
                time.sleep(0.1)

        logger.warning(f"Failed to acquire lock for {mode.value} after {timeout}s")
        return False

    def release_lock(self, holder: str) -> bool:
        """
        Release the pipeline lock.

        Args:
            holder: The holder releasing the lock (must match current holder)

        Returns:
            True if lock released, False otherwise
        """
        current_state = self.get_state()

        # Check if this holder owns the lock
        if current_state.get('holder') != holder and current_state.get('mode') != 'idle':
            logger.warning(f"{holder} tried to release lock held by {current_state.get('holder', 'unknown')}")
            return False

        return self._release_lock_internal()

    def _release_lock_internal(self) -> bool:
        """Internal method to release lock"""
        try:
            if self._file_lock:
                # Release the lock
                fcntl.flock(self._file_lock, fcntl.LOCK_UN)
                # Close the file descriptor
                os.close(self._file_lock)
                self._file_lock = None

            self._current_mode = PipelineMode.IDLE
            self._lock_holder = None
            self._lock_time = None

            # Update state file
            self._write_state()

            logger.info("Lock released")
            return True

        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
            return False

    def _force_release(self):
        """Forcefully release lock (used with force=True)"""
        try:
            # Kill any file locks by removing the lock file
            if self.LOCK_FILE.exists():
                self.LOCK_FILE.unlink()

            # Clear state
            self._current_mode = PipelineMode.IDLE
            self._lock_holder = None
            self._lock_time = None
            self._file_lock = None

            # Update state file
            self._write_state()

            logger.info("Lock forcefully released")

        except Exception as e:
            logger.error(f"Error force releasing lock: {e}")

    def check_lock(self, mode: PipelineMode) -> bool:
        """
        Check if lock can be acquired for given mode.

        Args:
            mode: The mode to check

        Returns:
            True if lock is available or held by same mode
        """
        current_state = self.get_state()
        current_mode = current_state.get('mode', 'idle')

        if current_mode == 'idle':
            return True

        if current_mode == mode.value:
            return True

        return False

    def get_state(self) -> Dict:
        """
        Get current lock state.

        Returns:
            Dict with mode, holder, and lock_time
        """
        try:
            if self.STATE_FILE.exists():
                with open(self.STATE_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error reading state file: {e}")

        return {
            'mode': 'idle',
            'holder': None,
            'lock_time': None
        }

    def _write_state(self):
        """Write current state to file"""
        try:
            state = {
                'mode': self._current_mode.value,
                'holder': self._lock_holder,
                'lock_time': self._lock_time.isoformat() if self._lock_time else None,
                'pid': os.getpid()
            }

            # Write atomically
            temp_file = self.STATE_FILE.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)

            temp_file.replace(self.STATE_FILE)

            # Set permissions for all users
            os.chmod(self.STATE_FILE, 0o666)

        except Exception as e:
            logger.error(f"Error writing state file: {e}")

    def wait_for_idle(self, timeout: float = 10.0) -> bool:
        """
        Wait for pipeline to become idle.

        Args:
            timeout: Maximum time to wait

        Returns:
            True if idle, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            state = self.get_state()
            if state.get('mode') == 'idle':
                return True
            time.sleep(0.1)

        return False


# Singleton instance
pipeline_manager = PipelineManager()
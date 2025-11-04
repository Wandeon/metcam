"""
Frame Synchronizer for Dual-Camera Panorama Stitching

Handles synchronization of frames from cam0 and cam1 using timestamp matching.
Ensures frames are temporally aligned before stitching.
"""

import time
import logging
from collections import deque
from typing import Optional, Tuple, Dict
import numpy as np

logger = logging.getLogger(__name__)


class FrameSynchronizer:
    """Synchronizes frames from dual cameras using timestamps"""

    def __init__(self, buffer_size: int = 4, tolerance_ms: float = 33.0):
        """
        Initialize frame synchronizer

        Args:
            buffer_size: Number of frames to buffer per camera
            tolerance_ms: Maximum time difference for frame matching (ms)
        """
        self.buffer_size = buffer_size
        self.tolerance_ms = tolerance_ms
        self.tolerance_ns = int(tolerance_ms * 1e6)  # Convert to nanoseconds

        # Ring buffers for each camera: store (frame, timestamp_ns)
        self.cam0_buffer = deque(maxlen=buffer_size)
        self.cam1_buffer = deque(maxlen=buffer_size)

        # Statistics
        self.stats = {
            'matched_frames': 0,
            'dropped_cam0': 0,
            'dropped_cam1': 0,
            'avg_time_diff_ms': 0.0,
            'total_time_diff_ms': 0.0
        }

        logger.info(f"FrameSynchronizer initialized: buffer_size={buffer_size}, tolerance={tolerance_ms}ms")

    def add_frame(self, camera_id: int, frame: np.ndarray, timestamp_ns: int) -> None:
        """
        Add frame to camera buffer

        Args:
            camera_id: Camera identifier (0 or 1)
            frame: Frame image data
            timestamp_ns: Frame timestamp in nanoseconds
        """
        if camera_id == 0:
            self.cam0_buffer.append((frame, timestamp_ns))
        elif camera_id == 1:
            self.cam1_buffer.append((frame, timestamp_ns))
        else:
            logger.warning(f"Invalid camera_id: {camera_id}. Expected 0 or 1.")

    def get_synchronized_pair(self) -> Optional[Tuple[np.ndarray, np.ndarray, Dict]]:
        """
        Get synchronized frame pair if available

        Finds the best timestamp match between cam0 and cam1 buffers.
        Returns frames and removes matched frames from buffers.

        Returns:
            Tuple of (cam0_frame, cam1_frame, metadata) if match found, else None
            metadata contains: timestamp_ns, time_diff_ms
        """
        if not self.cam0_buffer or not self.cam1_buffer:
            return None

        best_match = None
        best_diff = float('inf')
        best_indices = None

        # Find best matching pair within tolerance
        for i0, (frame0, ts0) in enumerate(self.cam0_buffer):
            for i1, (frame1, ts1) in enumerate(self.cam1_buffer):
                time_diff = abs(ts1 - ts0)

                if time_diff <= self.tolerance_ns and time_diff < best_diff:
                    best_diff = time_diff
                    best_match = (frame0, frame1, ts0, ts1)
                    best_indices = (i0, i1)

        # If no match found, drop oldest frames
        if best_match is None:
            # Drop the older frame
            ts0 = self.cam0_buffer[0][1]
            ts1 = self.cam1_buffer[0][1]

            if ts0 < ts1:
                self.cam0_buffer.popleft()
                self.stats['dropped_cam0'] += 1
                logger.debug(f"Dropped cam0 frame (no match): ts={ts0}")
            else:
                self.cam1_buffer.popleft()
                self.stats['dropped_cam1'] += 1
                logger.debug(f"Dropped cam1 frame (no match): ts={ts1}")

            return None

        # Extract matched frames
        frame0, frame1, ts0, ts1 = best_match
        i0, i1 = best_indices

        # Remove matched frames and any older frames from buffers
        for _ in range(i0 + 1):
            dropped = self.cam0_buffer.popleft()
            if _ < i0:
                self.stats['dropped_cam0'] += 1
                logger.debug(f"Dropped cam0 frame (older): ts={dropped[1]}")

        for _ in range(i1 + 1):
            dropped = self.cam1_buffer.popleft()
            if _ < i1:
                self.stats['dropped_cam1'] += 1
                logger.debug(f"Dropped cam1 frame (older): ts={dropped[1]}")

        # Update statistics
        time_diff_ms = best_diff / 1e6
        self.stats['matched_frames'] += 1
        self.stats['total_time_diff_ms'] += time_diff_ms
        self.stats['avg_time_diff_ms'] = (
            self.stats['total_time_diff_ms'] / self.stats['matched_frames']
        )

        # Use average timestamp
        avg_timestamp = (ts0 + ts1) // 2

        metadata = {
            'timestamp_ns': avg_timestamp,
            'time_diff_ms': time_diff_ms,
            'cam0_timestamp_ns': ts0,
            'cam1_timestamp_ns': ts1
        }

        logger.debug(f"Synchronized pair: time_diff={time_diff_ms:.2f}ms")

        return frame0, frame1, metadata

    def get_stats(self) -> Dict:
        """
        Return synchronization statistics

        Returns:
            Dictionary containing sync stats including success rate
        """
        stats = self.stats.copy()

        # Calculate sync success rate
        total_frames = (
            stats['matched_frames'] +
            stats['dropped_cam0'] +
            stats['dropped_cam1']
        )

        if total_frames > 0:
            stats['sync_success_rate'] = stats['matched_frames'] / total_frames
        else:
            stats['sync_success_rate'] = 0.0

        stats['buffer_cam0_size'] = len(self.cam0_buffer)
        stats['buffer_cam1_size'] = len(self.cam1_buffer)

        return stats

    def reset(self) -> None:
        """Clear buffers and reset statistics"""
        self.cam0_buffer.clear()
        self.cam1_buffer.clear()

        self.stats = {
            'matched_frames': 0,
            'dropped_cam0': 0,
            'dropped_cam1': 0,
            'avg_time_diff_ms': 0.0,
            'total_time_diff_ms': 0.0
        }

        logger.info("FrameSynchronizer buffers and statistics reset")

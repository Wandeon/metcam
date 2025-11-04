"""
GStreamer Frame Utilities for Panorama Stitching

Provides conversion functions between GStreamer buffers and NumPy arrays.
Handles I420 (YUV 4:2:0) format commonly used in GStreamer pipelines.

This module offers efficient conversion utilities for processing video frames
in a GStreamer-based panorama stitching pipeline.
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst
import numpy as np
import cv2
import logging
from typing import Tuple, Dict, Optional

logger = logging.getLogger(__name__)

# Initialize GStreamer
Gst.init(None)


def gst_sample_to_numpy(sample: Gst.Sample) -> Tuple[Optional[np.ndarray], int, Dict]:
    """
    Convert GStreamer sample to NumPy BGR array.

    Extracts frame data from a GStreamer sample, converts from I420 format
    to BGR for OpenCV/VPI processing, and extracts metadata.

    Args:
        sample: GStreamer sample from appsink

    Returns:
        Tuple of (frame_bgr, timestamp_ns, metadata)
        - frame_bgr: BGR numpy array (H, W, 3) uint8, or None if conversion fails
        - timestamp_ns: PTS timestamp in nanoseconds
        - metadata: Dictionary containing frame information

    Example:
        >>> frame, ts, meta = gst_sample_to_numpy(sample)
        >>> if frame is not None:
        ...     cv2.imshow('Frame', frame)
    """
    metadata = {}

    try:
        if sample is None:
            logger.error("Received None sample")
            return None, 0, metadata

        # Get buffer from sample
        buffer = sample.get_buffer()
        if buffer is None:
            logger.error("Failed to get buffer from sample")
            return None, 0, metadata

        # Get timestamp
        timestamp_ns = buffer.pts
        if timestamp_ns == Gst.CLOCK_TIME_NONE:
            logger.warning("Buffer has no PTS timestamp")
            timestamp_ns = 0

        # Get caps to extract format information
        caps = sample.get_caps()
        if caps is None:
            logger.error("Failed to get caps from sample")
            return None, timestamp_ns, metadata

        structure = caps.get_structure(0)
        width = structure.get_value('width')
        height = structure.get_value('height')
        format_str = structure.get_value('format')

        # Store metadata
        metadata = {
            'width': width,
            'height': height,
            'format': format_str,
            'timestamp_ns': timestamp_ns,
            'buffer_size': buffer.get_size()
        }

        logger.debug(f"Processing frame: {width}x{height}, format={format_str}, "
                    f"pts={timestamp_ns}, size={buffer.get_size()}")

        # Map buffer to access data
        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            logger.error("Failed to map buffer for reading")
            return None, timestamp_ns, metadata

        try:
            # Extract raw data
            data = map_info.data

            # Check expected size for I420 format
            expected_size = width * height * 3 // 2  # I420: Y + U/4 + V/4
            if len(data) < expected_size:
                logger.error(f"Buffer size mismatch: got {len(data)}, expected {expected_size}")
                return None, timestamp_ns, metadata

            # Convert based on format
            if format_str == 'I420':
                frame_bgr = i420_to_bgr(bytes(data[:expected_size]), width, height)
            elif format_str in ['BGR', 'RGB']:
                # Direct conversion for BGR/RGB formats
                frame_np = np.frombuffer(data, dtype=np.uint8)
                frame_np = frame_np.reshape((height, width, 3))
                if format_str == 'RGB':
                    frame_bgr = cv2.cvtColor(frame_np, cv2.COLOR_RGB2BGR)
                else:
                    frame_bgr = frame_np.copy()
            else:
                logger.error(f"Unsupported format: {format_str}")
                return None, timestamp_ns, metadata

            logger.debug(f"Successfully converted frame to BGR: shape={frame_bgr.shape}")
            return frame_bgr, timestamp_ns, metadata

        finally:
            # Always unmap buffer
            buffer.unmap(map_info)

    except Exception as e:
        logger.error(f"Error converting GStreamer sample to numpy: {e}", exc_info=True)
        return None, 0, metadata


def numpy_to_gst_buffer(frame: np.ndarray, timestamp_ns: int) -> Optional[Gst.Buffer]:
    """
    Convert NumPy BGR frame to GStreamer buffer.

    Converts a BGR numpy array to I420 format and wraps it in a GStreamer buffer
    with appropriate PTS timestamp.

    Args:
        frame: BGR frame as numpy array (H, W, 3) uint8
        timestamp_ns: PTS timestamp in nanoseconds

    Returns:
        GStreamer buffer or None if conversion fails

    Example:
        >>> frame = cv2.imread('image.jpg')
        >>> buffer = numpy_to_gst_buffer(frame, 1000000000)
        >>> if buffer is not None:
        ...     appsrc.emit('push-buffer', buffer)
    """
    try:
        if frame is None:
            logger.error("Received None frame")
            return None

        if not isinstance(frame, np.ndarray):
            logger.error(f"Frame must be numpy array, got {type(frame)}")
            return None

        if frame.ndim != 3 or frame.shape[2] != 3:
            logger.error(f"Frame must be (H, W, 3), got shape {frame.shape}")
            return None

        if frame.dtype != np.uint8:
            logger.warning(f"Frame dtype is {frame.dtype}, converting to uint8")
            frame = frame.astype(np.uint8)

        # Convert BGR to I420
        i420_data = bgr_to_i420(frame)

        # Create GStreamer buffer
        buffer = Gst.Buffer.new_allocate(None, len(i420_data), None)

        # Fill buffer with data
        success, map_info = buffer.map(Gst.MapFlags.WRITE)
        if not success:
            logger.error("Failed to map buffer for writing")
            return None

        try:
            map_info.data[:] = i420_data
        finally:
            buffer.unmap(map_info)

        # Set timestamp
        buffer.pts = timestamp_ns
        buffer.dts = Gst.CLOCK_TIME_NONE
        buffer.duration = Gst.CLOCK_TIME_NONE

        logger.debug(f"Created GStreamer buffer: size={len(i420_data)}, pts={timestamp_ns}")
        return buffer

    except Exception as e:
        logger.error(f"Error converting numpy to GStreamer buffer: {e}", exc_info=True)
        return None


def i420_to_bgr(i420_data: bytes, width: int, height: int) -> np.ndarray:
    """
    Convert I420 (YUV 4:2:0) data to BGR.

    I420 format layout:
    - Y plane: width × height bytes (luma)
    - U plane: (width/2) × (height/2) bytes (chroma blue projection)
    - V plane: (width/2) × (height/2) bytes (chroma red projection)

    Args:
        i420_data: Raw I420 bytes
        width: Frame width (must be even)
        height: Frame height (must be even)

    Returns:
        BGR numpy array (H, W, 3) uint8

    Raises:
        ValueError: If dimensions are invalid or data size is incorrect
    """
    try:
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid dimensions: {width}x{height}")

        if width % 2 != 0 or height % 2 != 0:
            raise ValueError(f"Width and height must be even for I420, got {width}x{height}")

        expected_size = width * height * 3 // 2
        if len(i420_data) < expected_size:
            raise ValueError(f"Insufficient data: got {len(i420_data)}, expected {expected_size}")

        # Calculate plane sizes
        y_size = width * height
        uv_size = (width // 2) * (height // 2)

        # Extract planes
        y_plane = np.frombuffer(i420_data[:y_size], dtype=np.uint8).reshape((height, width))
        u_plane = np.frombuffer(i420_data[y_size:y_size + uv_size], dtype=np.uint8).reshape((height // 2, width // 2))
        v_plane = np.frombuffer(i420_data[y_size + uv_size:y_size + 2 * uv_size], dtype=np.uint8).reshape((height // 2, width // 2))

        # Upsample U and V planes to match Y plane size
        u_plane = cv2.resize(u_plane, (width, height), interpolation=cv2.INTER_LINEAR)
        v_plane = cv2.resize(v_plane, (width, height), interpolation=cv2.INTER_LINEAR)

        # Merge planes into YUV image
        yuv_frame = np.stack([y_plane, u_plane, v_plane], axis=2)

        # Convert YUV to BGR
        bgr_frame = cv2.cvtColor(yuv_frame, cv2.COLOR_YUV2BGR)

        logger.debug(f"Converted I420 to BGR: {width}x{height}")
        return bgr_frame

    except Exception as e:
        logger.error(f"Error converting I420 to BGR: {e}", exc_info=True)
        raise


def bgr_to_i420(bgr_frame: np.ndarray) -> bytes:
    """
    Convert BGR frame to I420 format.

    Converts BGR frame to YUV color space and packs into I420 planar format
    suitable for GStreamer buffers.

    Args:
        bgr_frame: BGR numpy array (H, W, 3) uint8

    Returns:
        I420 format bytes

    Raises:
        ValueError: If frame format is invalid
    """
    try:
        if bgr_frame is None or not isinstance(bgr_frame, np.ndarray):
            raise ValueError("Frame must be a numpy array")

        if bgr_frame.ndim != 3 or bgr_frame.shape[2] != 3:
            raise ValueError(f"Frame must be (H, W, 3), got shape {bgr_frame.shape}")

        height, width = bgr_frame.shape[:2]

        if width % 2 != 0 or height % 2 != 0:
            # Crop to even dimensions
            logger.warning(f"Cropping frame from {width}x{height} to even dimensions")
            width = width - (width % 2)
            height = height - (height % 2)
            bgr_frame = bgr_frame[:height, :width]

        # Convert BGR to YUV
        yuv_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2YUV)

        # Extract Y, U, V planes
        y_plane = yuv_frame[:, :, 0]
        u_plane = yuv_frame[:, :, 1]
        v_plane = yuv_frame[:, :, 2]

        # Downsample U and V planes (4:2:0 subsampling)
        u_plane = cv2.resize(u_plane, (width // 2, height // 2), interpolation=cv2.INTER_LINEAR)
        v_plane = cv2.resize(v_plane, (width // 2, height // 2), interpolation=cv2.INTER_LINEAR)

        # Concatenate planes into I420 format
        i420_data = np.concatenate([
            y_plane.flatten(),
            u_plane.flatten(),
            v_plane.flatten()
        ])

        logger.debug(f"Converted BGR to I420: {width}x{height}, size={len(i420_data)}")
        return i420_data.tobytes()

    except Exception as e:
        logger.error(f"Error converting BGR to I420: {e}", exc_info=True)
        raise

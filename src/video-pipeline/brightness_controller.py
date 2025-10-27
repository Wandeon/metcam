#!/usr/bin/env python3
"""
Coordinated Brightness Controller for FootballVision Pro

Manages brightness (exposure/gain) across multiple cameras with:
- 10-second minimum adjustment intervals to prevent flickering
- Synchronized adjustments between cameras (averaged target)
- Histogram-based brightness analysis
- Gradual adjustments to avoid sudden changes
"""

import time
import logging
import threading
import subprocess
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class BrightnessState:
    """Current brightness state for a camera"""
    exposure_time: int  # nanoseconds
    analog_gain: float
    digital_gain: float
    last_adjustment: datetime
    target_brightness: Optional[float] = None  # 0-255 average


class BrightnessController:
    """
    Coordinates brightness across multiple cameras.

    Prevents flickering by:
    - Limiting adjustment frequency (10 seconds minimum)
    - Synchronizing cameras (both adjust to averaged target)
    - Making gradual changes (max 20% per adjustment)
    """

    def __init__(self, adjustment_interval: float = 10.0):
        """
        Args:
            adjustment_interval: Minimum seconds between adjustments
        """
        self.adjustment_interval = adjustment_interval
        self.lock = threading.Lock()

        # Camera states
        self.cameras: Dict[int, BrightnessState] = {}

        # Brightness targets
        self.target_brightness = 128.0  # 0-255, middle gray
        self.brightness_tolerance = 15.0  # Don't adjust if within this range

        # Exposure/gain limits (from nvarguscamerasrc)
        self.exposure_min = 13000  # 13 microseconds
        self.exposure_max = 33000000  # 33 milliseconds (30fps limit)
        self.analog_gain_min = 1.0
        self.analog_gain_max = 16.0
        self.digital_gain_min = 1.0
        self.digital_gain_max = 4.0

        # Adjustment constraints
        self.max_change_percent = 0.20  # Max 20% change per adjustment

        logger.info(f"BrightnessController initialized (interval={adjustment_interval}s)")

    def register_camera(self, camera_id: int, initial_exposure: int = 13000000,
                       initial_analog_gain: float = 4.0, initial_digital_gain: float = 1.0):
        """Register a camera with initial brightness settings"""
        with self.lock:
            self.cameras[camera_id] = BrightnessState(
                exposure_time=initial_exposure,
                analog_gain=initial_analog_gain,
                digital_gain=initial_digital_gain,
                last_adjustment=datetime.now() - timedelta(seconds=self.adjustment_interval)
            )
            logger.info(f"Camera {camera_id} registered: exposure={initial_exposure}ns, "
                       f"gain={initial_analog_gain}x/{initial_digital_gain}x")

    def unregister_camera(self, camera_id: int):
        """Unregister a camera"""
        with self.lock:
            if camera_id in self.cameras:
                del self.cameras[camera_id]
                logger.info(f"Camera {camera_id} unregistered")

    def analyze_frame_brightness(self, frame_path: str) -> Optional[float]:
        """
        Analyze brightness of a frame using ffmpeg.

        Args:
            frame_path: Path to HLS segment or frame

        Returns:
            Average brightness (0-255) or None if analysis failed
        """
        try:
            # Use ffmpeg to extract a frame and analyze brightness
            # signalstats filter provides YAVG (average luminance)
            cmd = [
                'ffmpeg', '-i', frame_path, '-vframes', '1', '-vf',
                'signalstats', '-f', 'null', '-'
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2.0
            )

            # Parse YAVG from output
            for line in result.stderr.split('\n'):
                if 'lavfi.signalstats.YAVG' in line:
                    # Format: [Parsed_signalstats_0 @ 0x...] lavfi.signalstats.YAVG=128.5
                    brightness = float(line.split('YAVG=')[1].split()[0])
                    return brightness

            logger.warning(f"Could not parse brightness from frame: {frame_path}")
            return None

        except subprocess.TimeoutExpired:
            logger.warning(f"Brightness analysis timeout for: {frame_path}")
            return None
        except Exception as e:
            logger.error(f"Error analyzing frame brightness: {e}")
            return None

    def update_camera_brightness(self, camera_id: int, current_brightness: float):
        """
        Update measured brightness for a camera.

        Args:
            camera_id: Camera ID
            current_brightness: Measured average brightness (0-255)
        """
        with self.lock:
            if camera_id not in self.cameras:
                logger.warning(f"Camera {camera_id} not registered")
                return

            self.cameras[camera_id].target_brightness = current_brightness
            logger.debug(f"Camera {camera_id} brightness: {current_brightness:.1f}")

    def should_adjust(self) -> bool:
        """Check if enough time has passed since last adjustment"""
        with self.lock:
            if not self.cameras:
                return False

            # Check if any camera can be adjusted
            now = datetime.now()
            for camera_state in self.cameras.values():
                elapsed = (now - camera_state.last_adjustment).total_seconds()
                if elapsed >= self.adjustment_interval:
                    return True

            return False

    def calculate_coordinated_adjustment(self) -> Optional[Tuple[float, float, float]]:
        """
        Calculate coordinated brightness adjustment for all cameras.

        Uses average of all camera measurements to determine adjustment.

        Returns:
            Tuple of (exposure_multiplier, analog_gain_multiplier, digital_gain_multiplier)
            or None if no adjustment needed
        """
        with self.lock:
            if not self.cameras:
                return None

            # Get average current brightness across all cameras
            brightness_readings = [
                cam.target_brightness
                for cam in self.cameras.values()
                if cam.target_brightness is not None
            ]

            if not brightness_readings:
                return None

            avg_brightness = sum(brightness_readings) / len(brightness_readings)

            # Check if adjustment needed
            brightness_error = self.target_brightness - avg_brightness

            if abs(brightness_error) < self.brightness_tolerance:
                logger.debug(f"Brightness OK: {avg_brightness:.1f} (target: {self.target_brightness:.1f})")
                return None

            # Calculate adjustment factor
            # Positive error = need to increase brightness
            # Negative error = need to decrease brightness
            brightness_ratio = self.target_brightness / max(avg_brightness, 1.0)

            # Clamp to max change percent
            max_ratio = 1.0 + self.max_change_percent
            min_ratio = 1.0 - self.max_change_percent
            brightness_ratio = max(min_ratio, min(max_ratio, brightness_ratio))

            # Prefer adjusting exposure over gain (better noise characteristics)
            # Split adjustment: 70% exposure, 30% analog gain
            exposure_multiplier = brightness_ratio ** 0.7
            analog_gain_multiplier = brightness_ratio ** 0.3
            digital_gain_multiplier = 1.0  # Keep digital gain constant

            logger.info(f"Brightness adjustment: {avg_brightness:.1f} -> {self.target_brightness:.1f} "
                       f"(exposure: {exposure_multiplier:.3f}x, gain: {analog_gain_multiplier:.3f}x)")

            return (exposure_multiplier, analog_gain_multiplier, digital_gain_multiplier)

    def apply_adjustment(self, camera_id: int, exposure_mult: float,
                        analog_gain_mult: float, digital_gain_mult: float) -> Dict[str, float]:
        """
        Apply brightness adjustment to a camera.

        Args:
            camera_id: Camera ID
            exposure_mult: Exposure time multiplier
            analog_gain_mult: Analog gain multiplier
            digital_gain_mult: Digital gain multiplier

        Returns:
            Dict with new settings: {exposure, analog_gain, digital_gain}
        """
        with self.lock:
            if camera_id not in self.cameras:
                logger.warning(f"Camera {camera_id} not registered")
                return {}

            camera = self.cameras[camera_id]

            # Calculate new values
            new_exposure = int(camera.exposure_time * exposure_mult)
            new_analog_gain = camera.analog_gain * analog_gain_mult
            new_digital_gain = camera.digital_gain * digital_gain_mult

            # Clamp to valid ranges
            new_exposure = max(self.exposure_min, min(self.exposure_max, new_exposure))
            new_analog_gain = max(self.analog_gain_min, min(self.analog_gain_max, new_analog_gain))
            new_digital_gain = max(self.digital_gain_min, min(self.digital_gain_max, new_digital_gain))

            # Update state
            camera.exposure_time = new_exposure
            camera.analog_gain = new_analog_gain
            camera.digital_gain = new_digital_gain
            camera.last_adjustment = datetime.now()

            logger.info(f"Camera {camera_id} adjusted: exposure={new_exposure}ns, "
                       f"gain={new_analog_gain:.2f}x/{new_digital_gain:.2f}x")

            return {
                'exposure': new_exposure,
                'analog_gain': new_analog_gain,
                'digital_gain': new_digital_gain
            }

    def adjust_all_cameras(self) -> Dict[int, Dict[str, float]]:
        """
        Perform coordinated brightness adjustment on all cameras.

        Returns:
            Dict mapping camera_id to new settings
        """
        if not self.should_adjust():
            return {}

        adjustment = self.calculate_coordinated_adjustment()
        if adjustment is None:
            return {}

        exposure_mult, analog_gain_mult, digital_gain_mult = adjustment

        results = {}
        with self.lock:
            camera_ids = list(self.cameras.keys())

        for camera_id in camera_ids:
            new_settings = self.apply_adjustment(
                camera_id, exposure_mult, analog_gain_mult, digital_gain_mult
            )
            if new_settings:
                results[camera_id] = new_settings

        return results

    def get_camera_settings(self, camera_id: int) -> Optional[Dict[str, float]]:
        """Get current brightness settings for a camera"""
        with self.lock:
            if camera_id not in self.cameras:
                return None

            camera = self.cameras[camera_id]
            return {
                'exposure': camera.exposure_time,
                'analog_gain': camera.analog_gain,
                'digital_gain': camera.digital_gain
            }

    def get_status(self) -> Dict:
        """Get controller status for all cameras"""
        with self.lock:
            now = datetime.now()
            cameras_status = {}

            for camera_id, camera in self.cameras.items():
                elapsed = (now - camera.last_adjustment).total_seconds()
                cameras_status[camera_id] = {
                    'exposure_ns': camera.exposure_time,
                    'analog_gain': camera.analog_gain,
                    'digital_gain': camera.digital_gain,
                    'current_brightness': camera.target_brightness,
                    'seconds_since_adjustment': elapsed,
                    'can_adjust': elapsed >= self.adjustment_interval
                }

            return {
                'adjustment_interval': self.adjustment_interval,
                'target_brightness': self.target_brightness,
                'cameras': cameras_status
            }


# Global singleton instance
_controller_instance: Optional[BrightnessController] = None
_controller_lock = threading.Lock()


def get_brightness_controller() -> BrightnessController:
    """Get or create the global BrightnessController instance"""
    global _controller_instance

    if _controller_instance is None:
        with _controller_lock:
            if _controller_instance is None:
                _controller_instance = BrightnessController(adjustment_interval=10.0)

    return _controller_instance

"""
Configuration Manager for Panorama Stitching

Handles loading, saving, and validation of panorama configuration.
Provides safe defaults and graceful error handling for missing or corrupted configs.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class PanoramaConfigManager:
    """Manages panorama configuration and calibration data"""

    DEFAULT_CONFIG = {
        "version": "1.0.0",
        "enabled": False,
        "calibration": {
            "calibrated": False,
            "homography_cam1_to_cam0": None,
            "overlap_region": {"start_x": 2200, "end_x": 2880, "width": 680},
            "blend_width": 150,
            "quality_score": 0.0,
            "calibration_date": None
        },
        "output": {
            "width": 3840,
            "height": 1315,
            "fps": 30
        },
        "performance": {
            "preview_fps_target": 15,
            "use_vic_backend": True,
            "use_cuda_backend": True,
            "buffer_size": 4,
            "sync_tolerance_ms": 33.0
        }
    }

    def __init__(self, config_path: str = "/home/mislav/footballvision-pro/config/panorama_config.json"):
        """
        Initialize configuration manager

        Args:
            config_path: Path to panorama configuration file
        """
        self.config_path = Path(config_path)
        self.config: Dict = {}
        self._load_or_create_config()

    def _load_or_create_config(self) -> None:
        """Load configuration from file or create with defaults"""
        try:
            if self.config_path.exists():
                self.config = self.load_config()
                logger.info(f"Loaded panorama config from {self.config_path}")
            else:
                logger.warning(f"Config file not found at {self.config_path}, creating with defaults")
                self.config = self.DEFAULT_CONFIG.copy()
                self.save_config(self.config)
        except Exception as e:
            logger.error(f"Failed to load config, using defaults: {e}")
            self.config = self.DEFAULT_CONFIG.copy()

    def load_config(self) -> Dict:
        """
        Load configuration from file

        Returns:
            Dict: Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is malformed
        """
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)

            # Validate and merge with defaults (ensure all keys exist)
            validated_config = self._validate_and_merge(config)
            return validated_config

        except FileNotFoundError:
            logger.error(f"Config file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading config: {e}")
            raise

    def _validate_and_merge(self, config: Dict) -> Dict:
        """
        Validate configuration and merge with defaults for missing keys

        Args:
            config: Configuration to validate

        Returns:
            Dict: Validated configuration with defaults for missing keys
        """
        # Deep merge with defaults
        validated = self.DEFAULT_CONFIG.copy()

        # Update top-level keys
        for key in ['version', 'enabled']:
            if key in config:
                validated[key] = config[key]

        # Update nested sections
        for section in ['calibration', 'output', 'performance']:
            if section in config and isinstance(config[section], dict):
                validated[section].update(config[section])

        # Validate critical fields
        self._validate_types(validated)

        return validated

    def _validate_types(self, config: Dict) -> None:
        """
        Validate configuration field types

        Args:
            config: Configuration to validate

        Raises:
            ValueError: If any field has invalid type
        """
        # Check boolean fields
        if not isinstance(config['enabled'], bool):
            raise ValueError("'enabled' must be boolean")

        # Check calibration fields
        if not isinstance(config['calibration']['calibrated'], bool):
            raise ValueError("'calibration.calibrated' must be boolean")

        if config['calibration']['homography_cam1_to_cam0'] is not None:
            homography = config['calibration']['homography_cam1_to_cam0']
            if not (isinstance(homography, list) and len(homography) == 3):
                raise ValueError("'homography_cam1_to_cam0' must be 3x3 matrix or None")

        # Check numeric fields
        if not isinstance(config['output']['width'], int) or config['output']['width'] <= 0:
            raise ValueError("'output.width' must be positive integer")

        if not isinstance(config['performance']['preview_fps_target'], (int, float)):
            raise ValueError("'performance.preview_fps_target' must be numeric")

    def save_config(self, config: Dict) -> bool:
        """
        Save configuration to file

        Args:
            config: Configuration dictionary to save

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Validate before saving
            self._validate_types(config)

            # Write to file with pretty formatting
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)

            # Update in-memory config
            self.config = config

            logger.info(f"Saved panorama config to {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def is_calibrated(self) -> bool:
        """
        Check if system is calibrated

        Returns:
            bool: True if calibrated and homography matrix exists
        """
        calibration = self.config.get('calibration', {})
        return (
            calibration.get('calibrated', False) and
            calibration.get('homography_cam1_to_cam0') is not None
        )

    def get_homography(self) -> Optional[np.ndarray]:
        """
        Get homography matrix as numpy array

        Returns:
            Optional[np.ndarray]: 3x3 homography matrix, or None if not calibrated
        """
        if not self.is_calibrated():
            return None

        try:
            homography_list = self.config['calibration']['homography_cam1_to_cam0']
            homography = np.array(homography_list, dtype=np.float32)

            # Validate shape
            if homography.shape != (3, 3):
                logger.error(f"Invalid homography shape: {homography.shape}, expected (3, 3)")
                return None

            return homography

        except Exception as e:
            logger.error(f"Failed to convert homography to numpy array: {e}")
            return None

    def save_calibration(
        self,
        homography: np.ndarray,
        quality_score: float,
        overlap_region: Dict
    ) -> bool:
        """
        Save calibration data to configuration

        Args:
            homography: 3x3 homography matrix as numpy array
            quality_score: Calibration quality score (0.0-1.0)
            overlap_region: Dictionary with 'start_x', 'end_x', 'width' keys

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate inputs
            if homography.shape != (3, 3):
                raise ValueError(f"Homography must be 3x3, got {homography.shape}")

            if not 0.0 <= quality_score <= 1.0:
                raise ValueError(f"Quality score must be 0.0-1.0, got {quality_score}")

            required_keys = {'start_x', 'end_x', 'width'}
            if not required_keys.issubset(overlap_region.keys()):
                raise ValueError(f"Overlap region missing keys: {required_keys - overlap_region.keys()}")

            # Convert homography to list for JSON serialization
            homography_list = homography.tolist()

            # Update calibration section
            self.config['calibration'].update({
                'calibrated': True,
                'homography_cam1_to_cam0': homography_list,
                'overlap_region': overlap_region,
                'quality_score': quality_score,
                'calibration_date': datetime.utcnow().isoformat() + 'Z'
            })

            # Save to file
            return self.save_config(self.config)

        except Exception as e:
            logger.error(f"Failed to save calibration: {e}")
            return False

    def clear_calibration(self) -> bool:
        """
        Clear calibration data from configuration

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.config['calibration'].update({
                'calibrated': False,
                'homography_cam1_to_cam0': None,
                'quality_score': 0.0,
                'calibration_date': None
            })

            return self.save_config(self.config)

        except Exception as e:
            logger.error(f"Failed to clear calibration: {e}")
            return False

    def get_config(self) -> Dict:
        """
        Get current configuration

        Returns:
            Dict: Current configuration dictionary
        """
        return self.config.copy()

    def update_config(self, updates: Dict) -> bool:
        """
        Update configuration with partial updates

        Args:
            updates: Dictionary with updates to apply

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Deep merge updates
            for key, value in updates.items():
                if key in self.config and isinstance(value, dict) and isinstance(self.config[key], dict):
                    self.config[key].update(value)
                else:
                    self.config[key] = value

            return self.save_config(self.config)

        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return False

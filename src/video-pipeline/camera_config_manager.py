#!/usr/bin/env python3
"""
Camera Configuration Manager
Handles loading, saving, and managing camera configurations and presets
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import threading


class CameraConfigManager:
    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            repo_root = Path(__file__).resolve().parents[2]
            config_path = repo_root / "config" / "camera_config.json"

        self.config_path = Path(config_path)
        self.config_lock = threading.RLock()  # Use RLock for reentrant locking
        self._config = None

        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Load configuration
        self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        with self.config_lock:
            try:
                with open(self.config_path, 'r') as f:
                    self._config = json.load(f)
                print(f"✅ Loaded camera configuration from {self.config_path}")
                return self._config
            except FileNotFoundError:
                print(f"⚠️  Config file not found, creating default configuration")
                self._config = self._get_default_config()
                self.save_config()
                return self._config
            except json.JSONDecodeError as e:
                print(f"❌ Error parsing config file: {e}")
                print(f"⚠️  Using default configuration")
                self._config = self._get_default_config()
                return self._config

    def save_config(self) -> bool:
        """Save current configuration to JSON file"""
        with self.config_lock:
            try:
                with open(self.config_path, 'w') as f:
                    json.dump(self._config, f, indent=2)
                print(f"✅ Saved camera configuration to {self.config_path}")
                return True
            except Exception as e:
                print(f"❌ Error saving config: {e}")
                return False

    def get_camera_config(self, camera_id: int) -> Dict[str, Any]:
        """Get configuration for a specific camera"""
        with self.config_lock:
            camera_key = str(camera_id)
            if camera_key not in self._config.get('cameras', {}):
                # Return default config for this camera
                return self._get_default_camera_config(camera_id)
            return self._config['cameras'][camera_key].copy()

    def get_all_cameras_config(self) -> Dict[str, Any]:
        """Get configuration for all cameras"""
        with self.config_lock:
            return self._config.get('cameras', {}).copy()

    def update_camera_config(self, camera_id: int, params: Dict[str, Any]) -> bool:
        """Update configuration for a specific camera"""
        with self.config_lock:
            camera_key = str(camera_id)

            # Ensure cameras section exists
            if 'cameras' not in self._config:
                self._config['cameras'] = {}

            # Get current config or default
            if camera_key not in self._config['cameras']:
                self._config['cameras'][camera_key] = self._get_default_camera_config(camera_id)

            # Update with new params
            current = self._config['cameras'][camera_key]

            # Update individual fields
            if 'rotation' in params:
                current['rotation'] = float(params['rotation'])

            if 'crop' in params:
                current['crop'] = params['crop']

            if 'correction_type' in params:
                current['correction_type'] = params['correction_type']

            if 'correction_params' in params:
                current['correction_params'] = params['correction_params']

            return self.save_config()

    def list_presets(self) -> List[Dict[str, str]]:
        """List all available presets"""
        with self.config_lock:
            presets = self._config.get('presets', {})
            return [
                {
                    'name': name,
                    'description': preset.get('description', ''),
                }
                for name, preset in presets.items()
            ]

    def get_preset(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific preset configuration"""
        with self.config_lock:
            presets = self._config.get('presets', {})
            return presets.get(preset_name, None)

    def save_preset(self, preset_name: str, description: str = "") -> bool:
        """Save current camera configuration as a preset"""
        with self.config_lock:
            if 'presets' not in self._config:
                self._config['presets'] = {}

            self._config['presets'][preset_name] = {
                'name': preset_name,
                'description': description,
                'cameras': self._config.get('cameras', {}).copy()
            }

            return self.save_config()

    def load_preset(self, preset_name: str) -> bool:
        """Load a preset and apply it to current configuration"""
        with self.config_lock:
            preset = self.get_preset(preset_name)
            if preset is None:
                print(f"❌ Preset '{preset_name}' not found")
                return False

            # Apply preset cameras to current config
            self._config['cameras'] = preset.get('cameras', {}).copy()

            return self.save_config()

    def delete_preset(self, preset_name: str) -> bool:
        """Delete a preset"""
        with self.config_lock:
            if 'presets' not in self._config:
                return False

            if preset_name not in self._config['presets']:
                return False

            # Don't allow deleting the default preset
            if preset_name == 'default':
                print("❌ Cannot delete 'default' preset")
                return False

            del self._config['presets'][preset_name]
            return self.save_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure"""
        return {
            "version": "1.0",
            "cameras": {
                "0": self._get_default_camera_config(0),
                "1": self._get_default_camera_config(1)
            },
            "presets": {
                "default": {
                    "name": "Default Settings",
                    "description": "Standard match recording setup",
                    "cameras": {
                        "0": self._get_default_camera_config(0),
                        "1": self._get_default_camera_config(1)
                    }
                }
            }
        }

    def _get_default_camera_config(self, camera_id: int) -> Dict[str, Any]:
        """Get default configuration for a camera"""
        # Use current values from camera_rotation_config as defaults
        if camera_id == 0:
            return {
                "rotation": 18.0,
                "crop": {
                    "left": 557,
                    "right": 403,
                    "top": 227,
                    "bottom": 313
                },
                "correction_type": "barrel",
                "correction_params": {
                    "k1": 0.15,
                    "k2": 0.05
                }
            }
        else:  # camera_id == 1
            return {
                "rotation": -18.0,
                "crop": {
                    "left": 595,
                    "right": 365,
                    "top": 335,
                    "bottom": 205
                },
                "correction_type": "barrel",
                "correction_params": {
                    "k1": 0.15,
                    "k2": 0.05
                }
            }


# Global instance
_config_manager = None


def get_config_manager() -> CameraConfigManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = CameraConfigManager()
    return _config_manager


if __name__ == "__main__":
    # Test the config manager
    manager = CameraConfigManager()

    print("\n=== Current Configuration ===")
    for cam_id in [0, 1]:
        config = manager.get_camera_config(cam_id)
        print(f"\nCamera {cam_id}:")
        print(f"  Rotation: {config['rotation']}°")
        print(f"  Crop: {config['crop']}")
        print(f"  Correction: {config['correction_type']}")
        print(f"  Params: {config['correction_params']}")

    print("\n=== Available Presets ===")
    for preset in manager.list_presets():
        print(f"  - {preset['name']}: {preset['description']}")

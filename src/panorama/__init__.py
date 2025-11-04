"""
FootballVision Pro - Panorama Stitching Module

GPU-accelerated panorama stitching using NVIDIA VPI 3.2.4 for Jetson Orin Nano.
Combines dual IMX477 cameras into a seamless wide-angle view.

Key Features:
- VPI hardware acceleration (VIC + CUDA backends)
- Real-time stitching for preview (15-20 FPS)
- Post-processing for recordings (5-8 FPS full quality)
- Camera calibration with homography calculation
- Zero-copy NVMM operations

Architecture:
- vpi_stitcher: Core GPU stitching engine using VPI
- panorama_service: Main service following FootballVision patterns
- calibration_service: One-time camera alignment setup
- frame_synchronizer: Dual-camera frame synchronization
- config_manager: Configuration and calibration management

Version: 1.0.0
Created: 2025-11-04
"""

__version__ = "1.0.0"
__author__ = "FootballVision Pro Team"

# Module exports
from .vpi_stitcher import VPIStitcher

__all__ = [
    "VPIStitcher",
]

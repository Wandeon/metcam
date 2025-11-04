#!/usr/bin/env python3
"""
Unit tests for VPIStitcher

Tests the GPU-accelerated panorama stitching functionality.
Note: Requires NVIDIA VPI 3.2.4 and GPU hardware for full testing.
"""

import unittest
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import vpi
    VPI_AVAILABLE = True
except ImportError:
    VPI_AVAILABLE = False
    print("Warning: VPI not available, some tests will be skipped")

from vpi_stitcher import VPIStitcher, StitchingStats


class TestStitchingStats(unittest.TestCase):
    """Test the StitchingStats dataclass"""

    def test_stats_initialization(self):
        """Test statistics initialization"""
        stats = StitchingStats()
        self.assertEqual(stats.frames_stitched, 0)
        self.assertEqual(stats.avg_stitch_time_ms, 0.0)
        self.assertEqual(stats.fps, 0.0)

    def test_stats_update(self):
        """Test statistics update"""
        stats = StitchingStats()
        stats.update(50.0, warp_time_ms=20.0, blend_time_ms=15.0, conversion_time_ms=5.0)

        self.assertEqual(stats.frames_stitched, 1)
        self.assertEqual(stats.avg_stitch_time_ms, 50.0)
        self.assertEqual(stats.last_stitch_time_ms, 50.0)
        self.assertEqual(stats.fps, 20.0)  # 1000 / 50
        self.assertEqual(stats.warp_time_ms, 20.0)
        self.assertEqual(stats.blend_time_ms, 15.0)

    def test_stats_to_dict(self):
        """Test statistics conversion to dictionary"""
        stats = StitchingStats()
        stats.update(33.33)

        result = stats.to_dict()
        self.assertIsInstance(result, dict)
        self.assertIn('frames_stitched', result)
        self.assertIn('avg_stitch_time_ms', result)
        self.assertIn('fps', result)
        self.assertEqual(result['frames_stitched'], 1)


@unittest.skipIf(not VPI_AVAILABLE, "VPI not available")
class TestVPIStitcher(unittest.TestCase):
    """Test the VPIStitcher class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a simple homography matrix (identity)
        self.homography = np.eye(3, dtype=np.float32)

        # Small test dimensions for faster testing
        self.output_width = 1280
        self.output_height = 720

    def test_initialization_calibrated(self):
        """Test stitcher initialization in calibrated mode"""
        stitcher = VPIStitcher(
            output_width=self.output_width,
            output_height=self.output_height,
            homography=self.homography
        )

        self.assertTrue(stitcher.calibrated_mode)
        self.assertEqual(stitcher.output_width, self.output_width)
        self.assertEqual(stitcher.output_height, self.output_height)
        self.assertIsNotNone(stitcher.homography)

    def test_initialization_uncalibrated(self):
        """Test stitcher initialization in uncalibrated mode"""
        stitcher = VPIStitcher(
            output_width=self.output_width,
            output_height=self.output_height
        )

        self.assertFalse(stitcher.calibrated_mode)
        self.assertIsNone(stitcher.homography)

    def test_update_homography(self):
        """Test homography matrix update"""
        stitcher = VPIStitcher(
            output_width=self.output_width,
            output_height=self.output_height
        )

        self.assertFalse(stitcher.calibrated_mode)

        # Update with new homography
        new_homography = np.array([
            [1.0, 0.1, 10],
            [0.0, 1.0, 5],
            [0.0, 0.0, 1.0]
        ], dtype=np.float32)

        stitcher.update_homography(new_homography)

        self.assertTrue(stitcher.calibrated_mode)
        np.testing.assert_array_equal(stitcher.homography, new_homography)

    def test_update_homography_invalid_shape(self):
        """Test homography update with invalid shape"""
        stitcher = VPIStitcher(
            output_width=self.output_width,
            output_height=self.output_height
        )

        invalid_homography = np.eye(2, dtype=np.float32)

        with self.assertRaises(ValueError):
            stitcher.update_homography(invalid_homography)

    def test_get_stats(self):
        """Test statistics retrieval"""
        stitcher = VPIStitcher(
            output_width=self.output_width,
            output_height=self.output_height,
            homography=self.homography
        )

        stats = stitcher.get_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn('frames_stitched', stats)
        self.assertIn('avg_stitch_time_ms', stats)
        self.assertIn('fps', stats)

    def test_reset_stats(self):
        """Test statistics reset"""
        stitcher = VPIStitcher(
            output_width=self.output_width,
            output_height=self.output_height,
            homography=self.homography
        )

        # Manually update stats
        stitcher.stats.frames_stitched = 10
        stitcher.stats.avg_stitch_time_ms = 50.0

        # Reset
        stitcher.reset_stats()

        stats = stitcher.get_stats()
        self.assertEqual(stats['frames_stitched'], 0)
        self.assertEqual(stats['avg_stitch_time_ms'], 0.0)

    def test_stitch_frames_invalid_input(self):
        """Test stitching with invalid input shapes"""
        stitcher = VPIStitcher(
            output_width=self.output_width,
            output_height=self.output_height,
            homography=self.homography
        )

        # Create frames with mismatched shapes
        frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
        frame2 = np.zeros((720, 1280, 3), dtype=np.uint8)

        with self.assertRaises(ValueError):
            stitcher.stitch_frames(frame1, frame2)

    def test_stitch_frames_invalid_channels(self):
        """Test stitching with invalid channel count"""
        stitcher = VPIStitcher(
            output_width=self.output_width,
            output_height=self.output_height,
            homography=self.homography
        )

        # Create grayscale frames (2D instead of 3D)
        frame1 = np.zeros((480, 640), dtype=np.uint8)
        frame2 = np.zeros((480, 640), dtype=np.uint8)

        with self.assertRaises(ValueError):
            stitcher.stitch_frames(frame1, frame2)

    def test_repr(self):
        """Test string representation"""
        stitcher = VPIStitcher(
            output_width=self.output_width,
            output_height=self.output_height,
            homography=self.homography
        )

        repr_str = repr(stitcher)
        self.assertIn('VPIStitcher', repr_str)
        self.assertIn(str(self.output_width), repr_str)
        self.assertIn(str(self.output_height), repr_str)


class TestVPIStitcherIntegration(unittest.TestCase):
    """Integration tests that work without VPI (using mocks if needed)"""

    def test_basic_workflow(self):
        """Test basic stitcher workflow"""
        # Create homography
        homography = np.eye(3, dtype=np.float32)

        # Initialize stitcher
        stitcher = VPIStitcher(
            output_width=1920,
            output_height=1080,
            homography=homography,
            blend_width=150
        )

        # Check initial state
        self.assertTrue(stitcher.calibrated_mode)
        self.assertEqual(stitcher.blend_width, 150)

        # Get initial stats
        stats = stitcher.get_stats()
        self.assertEqual(stats['frames_stitched'], 0)

        # Clean up
        stitcher.cleanup()
        self.assertFalse(stitcher._vpi_initialized)


if __name__ == '__main__':
    unittest.main()

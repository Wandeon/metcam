#!/usr/bin/env python3
"""
VPIStitcher Example Usage

Demonstrates how to use the VPIStitcher class for GPU-accelerated panorama stitching.
This example shows both calibrated and uncalibrated modes.
"""

import numpy as np
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

try:
    from vpi_stitcher import VPIStitcher
    VPI_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import VPIStitcher: {e}")
    VPI_AVAILABLE = False


def example_calibrated_stitching():
    """
    Example: Calibrated stitching with pre-computed homography
    This is the FAST mode (15-20 FPS for preview resolution)
    """
    logger.info("=" * 60)
    logger.info("Example 1: Calibrated Stitching (Fast Mode)")
    logger.info("=" * 60)

    # Pre-computed homography matrix from calibration
    # In production, this would come from calibration_service
    homography = np.array([
        [0.95, 0.05, 50],
        [-0.02, 0.98, 10],
        [0.0, 0.0, 1.0]
    ], dtype=np.float32)

    # Initialize stitcher for preview resolution (fast)
    stitcher = VPIStitcher(
        output_width=1440,
        output_height=960,
        use_vic=True,      # Hardware acceleration
        use_cuda=True,     # GPU blending
        homography=homography,
        blend_width=200    # 200px overlap blending
    )

    logger.info(f"Stitcher created: {stitcher}")

    # Simulate frames from dual cameras (IMX477)
    # In production, these come from GStreamer pipelines
    frame_height, frame_width = 960, 1440
    frame_cam0 = np.random.randint(0, 255, (frame_height, frame_width, 3), dtype=np.uint8)
    frame_cam1 = np.random.randint(0, 255, (frame_height, frame_width, 3), dtype=np.uint8)

    logger.info(f"Input frames: {frame_cam0.shape}")

    try:
        # Stitch frames
        panorama, metadata = stitcher.stitch_frames(frame_cam0, frame_cam1)

        logger.info(f"Stitching successful!")
        logger.info(f"  Output shape: {panorama.shape}")
        logger.info(f"  Stitch time: {metadata['stitch_time_ms']:.2f} ms")
        logger.info(f"  FPS: {metadata['fps']:.2f}")
        logger.info(f"  Timings breakdown:")
        logger.info(f"    - Conversion: {metadata['timings']['conversion_ms']:.2f} ms")
        logger.info(f"    - Warp: {metadata['timings']['warp_ms']:.2f} ms")
        logger.info(f"    - Blend: {metadata['timings']['blend_ms']:.2f} ms")

        # Get cumulative statistics
        stats = stitcher.get_stats()
        logger.info(f"  Statistics: {stats}")

        # Simulate multiple frames
        logger.info("\nProcessing 10 more frames...")
        for i in range(10):
            panorama, metadata = stitcher.stitch_frames(frame_cam0, frame_cam1)

        final_stats = stitcher.get_stats()
        logger.info(f"Final statistics after 11 frames:")
        logger.info(f"  Average FPS: {final_stats['fps']:.2f}")
        logger.info(f"  Average stitch time: {final_stats['avg_stitch_time_ms']:.2f} ms")

    except Exception as e:
        logger.error(f"Stitching failed: {e}", exc_info=True)

    finally:
        # Clean up resources
        stitcher.cleanup()
        logger.info("Stitcher resources cleaned up")


def example_uncalibrated_stitching():
    """
    Example: Uncalibrated stitching without pre-computed homography
    This is the SLOW mode (5-8 FPS for full resolution)
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Uncalibrated Stitching (Slow Mode)")
    logger.info("=" * 60)

    # Initialize stitcher without homography
    stitcher = VPIStitcher(
        output_width=2880,
        output_height=1752,
        use_vic=True,
        use_cuda=True,
        homography=None,  # Uncalibrated mode
        blend_width=250
    )

    logger.info(f"Stitcher created in uncalibrated mode: {stitcher}")
    logger.info(f"Calibrated mode: {stitcher.calibrated_mode}")

    # Later, after calibration is computed, update the homography
    logger.info("\nSimulating calibration process...")
    computed_homography = np.array([
        [0.98, 0.03, 45],
        [-0.01, 0.99, 8],
        [0.0, 0.0, 1.0]
    ], dtype=np.float32)

    stitcher.update_homography(computed_homography)
    logger.info(f"Homography updated, calibrated mode: {stitcher.calibrated_mode}")


def example_full_quality_stitching():
    """
    Example: Full quality stitching for post-processing
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Full Quality Stitching (Post-Processing)")
    logger.info("=" * 60)

    # High-resolution homography from calibration
    homography = np.array([
        [0.96, 0.04, 100],
        [-0.015, 0.985, 20],
        [0.0, 0.0, 1.0]
    ], dtype=np.float32)

    # Full resolution stitcher
    stitcher = VPIStitcher(
        output_width=3840,
        output_height=1315,
        use_vic=True,
        use_cuda=True,
        homography=homography,
        blend_width=300  # Wider blend for smoother transition
    )

    logger.info(f"Full quality stitcher: {stitcher}")

    # High resolution frames (2880×1752 from IMX477)
    frame_height, frame_width = 1752, 2880
    frame_cam0 = np.random.randint(0, 255, (frame_height, frame_width, 3), dtype=np.uint8)
    frame_cam1 = np.random.randint(0, 255, (frame_height, frame_width, 3), dtype=np.uint8)

    logger.info(f"Full resolution input: {frame_cam0.shape}")

    try:
        panorama, metadata = stitcher.stitch_frames(frame_cam0, frame_cam1)

        logger.info(f"Full quality stitching completed:")
        logger.info(f"  Output: {panorama.shape}")
        logger.info(f"  Processing time: {metadata['stitch_time_ms']:.2f} ms")
        logger.info(f"  FPS: {metadata['fps']:.2f}")

    except Exception as e:
        logger.error(f"Full quality stitching failed: {e}", exc_info=True)

    finally:
        stitcher.cleanup()


def example_statistics_tracking():
    """
    Example: Performance statistics tracking
    """
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Statistics Tracking")
    logger.info("=" * 60)

    homography = np.eye(3, dtype=np.float32)
    stitcher = VPIStitcher(
        output_width=1440,
        output_height=960,
        homography=homography
    )

    # Process multiple frames and track stats
    frame_cam0 = np.random.randint(0, 255, (960, 1440, 3), dtype=np.uint8)
    frame_cam1 = np.random.randint(0, 255, (960, 1440, 3), dtype=np.uint8)

    logger.info("Processing 20 frames...")
    for i in range(20):
        panorama, metadata = stitcher.stitch_frames(frame_cam0, frame_cam1)

        if i % 5 == 0:
            stats = stitcher.get_stats()
            logger.info(f"Frame {i+1}: FPS={stats['fps']:.2f}, "
                       f"Avg={stats['avg_stitch_time_ms']:.2f}ms")

    # Final statistics
    final_stats = stitcher.get_stats()
    logger.info(f"\nFinal statistics:")
    logger.info(f"  Total frames: {final_stats['frames_stitched']}")
    logger.info(f"  Average stitch time: {final_stats['avg_stitch_time_ms']:.2f} ms")
    logger.info(f"  Average FPS: {final_stats['fps']:.2f}")
    logger.info(f"  Last frame time: {final_stats['last_stitch_time_ms']:.2f} ms")

    # Reset statistics
    stitcher.reset_stats()
    logger.info("\nStatistics reset")
    reset_stats = stitcher.get_stats()
    logger.info(f"After reset: {reset_stats}")

    stitcher.cleanup()


def main():
    """Run all examples"""
    if not VPI_AVAILABLE:
        logger.error("VPI is not available. Cannot run examples.")
        logger.info("Make sure NVIDIA VPI 3.2.4 is installed on Jetson Orin Nano")
        return

    logger.info("VPIStitcher Examples")
    logger.info("=" * 60)
    logger.info("Note: These examples use synthetic data for demonstration.")
    logger.info("In production, frames come from dual IMX477 camera pipelines.")
    logger.info("=" * 60)

    try:
        # Run examples
        example_calibrated_stitching()
        example_uncalibrated_stitching()
        example_full_quality_stitching()
        example_statistics_tracking()

        logger.info("\n" + "=" * 60)
        logger.info("All examples completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Example execution failed: {e}", exc_info=True)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Example: Process football game recording into panoramic video

Usage:
    python process_game.py \
        --cam0 recordings/game1/cam0.h265 \
        --cam1 recordings/game1/cam1.h265 \
        --output output/game1_panorama.h265 \
        --calibration calibration.yaml \
        --quality high
"""

import argparse
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from processing import create_processor, ProcessingConfig
from processing.optimization.optimizer import PerformanceProfiler


def main():
    parser = argparse.ArgumentParser(
        description='Process dual-camera football recording into panoramic video'
    )

    parser.add_argument('--cam0', required=True, help='Path to camera 0 recording (H.265)')
    parser.add_argument('--cam1', required=True, help='Path to camera 1 recording (H.265)')
    parser.add_argument('--output', required=True, help='Path for output panoramic video')
    parser.add_argument('--calibration', required=True, help='Path to calibration file (YAML)')
    parser.add_argument('--quality', default='high', choices=['low', 'medium', 'high', 'ultra'],
                       help='Quality preset')
    parser.add_argument('--gpu-device', type=int, default=0, help='CUDA device ID')
    parser.add_argument('--batch-size', type=int, default=8, help='Processing batch size')
    parser.add_argument('--no-quality-checks', action='store_true',
                       help='Disable quality checks for faster processing')

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.cam0).exists():
        print(f"Error: Camera 0 recording not found: {args.cam0}")
        return 1

    if not Path(args.cam1).exists():
        print(f"Error: Camera 1 recording not found: {args.cam1}")
        return 1

    if not Path(args.calibration).exists():
        print(f"Error: Calibration file not found: {args.calibration}")
        return 1

    # Create output directory
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("FootballVision Pro - Panoramic Video Processing")
    print("=" * 80)
    print(f"\nInput:")
    print(f"  Camera 0: {args.cam0}")
    print(f"  Camera 1: {args.cam1}")
    print(f"\nOutput:")
    print(f"  Panorama: {args.output}")
    print(f"\nSettings:")
    print(f"  Quality: {args.quality}")
    print(f"  GPU Device: {args.gpu_device}")
    print(f"  Batch Size: {args.batch_size}")
    print(f"  Quality Checks: {'Disabled' if args.no_quality_checks else 'Enabled'}")
    print("\n" + "=" * 80)

    # Create processor
    try:
        processor = create_processor(
            cam0_path=args.cam0,
            cam1_path=args.cam1,
            output_path=args.output,
            calibration_file=args.calibration,
            quality_preset=args.quality,
            gpu_device=args.gpu_device,
            batch_size=args.batch_size,
            enable_quality_checks=not args.no_quality_checks
        )
    except Exception as e:
        print(f"\nError creating processor: {e}")
        return 1

    # Start processing
    print("\nStarting processing...")
    start_time = time.time()

    try:
        # Monitor progress in separate thread
        import threading

        def monitor_progress():
            while True:
                progress, stage = processor.get_progress()
                print(f"\rProgress: {progress*100:.1f}% | Stage: {stage.value:<20}", end='', flush=True)

                if progress >= 1.0:
                    break

                time.sleep(1.0)

        progress_thread = threading.Thread(target=monitor_progress, daemon=True)
        progress_thread.start()

        # Process game
        result = processor.process_game()

        progress_thread.join(timeout=1.0)

        elapsed = time.time() - start_time

        print("\n\n" + "=" * 80)

        if result.success:
            print("Processing completed successfully!")
            print("\nResults:")
            print(f"  Processing time: {result.processing_time:.1f}s ({elapsed/60:.1f} minutes)")
            print(f"  Total frames: {result.total_frames}")
            print(f"  Average FPS: {result.metrics.avg_processing_fps:.1f}")
            print(f"  Output: {result.output_path}")

            if result.metrics.ssim > 0:
                print(f"\nQuality Metrics:")
                print(f"  SSIM: {result.metrics.ssim:.3f}")
                print(f"  Seam Quality: {result.metrics.seam_quality:.3f}")
                print(f"  Temporal Consistency: {result.metrics.temporal_consistency:.3f}")

            if result.warnings:
                print(f"\nWarnings ({len(result.warnings)}):")
                for warning in result.warnings[:5]:
                    print(f"  - {warning}")

        else:
            print("Processing failed!")
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors:
                print(f"  - {error}")

            return 1

        print("=" * 80)

        return 0

    except KeyboardInterrupt:
        print("\n\nProcessing cancelled by user")
        processor.cancel()
        return 1

    except Exception as e:
        print(f"\n\nProcessing error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
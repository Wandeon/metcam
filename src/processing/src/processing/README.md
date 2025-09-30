# FootballVision Pro - Processing Pipeline

GPU-accelerated panoramic video processing for dual IMX477 cameras.

## Components

- **W21 Architecture**: Pipeline orchestration
- **W22 Calibration**: Camera calibration
- **W23 Barrel Correction**: CUDA undistortion
- **W24 Stitching**: Panoramic stitching
- **W25 Color Matching**: Color correction
- **W26 GPU Memory**: Memory management
- **W27 Video Codec**: NVDEC/NVENC
- **W28 Optimizer**: Performance tuning
- **W29 Quality**: QA framework
- **W30 Batch**: Job queue

## Performance Targets

- Processing: < 2 hours for 150min game
- Throughput: 40+ FPS pipeline
- GPU: > 80% utilization
- Quality: SSIM > 0.95

## Usage

```python
# Example processing workflow
processor = PanoramicProcessor(config)
result = processor.process_game()
```

See component READMEs for detailed documentation.
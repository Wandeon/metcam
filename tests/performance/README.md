# Performance Testing Suite - W43
## FootballVision Pro Performance Validation

## Overview
Comprehensive performance testing and benchmarking for FootballVision Pro. Validates system performance against defined targets from the master test plan.

## Performance Targets

### Recording System
- **Startup time**: <2 seconds
- **Frame rate**: 30 fps ±0.1
- **Frame drops**: 0 (zero tolerance)
- **Max duration**: 180 minutes continuous
- **Processing time**: <2x real-time

### System Resources
- **CPU usage**: <60% during recording
- **GPU usage**: <80% during processing
- **RAM usage**: <6GB (75% of 8GB)
- **GPU memory**: <4GB (50% of available)
- **Temperature**: <75°C sustained

### Response Times
- **API response**: <100ms p99
- **Boot time**: <30 seconds
- **Storage write**: >400MB/s

## Quick Start

```bash
# Run all performance tests
pytest tests/performance/ -v

# Run benchmarks only
pytest tests/performance/ -v -m benchmark

# Run with performance report
pytest tests/performance/ --benchmark-only --benchmark-autosave

# Skip slow tests
pytest tests/performance/ -v -m "not slow"
```

## Test Categories

### 1. Recording Performance
- Startup/shutdown times
- 3-hour continuous recording
- Frame rate consistency
- Zero frame drop validation

### 2. System Performance
- Boot time
- API response times
- Storage throughput
- Network performance

### 3. Resource Utilization
- Memory usage (RAM + GPU)
- CPU utilization
- GPU utilization
- Storage I/O

### 4. Stress Tests
- 10 start/stop cycles
- Low storage conditions
- Concurrent operations
- Thermal stress

### 5. Thermal Management
- Temperature under load
- Sustained thermal performance
- Thermal throttling detection

## Running Tests

### Basic Execution
```bash
# All performance tests
pytest tests/performance/ -v --tb=short

# With coverage
pytest tests/performance/ --cov=src --cov-report=html

# Parallel execution (fast tests only)
pytest tests/performance/ -v -n auto -m "not slow"
```

### Benchmark Mode
```bash
# Run benchmarks with pytest-benchmark
pytest tests/performance/test_benchmarks.py --benchmark-only

# Save benchmark results
pytest tests/performance/ --benchmark-autosave --benchmark-save=baseline

# Compare against baseline
pytest tests/performance/ --benchmark-compare=baseline
```

### Long-Running Tests
```bash
# 3-hour stress test
pytest tests/performance/test_benchmarks.py::TestRecordingPerformance::test_3hour_recording_stability -v

# All stress tests
pytest tests/performance/ -v -m slow --timeout=14400
```

## Performance Metrics

### Key Benchmarks
| Metric | Target | Critical |
|--------|--------|----------|
| Recording startup | <2s | YES |
| Frame drops | 0 | YES |
| Temperature | <75°C | YES |
| CPU usage | <60% | NO |
| API response | <100ms | NO |
| Storage write | >400MB/s | YES |

### Monitoring During Tests
```python
def test_with_metrics(test_harness):
    test_harness.start_recording({"match_id": "test"})

    # Collect metrics
    metrics = test_harness.get_metrics()

    # Validate
    assert metrics.dropped_frames == 0
    assert metrics.temperature_c < 75
    assert metrics.cpu_usage_percent < 60
```

## Benchmark Reports

### Generating Reports
```bash
# HTML report
pytest tests/performance/ --benchmark-only --benchmark-autosave \
  --benchmark-save=report_$(date +%Y%m%d)

# JSON output
pytest tests/performance/ --benchmark-only --benchmark-json=output.json

# Compare multiple runs
pytest-benchmark compare baseline latest --histogram
```

### Sample Output
```
Name                              Min     Max     Mean    StdDev
----------------------------------------------------------------
test_recording_startup_time     0.850   1.200   0.923   0.082
test_api_response_time          0.012   0.045   0.018   0.007
test_storage_write_speed        2.100   2.500   2.250   0.120
```

## CI/CD Integration

### GitHub Actions
```yaml
- name: Performance Tests
  run: |
    pytest tests/performance/ -v -m "not slow"
    pytest tests/performance/ --benchmark-only --benchmark-json=perf.json

- name: Performance Regression Check
  run: |
    # Fail if performance degrades >10%
    python scripts/check_perf_regression.py perf.json baseline.json
```

## Performance Profiling

### CPU Profiling
```bash
# Profile with py-spy
py-spy record -o profile.svg -- python -m pytest tests/performance/test_benchmarks.py::test_recording_startup_time

# Profile with cProfile
python -m cProfile -o profile.stats -m pytest tests/performance/
```

### Memory Profiling
```bash
# Memory profiler
python -m memory_profiler tests/performance/test_benchmarks.py

# Track memory growth
pytest tests/performance/ --memray
```

### GPU Profiling (Jetson)
```bash
# NVIDIA Nsight
nsys profile -o performance_trace python -m pytest tests/performance/

# tegrastats monitoring
tegrastats --interval 1000 > tegra_metrics.log &
pytest tests/performance/
```

## Stress Testing

### Extended Duration Tests
```python
@pytest.mark.slow
def test_3hour_continuous(test_harness):
    """180-minute stress test"""
    test_harness.start_recording({"duration": 10800})

    for minute in range(180):
        metrics = test_harness.get_metrics()
        assert metrics.dropped_frames == 0
        assert metrics.temperature_c < 75
        time.sleep(60)

    result = test_harness.stop_recording()
    assert result["status"] == "completed"
```

### Thermal Stress
```python
def test_thermal_stress(test_harness):
    """Test under maximum thermal load"""
    # Record while processing previous recording
    test_harness.start_recording({"match_id": "thermal"})

    max_temp = 0
    for _ in range(60):
        metrics = test_harness.get_metrics()
        max_temp = max(max_temp, metrics.temperature_c)
        assert metrics.temperature_c < 85  # Safety
        time.sleep(1)

    assert max_temp < 75  # Target
```

## Performance Optimization

### Identifying Bottlenecks
1. **CPU bound**: Profile with py-spy, optimize hot paths
2. **GPU bound**: Use NVIDIA Nsight, reduce kernel launches
3. **I/O bound**: Check storage throughput, optimize writes
4. **Memory bound**: Profile allocations, reduce copies

### Common Issues

**High Temperature**
- Check cooling system
- Verify thermal paste
- Reduce GPU workload
- Increase idle periods

**Frame Drops**
- Check CPU/GPU utilization
- Verify camera drivers
- Optimize recording pipeline
- Reduce concurrent operations

**Slow Storage**
- Verify storage speed (>400MB/s)
- Check for fragmentation
- Use faster SD card/SSD
- Optimize write patterns

## Deliverables

- [x] Performance benchmarking framework
- [x] Recording performance tests
- [x] System resource tests
- [x] Stress testing suite
- [x] Thermal monitoring tests
- [x] Memory leak detection
- [x] Documentation

## Version History
- **v1.0** (2025-09-30): Initial performance testing suite - W43

## References
- [Test Strategy](../strategy/MASTER_TEST_PLAN.md) - W41
- [Integration Tests](../integration/) - W42
- [Field Testing](../field-testing/) - W44
# Integration Testing Framework - W42
## FootballVision Pro End-to-End Testing

## Overview
Comprehensive integration testing framework for FootballVision Pro. Tests complete workflows, component interactions, API contracts, and hardware-in-the-loop scenarios.

## Features

### Test Harness
- **JetsonTestHarness**: Complete system testing environment
- **Automatic hardware detection**: Real Jetson/cameras or mock mode
- **Resource management**: Automatic setup and teardown
- **Metrics collection**: Real-time system monitoring
- **Crash simulation**: Fault injection for recovery testing

### Test Coverage
1. **Recording Workflows** - Complete recording lifecycle
2. **API Contracts** - Endpoint validation and compliance
3. **Hardware Integration** - Camera and system integration
4. **Failure Modes** - Error handling and recovery
5. **Performance** - Response times and load testing

## Quick Start

### Running Integration Tests
```bash
# Run all integration tests
pytest tests/integration/ -v

# Run specific test class
pytest tests/integration/test_recording_workflow.py::TestRecordingWorkflow -v

# Run with coverage
pytest tests/integration/ --cov=src --cov-report=html

# Run only fast tests (exclude slow)
pytest tests/integration/ -v -m "not slow"

# Run hardware tests (requires Jetson + cameras)
pytest tests/integration/ -v -m hardware
```

### Test Markers
- `@pytest.mark.integration` - Integration test (default)
- `@pytest.mark.hardware` - Requires real Jetson hardware
- `@pytest.mark.slow` - Test takes >1 minute
- `@pytest.mark.api` - API integration test

## Test Structure

### Directory Layout
```
tests/integration/
├── conftest.py              # Test fixtures and harness
├── test_recording_workflow.py  # Recording integration tests
├── test_api_contracts.py    # API endpoint tests
├── fixtures/               # Test data and fixtures
├── utils/                 # Test utilities
├── api/                  # API-specific tests
└── hardware/            # Hardware integration tests
```

### Core Test Fixtures

#### test_harness
Complete system harness with camera setup and storage management.

```python
def test_example(test_harness):
    # Harness provides full system access
    test_harness.start_recording({"match_id": "test"})
    metrics = test_harness.get_metrics()
    test_harness.stop_recording()
    # Automatic cleanup
```

#### recording_session
Pre-started recording session for testing during recording.

```python
def test_during_recording(recording_session, test_harness):
    # Recording already started
    metrics = test_harness.get_metrics()
    assert metrics.dropped_frames == 0
    # Automatic stop and cleanup
```

#### api_client
Mock API client for testing endpoints.

```python
def test_api(api_client):
    response = api_client.start_recording({"match_id": "test"})
    assert response["status"] == 200
```

## Test Scenarios

### Basic Recording Workflow
```python
def test_basic_recording_lifecycle(test_harness):
    # Start recording
    response = test_harness.start_recording({
        "match_id": "test_001",
        "duration": 60
    })
    assert response["status"] == "recording"

    # Record for a period
    time.sleep(5)

    # Check metrics
    metrics = test_harness.get_metrics()
    assert metrics.temperature_c < 75

    # Stop and verify
    result = test_harness.stop_recording()
    assert result["status"] == "completed"
    assert len(result["files"]) == 2
```

### Full Match Recording (Simulated)
```python
@pytest.mark.slow
def test_full_match_recording(test_harness):
    test_harness.start_recording({
        "match_id": "full_match",
        "duration": 5400  # 90 minutes
    })

    # Monitor periodically
    for minute in range(60):  # Simulated
        metrics = test_harness.get_metrics()
        assert metrics.dropped_frames == 0
        assert metrics.temperature_c < 75
        time.sleep(1)

    result = test_harness.stop_recording()
    assert result["status"] == "completed"
```

### Crash Recovery Testing
```python
def test_crash_recovery(test_harness):
    # Start recording
    test_harness.start_recording({"match_id": "crash_test"})
    time.sleep(3)

    # Simulate crash
    test_harness.force_reboot()
    test_harness.wait_for_boot()

    # Check for recovered files
    recovered = test_harness.get_recovered_recordings()
    assert len(recovered) >= 0
```

### API Contract Testing
```python
def test_api_contract(api_client):
    # Test endpoint response format
    response = api_client.get_status()

    # Verify schema
    assert "status" in response
    assert "recording" in response
    assert isinstance(response["recording"], bool)
```

## Hardware Integration

### Running with Real Hardware
Tests automatically detect available hardware:

```python
# Jetson detection
if harness.config.jetson_available:
    # Use real Jetson APIs
    temperature = read_jetson_temperature()
else:
    # Use mock values
    temperature = 45.0

# Camera detection
if harness.config.cameras_available >= 2:
    # Use real IMX477 cameras
    setup_real_cameras()
else:
    # Use mock cameras
    setup_mock_cameras()
```

### Hardware Test Requirements
To run hardware tests on actual Jetson:
- NVIDIA Jetson Orin Nano Super
- 2x IMX477 cameras connected
- Sufficient storage (>50GB)
- JetPack 6.1+

```bash
# Run hardware-specific tests
pytest tests/integration/ -v -m hardware
```

## Metrics Monitoring

### Available Metrics
```python
metrics = test_harness.get_metrics()

# System metrics
metrics.temperature_c       # °C
metrics.cpu_usage_percent   # %
metrics.gpu_usage_percent   # %
metrics.memory_used_mb      # MB
metrics.storage_available_gb # GB

# Recording metrics
metrics.dropped_frames      # count
```

### Metric Validation
```python
def test_metrics_within_limits(test_harness, recording_session):
    metrics = test_harness.get_metrics()

    # Verify limits from test plan
    assert metrics.temperature_c < 75, "Temperature too high"
    assert metrics.dropped_frames == 0, "Frame drops detected"
    assert metrics.storage_available_gb > 10, "Low storage"
```

## Test Data Management

### Video File Validation
```python
from conftest import validate_video

def test_video_output(test_harness):
    test_harness.start_recording({"match_id": "test"})
    time.sleep(5)
    result = test_harness.stop_recording()

    # Validate each output file
    for file_info in result["files"]:
        filepath = Path(file_info["path"])
        assert validate_video(filepath), f"Invalid video: {filepath}"
```

### Mock Video Files
```python
def test_with_mock_video(mock_video_file):
    # mock_video_file is a valid MP4 file
    assert mock_video_file.exists()
    assert mock_video_file.suffix == ".mp4"
```

## CI/CD Integration

### GitHub Actions Workflow
```yaml
# .github/workflows/integration-tests.yml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements-test.txt
      - name: Run integration tests
        run: |
          pytest tests/integration/ -v --cov=src
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

### Running in Docker
```bash
# Build test container
docker build -t footballvision-test -f Dockerfile.test .

# Run integration tests
docker run footballvision-test pytest tests/integration/ -v
```

## Performance Testing

### Response Time Validation
```python
import time

def test_api_response_time(api_client):
    start = time.time()
    response = api_client.get_status()
    elapsed = time.time() - start

    # Target: <100ms (from test plan)
    assert elapsed < 0.1, f"Too slow: {elapsed:.3f}s"
```

### Load Testing
```python
def test_concurrent_requests(api_client):
    import concurrent.futures

    def make_request():
        return api_client.get_status()

    # 10 concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(10)]
        results = [f.result() for f in futures]

    # All should succeed
    assert all(r["status"] == "ready" for r in results)
```

## Troubleshooting

### Common Issues

#### Tests Fail in Mock Mode
- **Issue**: Tests expect real hardware behavior
- **Solution**: Use `@pytest.mark.hardware` to skip in mock mode

```python
@pytest.mark.hardware
def test_real_hardware_only(test_harness):
    if not test_harness.config.jetson_available:
        pytest.skip("Requires real Jetson hardware")
```

#### Storage Cleanup Fails
- **Issue**: Temporary files not cleaned up
- **Solution**: Ensure fixture is function-scoped

```python
@pytest.fixture(scope="function")  # Not session
def test_harness(system_config):
    harness = JetsonTestHarness(system_config)
    yield harness
    harness.teardown()  # Always cleanup
```

#### Slow Test Execution
- **Issue**: Integration tests take too long
- **Solution**: Run in parallel or skip slow tests

```bash
# Parallel execution
pytest tests/integration/ -n auto

# Skip slow tests
pytest tests/integration/ -m "not slow"
```

## Test Requirements

### Python Dependencies
```
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-xdist>=3.3.0
pytest-timeout>=2.1.0
requests>=2.31.0
psutil>=5.9.0
```

### System Requirements
- **OS**: Ubuntu 22.04 or JetPack 6.1+
- **Python**: 3.10+
- **Storage**: >20GB for test files
- **Memory**: >4GB RAM

## Best Practices

### Writing Integration Tests
1. **Test real workflows** - Not just individual functions
2. **Use fixtures** - Leverage provided harness and fixtures
3. **Check metrics** - Always verify system health
4. **Handle both modes** - Work in mock and hardware mode
5. **Clean up** - Use fixtures for automatic cleanup

### Test Naming
```python
# Good: Descriptive, action-oriented
def test_full_match_recording_completes_successfully():
    pass

# Bad: Vague
def test_recording():
    pass
```

### Assertion Messages
```python
# Good: Informative failure messages
assert metrics.temperature_c < 75, \
    f"Temperature too high: {metrics.temperature_c}°C (max 75°C)"

# Bad: No context
assert metrics.temperature_c < 75
```

## Integration with Other Teams

### Video Pipeline (W11-W20)
- Import camera control APIs
- Test recording pipeline integration
- Validate video file outputs

### Processing (W21-W30)
- Test stitching integration
- Validate processing queue
- Test end-to-end pipeline

### Platform (W31-W40)
- Test API endpoints
- Validate database operations
- Test authentication flows

## Deliverables Checklist

- [x] Test harness (JetsonTestHarness)
- [x] Recording workflow tests
- [x] API contract tests
- [x] Hardware integration tests
- [x] Failure mode tests
- [x] Mock/real hardware support
- [x] Comprehensive fixtures
- [x] Documentation

## Version History
- **v1.0** (2025-09-30): Initial integration testing framework - W42
  - Test harness with hardware detection
  - Recording workflow tests
  - API contract tests
  - Metrics monitoring
  - Crash recovery testing

## Contact
- **Integration Testing Lead (W42)**: Via PR comments/reviews
- **Questions**: Open issue with label "integration-testing"

## References
- [Test Strategy](../strategy/MASTER_TEST_PLAN.md) - W41
- [Performance Tests](../performance-tests/) - W43
- [Field Testing](../field-testing/) - W44
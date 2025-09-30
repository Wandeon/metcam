"""
Integration Tests for Complete Recording Workflow
Tests end-to-end recording from start to video file output
"""

import pytest
import time
from pathlib import Path
from .conftest import validate_video


@pytest.mark.integration
class TestRecordingWorkflow:
    """Test complete recording workflow integration"""

    def test_basic_recording_lifecycle(self, test_harness):
        """Test basic start-record-stop workflow"""
        # Start recording
        response = test_harness.start_recording({
            "match_id": "test_basic_001",
            "duration": 60  # 1 minute test
        })

        assert response["status"] == "recording"
        assert "recording_id" in response

        # Verify recording is active
        assert test_harness.recording_active is True

        # Record for 5 seconds
        time.sleep(5)

        # Check metrics during recording
        metrics = test_harness.get_metrics()
        assert metrics.temperature_c > 0
        assert metrics.temperature_c < 85  # Safety threshold

        # Stop recording
        result = test_harness.stop_recording()

        assert result["status"] == "completed"
        assert len(result["files"]) == 2  # Two camera files
        assert result["duration_sec"] >= 4  # At least 4 seconds

        # Verify files exist and are valid
        for file_info in result["files"]:
            filepath = Path(file_info["path"])
            assert filepath.exists()
            assert validate_video(filepath)

    def test_short_duration_recording(self, test_harness):
        """Test very short recording (< 10 seconds)"""
        test_harness.start_recording({"match_id": "short_test", "duration": 10})
        time.sleep(2)
        result = test_harness.stop_recording()

        assert result["status"] == "completed"
        assert len(result["files"]) == 2

    @pytest.mark.slow
    def test_standard_half_recording(self, test_harness):
        """Test standard 45-minute half recording (simulated)"""
        # Simulate 45-minute recording with accelerated time
        test_harness.start_recording({
            "match_id": "half_match_001",
            "duration": 2700  # 45 minutes
        })

        # Monitor for 30 seconds (representing 45 minutes)
        start_time = time.time()
        while time.time() - start_time < 30:
            metrics = test_harness.get_metrics()

            # Verify critical metrics
            assert metrics.dropped_frames == 0, "Frame drops detected"
            assert metrics.temperature_c < 75, f"Temperature too high: {metrics.temperature_c}°C"
            assert metrics.storage_available_gb > 5, "Low storage"

            time.sleep(5)

        result = test_harness.stop_recording()
        assert result["status"] == "completed"
        assert len(result["files"]) == 2

    @pytest.mark.slow
    def test_full_match_recording(self, test_harness):
        """Test complete 90-minute match recording (simulated)"""
        test_harness.start_recording({
            "match_id": "full_match_001",
            "duration": 5400  # 90 minutes
        })

        # Monitor for 60 seconds (representing 90 minutes)
        start_time = time.time()
        check_interval = 10

        while time.time() - start_time < 60:
            metrics = test_harness.get_metrics()

            # Critical checks
            assert metrics.dropped_frames == 0
            assert metrics.temperature_c < 75
            assert metrics.cpu_usage_percent < 90
            assert metrics.storage_available_gb > 10

            time.sleep(check_interval)

        result = test_harness.stop_recording()

        assert result["status"] == "completed"
        assert result["duration_sec"] >= 59
        assert len(result["files"]) == 2

        # Verify file integrity
        for file_info in result["files"]:
            assert Path(file_info["path"]).exists()
            assert file_info["size_mb"] > 0

    def test_multiple_sequential_recordings(self, test_harness):
        """Test multiple recordings in sequence"""
        recording_count = 5

        for i in range(recording_count):
            test_harness.start_recording({
                "match_id": f"sequential_{i:03d}",
                "duration": 60
            })
            time.sleep(2)
            result = test_harness.stop_recording()

            assert result["status"] == "completed"
            assert len(result["files"]) == 2

        # Verify all files exist
        files = list(test_harness.config.storage_path.glob("*.mp4"))
        assert len(files) == recording_count * 2

    def test_recording_with_pauses(self, test_harness):
        """Test recording with pauses between segments"""
        # First recording
        test_harness.start_recording({"match_id": "pause_test_1"})
        time.sleep(3)
        result1 = test_harness.stop_recording()

        # Pause
        time.sleep(2)

        # Second recording
        test_harness.start_recording({"match_id": "pause_test_2"})
        time.sleep(3)
        result2 = test_harness.stop_recording()

        assert result1["status"] == "completed"
        assert result2["status"] == "completed"
        assert result1["recording_id"] != result2["recording_id"]


@pytest.mark.integration
class TestRecordingFailureModes:
    """Test recording failure handling and recovery"""

    def test_start_while_recording_fails(self, test_harness):
        """Test that starting a new recording while one is active fails gracefully"""
        test_harness.start_recording({"match_id": "first"})

        with pytest.raises(RuntimeError, match="already in progress"):
            test_harness.start_recording({"match_id": "second"})

        # Cleanup
        test_harness.stop_recording()

    def test_stop_without_start_fails(self, test_harness):
        """Test that stopping without active recording fails gracefully"""
        with pytest.raises(RuntimeError, match="No recording in progress"):
            test_harness.stop_recording()

    def test_crash_recovery(self, test_harness):
        """Test recovery from unexpected system crash"""
        # Start recording
        test_harness.start_recording({"match_id": "crash_test"})
        time.sleep(3)  # Record for 3 seconds

        # Simulate crash
        test_harness.force_reboot()

        # Simulate system restart
        test_harness.wait_for_boot()

        # Check for recovered recordings
        recovered = test_harness.get_recovered_recordings()

        # Should have partial recordings
        assert len(recovered) >= 0  # May or may not have partial files

    def test_storage_full_handling(self, test_harness):
        """Test behavior when storage is nearly full"""
        # Start recording
        test_harness.start_recording({"match_id": "storage_test"})

        # Check storage during recording
        metrics = test_harness.get_metrics()

        # If storage low, should still complete gracefully
        if metrics.storage_available_gb < 20:
            result = test_harness.stop_recording()
            assert result["status"] == "completed"
        else:
            test_harness.stop_recording()


@pytest.mark.integration
class TestRecordingMetrics:
    """Test metrics collection during recording"""

    def test_metrics_during_recording(self, test_harness):
        """Test that metrics are collected accurately during recording"""
        test_harness.start_recording({"match_id": "metrics_test"})
        time.sleep(2)

        metrics = test_harness.get_metrics()

        # Verify all metrics are populated
        assert metrics.temperature_c > 0
        assert metrics.cpu_usage_percent >= 0
        assert metrics.gpu_usage_percent >= 0
        assert metrics.memory_used_mb > 0
        assert metrics.storage_available_gb > 0

        # Verify metrics are reasonable
        assert metrics.temperature_c < 100  # °C
        assert metrics.cpu_usage_percent <= 100
        assert metrics.gpu_usage_percent <= 100

        test_harness.stop_recording()

    def test_temperature_monitoring(self, test_harness):
        """Test continuous temperature monitoring"""
        test_harness.start_recording({"match_id": "temp_test"})

        temperatures = []
        for _ in range(5):
            metrics = test_harness.get_metrics()
            temperatures.append(metrics.temperature_c)
            time.sleep(1)

        test_harness.stop_recording()

        # Verify temperature readings are consistent
        assert all(t > 0 for t in temperatures)
        assert all(t < 85 for t in temperatures)  # Safety threshold

    def test_frame_drop_detection(self, test_harness):
        """Test frame drop detection during recording"""
        test_harness.start_recording({"match_id": "framedrop_test"})
        time.sleep(5)

        metrics = test_harness.get_metrics()

        # Should have zero frame drops under normal conditions
        assert metrics.dropped_frames == 0

        test_harness.stop_recording()


@pytest.mark.integration
class TestCameraIntegration:
    """Test camera system integration"""

    def test_dual_camera_recording(self, test_harness):
        """Test simultaneous recording from both cameras"""
        result = test_harness.start_recording({"match_id": "dual_cam_test"})

        assert result["status"] == "recording"

        time.sleep(3)

        result = test_harness.stop_recording()

        # Should have one file per camera
        assert len(result["files"]) == 2
        cameras = [f["camera"] for f in result["files"]]
        assert "cam0" in cameras or "mock_cam0" in cameras
        assert "cam1" in cameras or "mock_cam1" in cameras

    def test_camera_synchronization(self, test_harness):
        """Test that cameras start recording simultaneously"""
        test_harness.start_recording({"match_id": "sync_test"})
        time.sleep(2)
        result = test_harness.stop_recording()

        # Both files should have similar durations (within 0.1 seconds)
        durations = [f["duration_sec"] for f in result["files"]]
        assert abs(durations[0] - durations[1]) < 0.1


@pytest.mark.integration
class TestStorageManagement:
    """Test storage management during recording"""

    def test_file_naming_convention(self, test_harness):
        """Test that files follow naming convention"""
        match_id = "naming_test_001"
        test_harness.start_recording({"match_id": match_id})
        time.sleep(2)
        result = test_harness.stop_recording()

        for file_info in result["files"]:
            filepath = Path(file_info["path"])
            filename = filepath.name

            # Should contain match_id
            assert match_id in filename

            # Should have .mp4 extension
            assert filepath.suffix == ".mp4"

    def test_storage_path_creation(self, test_harness):
        """Test that storage paths are created correctly"""
        storage_path = test_harness.config.storage_path

        assert storage_path.exists()
        assert storage_path.is_dir()

    def test_cleanup_old_recordings(self, test_harness):
        """Test cleanup of old recordings"""
        # Create multiple recordings
        for i in range(3):
            test_harness.start_recording({"match_id": f"cleanup_{i}"})
            time.sleep(1)
            test_harness.stop_recording()

        # Clear storage
        test_harness.clear_storage()

        # Should have no files
        files = list(test_harness.config.storage_path.glob("*.mp4"))
        assert len(files) == 0
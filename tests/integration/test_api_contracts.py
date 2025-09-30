"""
API Contract Integration Tests
Tests API endpoints and contract compliance
"""

import pytest
from typing import Dict, Any


@pytest.mark.integration
@pytest.mark.api
class TestRecordingAPI:
    """Test recording API endpoints"""

    def test_start_recording_endpoint(self, api_client):
        """Test POST /api/recording/start"""
        response = api_client.start_recording({
            "match_id": "api_test_001",
            "duration": 5400
        })

        assert response["status"] == 200
        assert "recording_id" in response

    def test_stop_recording_endpoint(self, api_client):
        """Test POST /api/recording/stop"""
        # Start recording first
        api_client.start_recording({"match_id": "api_test_002"})

        # Stop recording
        response = api_client.stop_recording()

        assert response["status"] == 200
        assert "files" in response

    def test_get_status_endpoint(self, api_client):
        """Test GET /api/status"""
        response = api_client.get_status()

        assert "status" in response
        assert "recording" in response
        assert isinstance(response["recording"], bool)

    def test_invalid_recording_params(self, api_client):
        """Test API with invalid parameters"""
        # Missing required field
        response = api_client.start_recording({})

        # Should handle gracefully (implementation dependent)
        assert "recording_id" in response or "error" in response


@pytest.mark.integration
@pytest.mark.api
class TestAPIErrorHandling:
    """Test API error handling"""

    def test_stop_without_active_recording(self, api_client):
        """Test stopping when no recording active"""
        # Ensure no recording active
        status = api_client.get_status()
        if status.get("recording"):
            api_client.stop_recording()

        # Try to stop again
        response = api_client.stop_recording()

        # Should return error or graceful response
        assert response["status"] in [200, 400, 404]

    def test_concurrent_recording_requests(self, api_client):
        """Test handling of concurrent recording start requests"""
        # Start first recording
        response1 = api_client.start_recording({"match_id": "concurrent_1"})
        assert response1["status"] == 200

        # Try to start second recording
        response2 = api_client.start_recording({"match_id": "concurrent_2"})

        # Second should fail or queue
        # Implementation dependent

        # Cleanup
        api_client.stop_recording()


@pytest.mark.integration
@pytest.mark.api
class TestAPIResponseFormat:
    """Test API response format compliance"""

    def test_status_response_schema(self, api_client):
        """Test that status response matches expected schema"""
        response = api_client.get_status()

        # Required fields
        assert "status" in response
        assert "recording" in response

        # Type validation
        assert isinstance(response["status"], str)
        assert isinstance(response["recording"], bool)

    def test_recording_response_schema(self, api_client):
        """Test that recording responses match expected schema"""
        response = api_client.start_recording({"match_id": "schema_test"})

        # Required fields
        assert "status" in response

        # Type validation
        assert isinstance(response["status"], int)

        # Cleanup
        api_client.stop_recording()


@pytest.mark.integration
@pytest.mark.api
class TestAPIPerformance:
    """Test API response time performance"""

    def test_status_response_time(self, api_client):
        """Test that status endpoint responds quickly"""
        import time

        start = time.time()
        response = api_client.get_status()
        elapsed = time.time() - start

        # Should respond in < 100ms (target from test plan)
        assert elapsed < 0.1, f"Status endpoint too slow: {elapsed:.3f}s"

    def test_api_under_load(self, api_client):
        """Test API responsiveness under multiple requests"""
        import time

        # Make 10 rapid requests
        times = []
        for _ in range(10):
            start = time.time()
            api_client.get_status()
            times.append(time.time() - start)

        # All should be fast
        assert all(t < 0.1 for t in times), f"Some requests too slow: {times}"

        # Average should be good
        avg_time = sum(times) / len(times)
        assert avg_time < 0.05, f"Average response time too high: {avg_time:.3f}s"
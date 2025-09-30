"""
Comprehensive API tests for FootballVision Pro
"""

import pytest
from fastapi.testclient import TestClient
from ..main import app
from ..database.db_manager import init_database
import tempfile
import os


@pytest.fixture
def test_db():
    """Create temporary test database"""
    fd, path = tempfile.mkstemp(suffix='.db')
    init_database(path)
    yield path
    os.close(fd)
    os.unlink(path)


@pytest.fixture
def client(test_db):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def auth_token(client):
    """Get authentication token"""
    response = client.post("/api/v1/auth/login", json={
        "email": "admin@localhost",
        "password": "admin123"
    })
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Get authentication headers"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestAuthentication:
    """Test authentication endpoints"""

    def test_login_success(self, client):
        """Test successful login"""
        response = client.post("/api/v1/auth/login", json={
            "email": "admin@localhost",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "admin@localhost"

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials"""
        response = client.post("/api/v1/auth/login", json={
            "email": "admin@localhost",
            "password": "wrong_password"
        })
        assert response.status_code == 401

    def test_refresh_token(self, client):
        """Test token refresh"""
        # Login first
        login_response = client.post("/api/v1/auth/login", json={
            "email": "admin@localhost",
            "password": "admin123"
        })
        refresh_token = login_response.json()["refresh_token"]

        # Refresh token
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_protected_endpoint_without_auth(self, client):
        """Test accessing protected endpoint without auth"""
        response = client.get("/api/v1/system/status")
        assert response.status_code == 401


class TestRecording:
    """Test recording endpoints"""

    def test_start_recording(self, client, auth_headers):
        """Test starting recording"""
        response = client.post("/api/v1/recording", headers=auth_headers, json={
            "match_id": "test_match_001",
            "home_team": "Team A",
            "away_team": "Team B",
            "scheduled_duration": 90
        })
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["match_id"] == "test_match_001"

    def test_get_recording_status(self, client, auth_headers):
        """Test getting recording status"""
        response = client.get("/api/v1/recording/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "is_recording" in data
        assert "cameras" in data

    def test_stop_recording(self, client, auth_headers):
        """Test stopping recording"""
        response = client.delete("/api/v1/recording", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "duration_seconds" in data


class TestMatches:
    """Test match management endpoints"""

    def test_create_match(self, client, auth_headers):
        """Test creating a match"""
        response = client.post("/api/v1/matches", headers=auth_headers, json={
            "home_team": "Team A",
            "away_team": "Team B",
            "match_date": "2024-01-15T15:00:00",
            "competition": "League",
            "venue": "Stadium"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["home_team"] == "Team A"
        assert data["away_team"] == "Team B"
        return data["id"]

    def test_list_matches(self, client, auth_headers):
        """Test listing matches"""
        response = client.get("/api/v1/matches", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "matches" in data
        assert "total" in data

    def test_get_match(self, client, auth_headers):
        """Test getting a specific match"""
        # Create a match first
        create_response = client.post("/api/v1/matches", headers=auth_headers, json={
            "home_team": "Team A",
            "away_team": "Team B",
            "match_date": "2024-01-15T15:00:00"
        })
        match_id = create_response.json()["id"]

        # Get the match
        response = client.get(f"/api/v1/matches/{match_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == match_id

    def test_update_match(self, client, auth_headers):
        """Test updating a match"""
        # Create a match first
        create_response = client.post("/api/v1/matches", headers=auth_headers, json={
            "home_team": "Team A",
            "away_team": "Team B",
            "match_date": "2024-01-15T15:00:00"
        })
        match_id = create_response.json()["id"]

        # Update the match
        response = client.patch(f"/api/v1/matches/{match_id}", headers=auth_headers, json={
            "competition": "Cup"
        })
        assert response.status_code == 200
        assert response.json()["competition"] == "Cup"

    def test_delete_match(self, client, auth_headers):
        """Test deleting a match"""
        # Create a match first
        create_response = client.post("/api/v1/matches", headers=auth_headers, json={
            "home_team": "Team A",
            "away_team": "Team B",
            "match_date": "2024-01-15T15:00:00"
        })
        match_id = create_response.json()["id"]

        # Delete the match
        response = client.delete(f"/api/v1/matches/{match_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify it's deleted
        get_response = client.get(f"/api/v1/matches/{match_id}", headers=auth_headers)
        assert get_response.status_code == 404


class TestSystem:
    """Test system endpoints"""

    def test_get_system_status(self, client, auth_headers):
        """Test getting system status"""
        response = client.get("/api/v1/system/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "state" in data
        assert "storage_available_gb" in data
        assert "temperature_c" in data

    def test_health_check(self, client):
        """Test health check endpoint (no auth required)"""
        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checks" in data

    def test_get_logs(self, client, auth_headers):
        """Test getting system logs"""
        response = client.get("/api/v1/system/logs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data


class TestCloud:
    """Test cloud upload endpoints"""

    def test_get_cloud_config(self, client, auth_headers):
        """Test getting cloud configuration"""
        response = client.get("/api/v1/cloud/config", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data

    def test_start_upload(self, client, auth_headers):
        """Test starting cloud upload"""
        # Create a match first
        match_response = client.post("/api/v1/matches", headers=auth_headers, json={
            "home_team": "Team A",
            "away_team": "Team B",
            "match_date": "2024-01-15T15:00:00"
        })
        match_id = match_response.json()["id"]

        # Start upload
        response = client.post("/api/v1/cloud/upload", headers=auth_headers, json={
            "match_id": match_id,
            "provider": "aws_s3"
        })
        assert response.status_code == 202
        data = response.json()
        assert "upload_id" in data


class TestDevice:
    """Test device management endpoints"""

    def test_get_device_info(self, client, auth_headers):
        """Test getting device information"""
        response = client.get("/api/v1/device/info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "device_id" in data
        assert "cameras" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
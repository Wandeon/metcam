"""
Authentication service tests
"""

import pytest
from ..services.auth import AuthService, get_auth_service


class TestAuthService:
    """Test authentication service"""

    def test_password_hashing(self):
        """Test password hashing and verification"""
        auth = get_auth_service()

        password = "test_password_123"
        hashed = auth.hash_password(password)

        assert auth.verify_password(password, hashed)
        assert not auth.verify_password("wrong_password", hashed)

    def test_create_access_token(self):
        """Test access token creation"""
        auth = get_auth_service()

        token = auth.create_access_token(1, "test@example.com", "admin")
        assert token is not None
        assert len(token) > 0

        # Verify token
        payload = auth.verify_token(token)
        assert payload is not None
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        """Test refresh token creation"""
        auth = get_auth_service()

        token = auth.create_refresh_token(1)
        assert token is not None

        # Verify token
        payload = auth.verify_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_verify_invalid_token(self):
        """Test verifying invalid token"""
        auth = get_auth_service()

        payload = auth.verify_token("invalid_token")
        assert payload is None
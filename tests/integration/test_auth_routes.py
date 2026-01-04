"""Integration tests for authenticated endpoints."""

import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt


# Test JWT secret for integration tests
TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests"


def create_test_token(
    sub: str = "550e8400-e29b-41d4-a716-446655440000",
    email: str | None = "test@example.com",
    role: str | None = "user",
    exp_offset: int = 3600,
) -> str:
    """Create a test JWT token."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "role": role,
        "exp": now + exp_offset,
        "iat": now,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


class TestHealthAuthEndpoint:
    """Tests for /health/auth protected endpoint."""

    def test_returns_401_without_auth_header(self, client: TestClient) -> None:
        """Test that /health/auth returns 401 without Authorization header."""
        response = client.get("/health/auth")
        assert response.status_code == 401

    def test_returns_401_with_empty_auth_header(self, client: TestClient) -> None:
        """Test that /health/auth returns 401 with empty Authorization header."""
        response = client.get("/health/auth", headers={"Authorization": ""})
        assert response.status_code == 401

    def test_returns_401_with_invalid_token_format(self, client: TestClient) -> None:
        """Test that /health/auth returns 401 with invalid token format."""
        response = client.get("/health/auth", headers={"Authorization": "InvalidFormat"})
        assert response.status_code == 401

    @patch("src.api.middleware.auth.get_settings")
    def test_returns_401_with_expired_token(
        self, mock_settings: any, mock_supabase_client: MagicMock
    ) -> None:
        """Test that /health/auth returns 401 with expired token."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        # Create expired token
        expired_token = create_test_token(exp_offset=-3600)

        from src.main import app

        with TestClient(app) as test_client:
            response = test_client.get(
                "/health/auth", headers={"Authorization": f"Bearer {expired_token}"}
            )

            assert response.status_code == 401
            data = response.json()
            assert "expired" in data.get("detail", "").lower()

    @patch("src.api.middleware.auth.get_settings")
    def test_returns_200_with_valid_token(
        self, mock_settings: any, mock_supabase_client: MagicMock
    ) -> None:
        """Test that /health/auth returns 200 with valid token."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        valid_token = create_test_token()

        from src.main import app

        with TestClient(app) as test_client:
            response = test_client.get(
                "/health/auth", headers={"Authorization": f"Bearer {valid_token}"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is True
            assert data["user_id"] == "550e8400-e29b-41d4-a716-446655440000"
            assert data["email"] == "test@example.com"
            assert data["role"] == "user"

    @patch("src.api.middleware.auth.get_settings")
    def test_returns_user_info_from_token(
        self, mock_settings: any, mock_supabase_client: MagicMock
    ) -> None:
        """Test that /health/auth returns correct user info from token."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        # Create token with specific user info
        valid_token = create_test_token(
            sub="12345678-1234-1234-1234-123456789012",
            email="admin@example.com",
            role="admin",
        )

        from src.main import app

        with TestClient(app) as test_client:
            response = test_client.get(
                "/health/auth", headers={"Authorization": f"Bearer {valid_token}"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "12345678-1234-1234-1234-123456789012"
            assert data["email"] == "admin@example.com"
            assert data["role"] == "admin"

    @patch("src.api.middleware.auth.get_settings")
    def test_handles_token_without_optional_claims(
        self, mock_settings: any, mock_supabase_client: MagicMock
    ) -> None:
        """Test that /health/auth handles tokens without email/role."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        # Create token without optional fields
        valid_token = create_test_token(email=None, role=None)

        from src.main import app

        with TestClient(app) as test_client:
            response = test_client.get(
                "/health/auth", headers={"Authorization": f"Bearer {valid_token}"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is True
            assert data["email"] is None
            assert data["role"] is None

    @patch("src.api.middleware.auth.get_settings")
    def test_returns_401_with_wrong_secret(
        self, mock_settings: any, mock_supabase_client: MagicMock
    ) -> None:
        """Test that /health/auth returns 401 when token signed with wrong secret."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        # Create token with different secret
        now = int(time.time())
        payload = {
            "sub": "550e8400-e29b-41d4-a716-446655440000",
            "exp": now + 3600,
            "iat": now,
        }
        wrong_secret_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        from src.main import app

        with TestClient(app) as test_client:
            response = test_client.get(
                "/health/auth", headers={"Authorization": f"Bearer {wrong_secret_token}"}
            )

            assert response.status_code == 401

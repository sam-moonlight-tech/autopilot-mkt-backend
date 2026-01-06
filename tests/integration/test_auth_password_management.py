"""Integration tests for password management endpoints."""

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


class TestForgotPassword:
    """Tests for POST /api/v1/auth/forgot-password endpoint."""

    @patch("src.services.auth_service.get_supabase_client")
    @patch("src.services.auth_service.get_settings")
    def test_forgot_password_sends_email(
        self, mock_settings: MagicMock, mock_supabase: MagicMock, client: TestClient
    ) -> None:
        """Test that forgot password sends reset email."""
        # Mock settings
        mock_settings.return_value.auth_redirect_url = "https://example.com"

        # Mock Supabase client
        mock_auth = MagicMock()
        mock_supabase.return_value.auth = mock_auth
        mock_auth.reset_password_for_email.return_value = None

        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email_sent"] is True
        assert "message" in data
        mock_auth.reset_password_for_email.assert_called_once()

    @patch("src.services.auth_service.get_supabase_client")
    @patch("src.services.auth_service.get_settings")
    def test_forgot_password_always_returns_success(
        self, mock_settings: MagicMock, mock_supabase: MagicMock, client: TestClient
    ) -> None:
        """Test that forgot password always returns success for security."""
        # Mock settings
        mock_settings.return_value.auth_redirect_url = "https://example.com"

        # Mock Supabase client with error
        mock_auth = MagicMock()
        mock_supabase.return_value.auth = mock_auth
        mock_auth.reset_password_for_email.side_effect = Exception("Email not found")

        # Should still return success to prevent email enumeration
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email_sent"] is True


class TestResetPassword:
    """Tests for POST /api/v1/auth/reset-password endpoint."""

    @patch("src.services.auth_service.get_supabase_client")
    @patch("src.services.auth_service.get_settings")
    def test_reset_password_with_valid_token(
        self, mock_settings: MagicMock, mock_supabase: MagicMock, client: TestClient
    ) -> None:
        """Test that password reset works with valid token."""
        # Mock settings
        mock_settings.return_value.auth_redirect_url = "https://example.com"

        # Mock Supabase client
        mock_auth = MagicMock()
        mock_supabase.return_value.auth = mock_auth

        # Mock user and session for OTP verification
        mock_user = MagicMock()
        mock_user.id = "550e8400-e29b-41d4-a716-446655440000"
        mock_user.email = "test@example.com"

        mock_session = MagicMock()
        mock_session.access_token = "test-access-token"
        mock_session.refresh_token = "test-refresh-token"

        mock_otp_response = MagicMock()
        mock_otp_response.user = mock_user
        mock_otp_response.session = mock_session

        mock_auth.verify_otp.return_value = mock_otp_response

        # Mock update user response
        mock_update_user = MagicMock()
        mock_update_user.id = "550e8400-e29b-41d4-a716-446655440000"
        mock_update_response = MagicMock()
        mock_update_response.user = mock_update_user
        mock_auth.update_user.return_value = mock_update_response

        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "valid-reset-token", "new_password": "NewPassword123!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "redirect_url" in data
        mock_auth.verify_otp.assert_called_once()

    @patch("src.services.auth_service.get_supabase_client")
    @patch("src.services.auth_service.get_settings")
    def test_reset_password_with_invalid_token(
        self, mock_settings: MagicMock, mock_supabase: MagicMock, client: TestClient
    ) -> None:
        """Test that password reset fails with invalid token."""
        # Mock settings
        mock_settings.return_value.auth_redirect_url = "https://example.com"

        # Mock Supabase client
        mock_auth = MagicMock()
        mock_supabase.return_value.auth = mock_auth

        # Mock OTP verification failure
        mock_auth.verify_otp.side_effect = Exception("Invalid token")

        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "invalid-token", "new_password": "NewPassword123!"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower() or "expired" in data["detail"].lower()

    def test_reset_password_validation_error(self, client: TestClient) -> None:
        """Test that reset password validates input."""
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "test-token"},  # Missing new_password
        )

        assert response.status_code == 422  # Validation error


class TestChangePassword:
    """Tests for POST /api/v1/auth/change-password endpoint."""

    @patch("src.api.deps.decode_jwt")
    @patch("src.services.auth_service.get_supabase_client")
    @patch("src.services.profile_service.get_supabase_client")
    def test_change_password_success(
        self,
        mock_profile_supabase: MagicMock,
        mock_auth_supabase: MagicMock,
        mock_decode_jwt: MagicMock,
        client: TestClient,
    ) -> None:
        """Test that authenticated user can change password."""
        # Mock JWT decoding
        from src.schemas.auth import TokenPayload
        
        mock_token_payload = TokenPayload(
            sub="550e8400-e29b-41d4-a716-446655440000",
            email="test@example.com",
            role="user",
            exp=int(time.time()) + 3600,
            iat=int(time.time()),
        )
        mock_decode_jwt.return_value = mock_token_payload

        token = create_test_token()

        # Mock profile service
        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "test@example.com",
        }
        mock_profile_response = MagicMock()
        mock_profile_response.data = profile_data
        mock_profile_supabase.return_value.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_profile_response
        )

        # Mock auth service - sign in to verify current password
        mock_auth = MagicMock()
        mock_auth_supabase.return_value.auth = mock_auth

        mock_user = MagicMock()
        mock_user.id = "550e8400-e29b-41d4-a716-446655440000"
        mock_user.email = "test@example.com"

        mock_session = MagicMock()
        mock_session.access_token = "test-access-token"
        mock_session.refresh_token = "test-refresh-token"

        mock_signin_response = MagicMock()
        mock_signin_response.user = mock_user
        mock_signin_response.session = mock_session
        mock_auth.sign_in_with_password.return_value = mock_signin_response

        # Mock update user
        mock_update_user = MagicMock()
        mock_update_user.id = "550e8400-e29b-41d4-a716-446655440000"
        mock_update_response = MagicMock()
        mock_update_response.user = mock_update_user
        mock_auth.update_user.return_value = mock_update_response

        response = client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "OldPassword123!", "new_password": "NewPassword123!"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "successfully" in data["message"].lower()

    @patch("src.api.deps.decode_jwt")
    @patch("src.services.auth_service.get_supabase_client")
    @patch("src.services.profile_service.get_supabase_client")
    def test_change_password_wrong_current_password(
        self,
        mock_profile_supabase: MagicMock,
        mock_auth_supabase: MagicMock,
        mock_decode_jwt: MagicMock,
        client: TestClient,
    ) -> None:
        """Test that change password fails with wrong current password."""
        # Mock JWT decoding
        from src.schemas.auth import TokenPayload
        
        mock_token_payload = TokenPayload(
            sub="550e8400-e29b-41d4-a716-446655440000",
            email="test@example.com",
            role="user",
            exp=int(time.time()) + 3600,
            iat=int(time.time()),
        )
        mock_decode_jwt.return_value = mock_token_payload

        token = create_test_token()

        # Mock profile service
        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "test@example.com",
        }
        mock_profile_response = MagicMock()
        mock_profile_response.data = profile_data
        mock_profile_supabase.return_value.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_profile_response
        )

        # Mock auth service - sign in fails (wrong password)
        mock_auth = MagicMock()
        mock_auth_supabase.return_value.auth = mock_auth
        mock_auth.sign_in_with_password.side_effect = Exception("Invalid credentials")

        response = client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "WrongPassword!", "new_password": "NewPassword123!"},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "incorrect" in data["detail"].lower()

    def test_change_password_requires_auth(self, client: TestClient) -> None:
        """Test that change password requires authentication."""
        response = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "OldPassword123!", "new_password": "NewPassword123!"},
        )

        assert response.status_code == 401

    @patch("src.api.deps.decode_jwt")
    def test_change_password_validation_error(
        self, mock_decode_jwt: MagicMock, client: TestClient
    ) -> None:
        """Test that change password validates input."""
        # Mock JWT decoding
        from src.schemas.auth import TokenPayload
        
        mock_token_payload = TokenPayload(
            sub="550e8400-e29b-41d4-a716-446655440000",
            email="test@example.com",
            role="user",
            exp=int(time.time()) + 3600,
            iat=int(time.time()),
        )
        mock_decode_jwt.return_value = mock_token_payload
        
        token = create_test_token()

        response = client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "OldPassword123!"},  # Missing new_password
        )

        assert response.status_code == 422  # Validation error


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh endpoint."""

    @patch("src.services.auth_service.get_supabase_client")
    def test_refresh_token_success(
        self, mock_supabase: MagicMock, client: TestClient
    ) -> None:
        """Test that refresh token works with valid refresh token."""
        # Mock Supabase client
        mock_auth = MagicMock()
        mock_supabase.return_value.auth = mock_auth

        # Mock session
        mock_session = MagicMock()
        mock_session.access_token = "new-access-token"
        mock_session.refresh_token = "new-refresh-token"
        mock_session.expires_in = 3600

        mock_refresh_response = MagicMock()
        mock_refresh_response.session = mock_session
        mock_auth.refresh_session.return_value = mock_refresh_response

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "valid-refresh-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] == "new-access-token"
        assert "expires_in" in data
        assert data["expires_in"] == 3600
        mock_auth.refresh_session.assert_called_once_with("valid-refresh-token")

    @patch("src.services.auth_service.get_supabase_client")
    def test_refresh_token_invalid(
        self, mock_supabase: MagicMock, client: TestClient
    ) -> None:
        """Test that refresh token fails with invalid token."""
        # Mock Supabase client
        mock_auth = MagicMock()
        mock_supabase.return_value.auth = mock_auth

        # Mock refresh failure
        mock_auth.refresh_session.side_effect = Exception("Invalid refresh token")

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-refresh-token"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "invalid" in data["detail"].lower() or "expired" in data["detail"].lower()

    def test_refresh_token_missing_token(self, client: TestClient) -> None:
        """Test that refresh token fails without token."""
        response = client.post(
            "/api/v1/auth/refresh",
            json={},
        )

        assert response.status_code == 422  # Validation error


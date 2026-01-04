"""Unit tests for JWT decoding and authentication utilities."""

import time
from unittest.mock import patch

import pytest
from jose import jwt

from src.api.middleware.auth import AuthError, AuthErrorCode, decode_jwt


# Test JWT secret for unit tests
TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests"


def create_test_token(
    sub: str = "550e8400-e29b-41d4-a716-446655440000",
    email: str | None = "test@example.com",
    role: str | None = "user",
    exp_offset: int = 3600,
    secret: str = TEST_JWT_SECRET,
    algorithm: str = "HS256",
) -> str:
    """Create a test JWT token.

    Args:
        sub: Subject (user ID).
        email: User email.
        role: User role.
        exp_offset: Seconds from now for expiration (negative for expired).
        secret: JWT secret for signing.
        algorithm: Signing algorithm.

    Returns:
        str: Encoded JWT token.
    """
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "role": role,
        "exp": now + exp_offset,
        "iat": now,
        "aud": "authenticated",
        "iss": "https://test.supabase.co/auth/v1",
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


class TestDecodeJWT:
    """Tests for decode_jwt function."""

    @patch("src.api.middleware.auth.get_settings")
    def test_decode_jwt_with_valid_token(self, mock_settings: any) -> None:
        """Test decode_jwt successfully decodes a valid token."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        token = create_test_token()
        payload = decode_jwt(token)

        assert payload.sub == "550e8400-e29b-41d4-a716-446655440000"
        assert payload.email == "test@example.com"
        assert payload.role == "user"

    @patch("src.api.middleware.auth.get_settings")
    def test_decode_jwt_with_expired_token(self, mock_settings: any) -> None:
        """Test decode_jwt raises AuthError for expired token."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        # Create token that expired 1 hour ago
        token = create_test_token(exp_offset=-3600)

        with pytest.raises(AuthError) as exc_info:
            decode_jwt(token)

        assert exc_info.value.code == AuthErrorCode.TOKEN_EXPIRED
        assert "expired" in exc_info.value.message.lower()

    @patch("src.api.middleware.auth.get_settings")
    def test_decode_jwt_with_invalid_signature(self, mock_settings: any) -> None:
        """Test decode_jwt raises AuthError for invalid signature."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        # Create token with wrong secret
        token = create_test_token(secret="wrong-secret")

        with pytest.raises(AuthError) as exc_info:
            decode_jwt(token)

        assert exc_info.value.code in [AuthErrorCode.INVALID_SIGNATURE, AuthErrorCode.INVALID_TOKEN]

    @patch("src.api.middleware.auth.get_settings")
    def test_decode_jwt_with_malformed_token(self, mock_settings: any) -> None:
        """Test decode_jwt raises AuthError for malformed token."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        with pytest.raises(AuthError) as exc_info:
            decode_jwt("not-a-valid-jwt-token")

        assert exc_info.value.code == AuthErrorCode.INVALID_TOKEN

    @patch("src.api.middleware.auth.get_settings")
    def test_decode_jwt_with_empty_token(self, mock_settings: any) -> None:
        """Test decode_jwt raises AuthError for empty token."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        with pytest.raises(AuthError) as exc_info:
            decode_jwt("")

        assert exc_info.value.code == AuthErrorCode.INVALID_TOKEN

    @patch("src.api.middleware.auth.get_settings")
    def test_decode_jwt_missing_sub_claim(self, mock_settings: any) -> None:
        """Test decode_jwt raises AuthError when sub claim is missing."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        # Create token without sub claim
        now = int(time.time())
        payload = {
            "email": "test@example.com",
            "exp": now + 3600,
            "iat": now,
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")

        with pytest.raises(AuthError) as exc_info:
            decode_jwt(token)

        assert exc_info.value.code == AuthErrorCode.INVALID_TOKEN
        assert "sub" in exc_info.value.message.lower()

    @patch("src.api.middleware.auth.get_settings")
    def test_decode_jwt_converts_to_user_context(self, mock_settings: any) -> None:
        """Test that token payload can be converted to UserContext."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        token = create_test_token()
        payload = decode_jwt(token)
        user_context = payload.to_user_context()

        assert str(user_context.user_id) == "550e8400-e29b-41d4-a716-446655440000"
        assert user_context.email == "test@example.com"
        assert user_context.role == "user"

    @patch("src.api.middleware.auth.get_settings")
    def test_decode_jwt_optional_fields(self, mock_settings: any) -> None:
        """Test decode_jwt handles missing optional fields."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        token = create_test_token(email=None, role=None)
        payload = decode_jwt(token)

        assert payload.sub == "550e8400-e29b-41d4-a716-446655440000"
        assert payload.email is None
        assert payload.role is None

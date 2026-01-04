"""Unit tests for FastAPI dependency injection functions."""

import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt

from src.api.deps import get_current_user, get_optional_user
from src.schemas.auth import UserContext


# Test JWT secret for unit tests
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


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    @patch("src.api.deps.decode_jwt")
    async def test_extracts_user_context_correctly(self, mock_decode: any) -> None:
        """Test get_current_user extracts UserContext from valid token."""
        from src.schemas.auth import TokenPayload

        mock_payload = TokenPayload(
            sub="550e8400-e29b-41d4-a716-446655440000",
            email="test@example.com",
            role="user",
            exp=int(time.time()) + 3600,
            iat=int(time.time()),
        )
        mock_decode.return_value = mock_payload

        user = await get_current_user("Bearer valid-token")

        assert isinstance(user, UserContext)
        assert str(user.user_id) == "550e8400-e29b-41d4-a716-446655440000"
        assert user.email == "test@example.com"
        assert user.role == "user"

    @pytest.mark.asyncio
    async def test_raises_401_for_missing_header(self) -> None:
        """Test get_current_user raises 401 when Authorization header is missing."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("")

        assert exc_info.value.status_code == 401
        assert "Authorization header required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_401_for_invalid_header_format(self) -> None:
        """Test get_current_user raises 401 for invalid header format."""
        # Missing "Bearer" prefix
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("invalid-token")

        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_401_for_wrong_scheme(self) -> None:
        """Test get_current_user raises 401 for non-Bearer scheme."""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("Basic some-credentials")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    @patch("src.api.deps.decode_jwt")
    async def test_raises_401_for_expired_token(self, mock_decode: any) -> None:
        """Test get_current_user raises 401 for expired token."""
        from src.api.middleware.auth import AuthError, AuthErrorCode

        mock_decode.side_effect = AuthError("Token has expired", AuthErrorCode.TOKEN_EXPIRED)

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("Bearer expired-token")

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()


class TestGetOptionalUser:
    """Tests for get_optional_user dependency."""

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_header(self) -> None:
        """Test get_optional_user returns None when no Authorization header."""
        user = await get_optional_user(None)
        assert user is None

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_header(self) -> None:
        """Test get_optional_user returns None for empty header."""
        user = await get_optional_user("")
        assert user is None

    @pytest.mark.asyncio
    @patch("src.api.deps.decode_jwt")
    async def test_returns_user_context_for_valid_token(self, mock_decode: any) -> None:
        """Test get_optional_user returns UserContext for valid token."""
        from src.schemas.auth import TokenPayload

        mock_payload = TokenPayload(
            sub="550e8400-e29b-41d4-a716-446655440000",
            email="test@example.com",
            role="user",
            exp=int(time.time()) + 3600,
            iat=int(time.time()),
        )
        mock_decode.return_value = mock_payload

        user = await get_optional_user("Bearer valid-token")

        assert user is not None
        assert isinstance(user, UserContext)
        assert str(user.user_id) == "550e8400-e29b-41d4-a716-446655440000"

    @pytest.mark.asyncio
    @patch("src.api.deps.decode_jwt")
    async def test_raises_401_for_invalid_token(self, mock_decode: any) -> None:
        """Test get_optional_user raises 401 if token is present but invalid."""
        from src.api.middleware.auth import AuthError, AuthErrorCode

        mock_decode.side_effect = AuthError("Invalid token", AuthErrorCode.INVALID_TOKEN)

        # When a token is provided but invalid, it should still raise
        with pytest.raises(HTTPException) as exc_info:
            await get_optional_user("Bearer invalid-token")

        assert exc_info.value.status_code == 401

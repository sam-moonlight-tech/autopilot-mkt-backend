"""Integration tests for profile API endpoints."""

import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt


TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests"


def create_test_token(
    sub: str = "550e8400-e29b-41d4-a716-446655440000",
    email: str = "test@example.com",
) -> str:
    """Create a test JWT token."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "role": "user",
        "exp": now + 3600,
        "iat": now,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


class TestGetMyProfile:
    """Tests for GET /api/v1/profiles/me endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    def test_returns_profile(
        self, mock_supabase: MagicMock, mock_settings: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that profile is returned for authenticated user."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "display_name": "Test User",
            "email": "test@example.com",
            "avatar_url": None,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        mock_response = MagicMock()
        mock_response.data = [profile_data]
        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/profiles/me",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "test@example.com"

    def test_returns_401_without_auth(self, mock_supabase_client: MagicMock) -> None:
        """Test that 401 is returned without auth header."""
        from src.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/profiles/me")
            assert response.status_code == 401


class TestUpdateMyProfile:
    """Tests for PUT /api/v1/profiles/me endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    def test_updates_profile(
        self, mock_supabase: MagicMock, mock_settings: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that profile is updated."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        existing_profile = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "display_name": "Test User",
            "email": "test@example.com",
            "avatar_url": None,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        updated_profile = {
            **existing_profile,
            "display_name": "Updated Name",
        }

        # Mock for get_or_create
        mock_response1 = MagicMock()
        mock_response1.data = [existing_profile]

        # Mock for update
        mock_response2 = MagicMock()
        mock_response2.data = [updated_profile]

        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_response1
        )
        mock_supabase.return_value.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            mock_response2
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.put(
                "/api/v1/profiles/me",
                headers={"Authorization": f"Bearer {token}"},
                json={"display_name": "Updated Name"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["display_name"] == "Updated Name"


class TestGetMyCompanies:
    """Tests for GET /api/v1/profiles/me/companies endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    def test_returns_user_companies(
        self, mock_supabase: MagicMock, mock_settings: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that user's companies are returned."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
        }

        memberships = [
            {
                "role": "owner",
                "joined_at": "2024-01-01T00:00:00Z",
                "companies": {
                    "id": "770e8400-e29b-41d4-a716-446655440000",
                    "name": "Test Company",
                },
            }
        ]

        profile_response = MagicMock()
        profile_response.data = profile_data

        membership_response = MagicMock()
        membership_response.data = memberships

        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            profile_response
        )
        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            membership_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/profiles/me/companies",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "Test Company"
            assert data[0]["role"] == "owner"

"""Integration tests for discovery profile API endpoints."""

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


class TestGetDiscoveryProfile:
    """Tests for GET /api/v1/discovery endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.discovery_profile_service.get_supabase_client")
    @patch("src.services.profile_service.get_supabase_client")
    def test_returns_discovery_profile(
        self,
        mock_profile_supabase: MagicMock,
        mock_discovery_supabase: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that discovery profile is returned for authenticated user."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "display_name": "Test User",
            "email": "test@example.com",
        }

        discovery_data = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "profile_id": "660e8400-e29b-41d4-a716-446655440000",
            "current_question_index": 5,
            "phase": "roi",
            "answers": {"q1": {"key": "val"}},
            "roi_inputs": None,
            "selected_product_ids": [],
            "timeframe": None,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        # Mock profile lookup
        mock_profile_response = MagicMock()
        mock_profile_response.data = [profile_data]
        mock_profile_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_profile_response
        )

        # Mock discovery profile lookup
        mock_discovery_response = MagicMock()
        mock_discovery_response.data = [discovery_data]
        mock_discovery_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_discovery_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/discovery",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["phase"] == "roi"
            assert data["current_question_index"] == 5

    def test_returns_401_without_auth(self, mock_supabase_client: MagicMock) -> None:
        """Test that 401 is returned without auth header."""
        from src.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/discovery")
            assert response.status_code == 401


class TestUpdateDiscoveryProfile:
    """Tests for PUT /api/v1/discovery endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.discovery_profile_service.get_supabase_client")
    @patch("src.services.profile_service.get_supabase_client")
    def test_updates_discovery_profile(
        self,
        mock_profile_supabase: MagicMock,
        mock_discovery_supabase: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that discovery profile is updated."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "display_name": "Test User",
            "email": "test@example.com",
        }

        existing_discovery = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "profile_id": "660e8400-e29b-41d4-a716-446655440000",
            "current_question_index": 0,
            "phase": "discovery",
            "answers": {},
            "roi_inputs": None,
            "selected_product_ids": [],
            "timeframe": None,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        updated_discovery = {
            **existing_discovery,
            "phase": "greenlight",
            "current_question_index": 15,
        }

        # Mock profile lookup
        mock_profile_response = MagicMock()
        mock_profile_response.data = [profile_data]
        mock_profile_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_profile_response
        )

        # Mock discovery profile get_or_create
        mock_discovery_response = MagicMock()
        mock_discovery_response.data = [existing_discovery]
        mock_discovery_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_discovery_response
        )

        # Mock discovery profile update
        mock_update_response = MagicMock()
        mock_update_response.data = [updated_discovery]
        mock_discovery_supabase.return_value.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            mock_update_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.put(
                "/api/v1/discovery",
                headers={"Authorization": f"Bearer {token}"},
                json={"phase": "greenlight", "current_question_index": 15},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["phase"] == "greenlight"
            assert data["current_question_index"] == 15

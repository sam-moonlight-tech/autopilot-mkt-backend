"""Integration tests for conversation API endpoints."""

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


class TestCreateConversation:
    """Tests for POST /api/v1/conversations endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    @patch("src.services.conversation_service.get_supabase_client")
    def test_creates_conversation(
        self,
        mock_conv_supabase: MagicMock,
        mock_profile_supabase: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that conversation is created."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
        }

        conversation_data = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "user_id": "660e8400-e29b-41d4-a716-446655440000",
            "title": "New Conversation",
            "phase": "discovery",
            "metadata": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        profile_response = MagicMock()
        profile_response.data = [profile_data]
        mock_profile_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            profile_response
        )

        conv_response = MagicMock()
        conv_response.data = [conversation_data]
        mock_conv_supabase.return_value.table.return_value.insert.return_value.execute.return_value = (
            conv_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/conversations",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["title"] == "New Conversation"
            assert data["phase"] == "discovery"


class TestListConversations:
    """Tests for GET /api/v1/conversations endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    @patch("src.services.conversation_service.get_supabase_client")
    def test_returns_user_conversations(
        self,
        mock_conv_supabase: MagicMock,
        mock_profile_supabase: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that user's conversations are returned."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
        }

        conversations = [
            {
                "id": "770e8400-e29b-41d4-a716-446655440000",
                "user_id": "660e8400-e29b-41d4-a716-446655440000",
                "title": "Test Conversation",
                "phase": "discovery",
                "metadata": {},
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "messages": [{"count": 5}],
            }
        ]

        profile_response = MagicMock()
        profile_response.data = [profile_data]
        mock_profile_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            profile_response
        )

        conv_response = MagicMock()
        conv_response.data = conversations
        mock_conv_supabase.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            conv_response
        )

        # Mock for last message time
        msg_response = MagicMock()
        msg_response.data = []
        mock_conv_supabase.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            msg_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/conversations",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "conversations" in data


class TestGetConversation:
    """Tests for GET /api/v1/conversations/{id} endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    @patch("src.services.conversation_service.get_supabase_client")
    def test_returns_single_conversation(
        self,
        mock_conv_supabase: MagicMock,
        mock_profile_supabase: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that single conversation is returned."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
        }

        conversation = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "user_id": "660e8400-e29b-41d4-a716-446655440000",
            "company_id": None,
            "title": "Test Conversation",
            "phase": "discovery",
            "metadata": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        profile_response = MagicMock()
        profile_response.data = [profile_data]
        mock_profile_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            profile_response
        )

        conv_response = MagicMock()
        conv_response.data = conversation
        mock_conv_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            conv_response
        )

        # Mock for messages
        msg_response = MagicMock()
        msg_response.data = []
        mock_conv_supabase.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            msg_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/conversations/770e8400-e29b-41d4-a716-446655440000",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "Test Conversation"


class TestDeleteConversation:
    """Tests for DELETE /api/v1/conversations/{id} endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    @patch("src.services.conversation_service.get_supabase_client")
    def test_deletes_conversation(
        self,
        mock_conv_supabase: MagicMock,
        mock_profile_supabase: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that conversation is deleted."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
        }

        conversation = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "user_id": "660e8400-e29b-41d4-a716-446655440000",
            "company_id": None,
        }

        profile_response = MagicMock()
        profile_response.data = [profile_data]
        mock_profile_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            profile_response
        )

        conv_response = MagicMock()
        conv_response.data = conversation
        mock_conv_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            conv_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.delete(
                "/api/v1/conversations/770e8400-e29b-41d4-a716-446655440000",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 204

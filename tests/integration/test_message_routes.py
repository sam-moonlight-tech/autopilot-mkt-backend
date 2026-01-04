"""Integration tests for message API endpoints."""

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


class TestSendMessage:
    """Tests for POST /api/v1/conversations/{id}/messages endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    @patch("src.services.conversation_service.get_supabase_client")
    @patch("src.services.agent_service.get_openai_client")
    @patch("src.services.agent_service.get_settings")
    def test_sends_message_and_gets_response(
        self,
        mock_agent_settings: MagicMock,
        mock_openai: MagicMock,
        mock_conv_supabase: MagicMock,
        mock_profile_supabase: MagicMock,
        mock_auth_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that message is sent and agent response is received."""
        mock_auth_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET
        mock_agent_settings.return_value.max_context_messages = 20
        mock_agent_settings.return_value.openai_model = "gpt-4o"

        # Mock OpenAI response
        openai_response = MagicMock()
        openai_response.choices = [MagicMock()]
        openai_response.choices[0].message.content = "Hello! How can I help you?"
        mock_openai.return_value.chat.completions.create.return_value = openai_response

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
        }

        conversation = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "user_id": "660e8400-e29b-41d4-a716-446655440000",
            "company_id": None,
            "phase": "discovery",
        }

        user_message = {
            "id": "880e8400-e29b-41d4-a716-446655440000",
            "conversation_id": "770e8400-e29b-41d4-a716-446655440000",
            "role": "user",
            "content": "Hello",
            "metadata": {},
            "created_at": "2024-01-01T00:00:00Z",
        }

        agent_message = {
            "id": "990e8400-e29b-41d4-a716-446655440000",
            "conversation_id": "770e8400-e29b-41d4-a716-446655440000",
            "role": "assistant",
            "content": "Hello! How can I help you?",
            "metadata": {"model": "gpt-4o"},
            "created_at": "2024-01-01T00:00:01Z",
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

        # Mock for recent messages
        msg_history_response = MagicMock()
        msg_history_response.data = []
        mock_conv_supabase.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            msg_history_response
        )

        # Mock for message insert
        insert_responses = [user_message, agent_message]
        insert_call_count = [0]

        def mock_insert_execute(*args, **kwargs):
            response = MagicMock()
            response.data = [insert_responses[insert_call_count[0]]]
            insert_call_count[0] += 1
            return response

        mock_conv_supabase.return_value.table.return_value.insert.return_value.execute = (
            mock_insert_execute
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/conversations/770e8400-e29b-41d4-a716-446655440000/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={"content": "Hello"},
            )

            assert response.status_code == 201
            data = response.json()
            assert "user_message" in data
            assert "agent_message" in data
            assert data["user_message"]["content"] == "Hello"


class TestListMessages:
    """Tests for GET /api/v1/conversations/{id}/messages endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    @patch("src.services.conversation_service.get_supabase_client")
    def test_returns_message_history(
        self,
        mock_conv_supabase: MagicMock,
        mock_profile_supabase: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that message history is returned."""
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

        messages = [
            {
                "id": "880e8400-e29b-41d4-a716-446655440000",
                "conversation_id": "770e8400-e29b-41d4-a716-446655440000",
                "role": "user",
                "content": "Hello",
                "metadata": {},
                "created_at": "2024-01-01T00:00:00Z",
            },
            {
                "id": "990e8400-e29b-41d4-a716-446655440000",
                "conversation_id": "770e8400-e29b-41d4-a716-446655440000",
                "role": "assistant",
                "content": "Hi there!",
                "metadata": {},
                "created_at": "2024-01-01T00:00:01Z",
            },
        ]

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

        msg_response = MagicMock()
        msg_response.data = messages
        mock_conv_supabase.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            msg_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/conversations/770e8400-e29b-41d4-a716-446655440000/messages",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "messages" in data
            assert len(data["messages"]) == 2

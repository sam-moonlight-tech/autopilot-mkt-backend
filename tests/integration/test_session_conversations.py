"""Integration tests for session-owned conversation endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestCreateConversationWithSession:
    """Tests for POST /api/v1/conversations with session auth."""

    @patch("src.services.session_service.get_supabase_client")
    @patch("src.services.conversation_service.get_supabase_client")
    def test_creates_session_owned_conversation(
        self,
        mock_conversation_supabase: MagicMock,
        mock_session_supabase: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that conversation is created with session ownership."""
        session_token = "a" * 64
        session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": session_token,
            "current_question_index": 0,
            "phase": "discovery",
            "claimed_by_profile_id": None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }

        conversation = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": None,
            "company_id": None,
            "title": "New Conversation",
            "phase": "discovery",
            "metadata": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Mock session validation
        mock_session_response = MagicMock()
        mock_session_response.data = session
        mock_session_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_session_response
        )

        # Mock session update (set conversation)
        mock_session_update_response = MagicMock()
        mock_session_update_response.data = [session]
        mock_session_supabase.return_value.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            mock_session_update_response
        )

        # Mock conversation creation
        mock_conversation_response = MagicMock()
        mock_conversation_response.data = [conversation]
        mock_conversation_supabase.return_value.table.return_value.insert.return_value.execute.return_value = (
            mock_conversation_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/conversations",
                cookies={"autopilot_session": session_token},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["session_id"] == "550e8400-e29b-41d4-a716-446655440000"
            assert data["user_id"] is None


class TestSendMessageWithSession:
    """Tests for POST /api/v1/conversations/{id}/messages with session auth."""

    @patch("src.services.session_service.get_supabase_client")
    @patch("src.services.conversation_service.get_supabase_client")
    @patch("src.services.agent_service.get_openai_client")
    @patch("src.services.rag_service.get_rag_service")
    def test_sends_message_with_session(
        self,
        mock_rag_service: MagicMock,
        mock_openai: MagicMock,
        mock_conversation_supabase: MagicMock,
        mock_session_supabase: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that message is sent with session authentication."""
        session_token = "a" * 64
        session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": session_token,
            "claimed_by_profile_id": None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }

        conversation = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": None,
            "phase": "discovery",
        }

        user_message = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "conversation_id": "660e8400-e29b-41d4-a716-446655440000",
            "role": "user",
            "content": "Hello",
            "metadata": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        agent_message = {
            "id": "880e8400-e29b-41d4-a716-446655440000",
            "conversation_id": "660e8400-e29b-41d4-a716-446655440000",
            "role": "assistant",
            "content": "Hello! How can I help you?",
            "metadata": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Mock session validation
        mock_session_response = MagicMock()
        mock_session_response.data = session
        mock_session_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_session_response
        )

        # Mock conversation lookup
        mock_conv_response = MagicMock()
        mock_conv_response.data = conversation
        mock_conversation_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_conv_response
        )

        # Mock message inserts
        mock_user_msg_response = MagicMock()
        mock_user_msg_response.data = [user_message]
        mock_agent_msg_response = MagicMock()
        mock_agent_msg_response.data = [agent_message]

        mock_conversation_supabase.return_value.table.return_value.insert.return_value.execute.side_effect = [
            mock_user_msg_response,
            mock_agent_msg_response,
        ]

        # Mock recent messages (empty)
        mock_empty_response = MagicMock()
        mock_empty_response.data = []
        mock_conversation_supabase.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            mock_empty_response
        )

        # Mock OpenAI response
        mock_openai_response = MagicMock()
        mock_openai_response.choices = [MagicMock()]
        mock_openai_response.choices[0].message.content = "Hello! How can I help you?"
        mock_openai.return_value.chat.completions.create.return_value = mock_openai_response

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/conversations/660e8400-e29b-41d4-a716-446655440000/messages",
                cookies={"autopilot_session": session_token},
                json={"content": "Hello"},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["user_message"]["content"] == "Hello"
            assert data["agent_message"]["role"] == "assistant"


class TestSessionConversationAccessDenied:
    """Tests for conversation access denial with wrong session."""

    @patch("src.services.session_service.get_supabase_client")
    @patch("src.services.conversation_service.get_supabase_client")
    def test_denies_access_for_wrong_session(
        self,
        mock_conversation_supabase: MagicMock,
        mock_session_supabase: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that access is denied for wrong session."""
        session_token = "a" * 64
        session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": session_token,
            "claimed_by_profile_id": None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }

        # Conversation owned by different session
        conversation = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "session_id": "different-session-id",
            "user_id": None,
            "company_id": None,
            "phase": "discovery",
        }

        # Mock session validation
        mock_session_response = MagicMock()
        mock_session_response.data = session
        mock_session_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_session_response
        )

        # Mock conversation lookup
        mock_conv_response = MagicMock()
        mock_conv_response.data = conversation
        mock_conversation_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_conv_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/conversations/660e8400-e29b-41d4-a716-446655440000",
                cookies={"autopilot_session": session_token},
            )

            assert response.status_code == 403
            assert "access" in response.json()["detail"].lower()

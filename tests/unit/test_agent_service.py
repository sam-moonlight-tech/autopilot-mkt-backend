"""Unit tests for AgentService."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from src.models.conversation import ConversationPhase
from src.services.agent_service import AgentService, SYSTEM_PROMPTS


class TestGetSystemPrompt:
    """Tests for get_system_prompt method."""

    def test_returns_discovery_prompt(self) -> None:
        """Test that discovery phase returns correct prompt."""
        with patch("src.services.agent_service.get_openai_client"):
            with patch("src.services.agent_service.get_settings"):
                service = AgentService()
                prompt = service.get_system_prompt(ConversationPhase.DISCOVERY)

                assert "Discovery" in prompt
                assert "robotics procurement" in prompt.lower()

    def test_returns_roi_prompt(self) -> None:
        """Test that ROI phase returns correct prompt."""
        with patch("src.services.agent_service.get_openai_client"):
            with patch("src.services.agent_service.get_settings"):
                service = AgentService()
                prompt = service.get_system_prompt(ConversationPhase.ROI)

                assert "ROI" in prompt
                assert "costs" in prompt.lower() or "savings" in prompt.lower()

    def test_returns_selection_prompt(self) -> None:
        """Test that selection phase returns correct prompt."""
        with patch("src.services.agent_service.get_openai_client"):
            with patch("src.services.agent_service.get_settings"):
                service = AgentService()
                prompt = service.get_system_prompt(ConversationPhase.SELECTION)

                assert "Selection" in prompt
                assert "recommend" in prompt.lower() or "product" in prompt.lower()


class TestBuildContext:
    """Tests for build_context method."""

    @pytest.mark.asyncio
    async def test_includes_system_prompt(self) -> None:
        """Test that context includes system prompt at the beginning."""
        mock_settings = MagicMock()
        mock_settings.max_context_messages = 20

        with patch("src.services.agent_service.get_openai_client"):
            with patch("src.services.agent_service.get_settings", return_value=mock_settings):
                with patch(
                    "src.services.agent_service.ConversationService"
                ) as mock_conv_service:
                    mock_conv_service.return_value.get_recent_messages.return_value = []

                    service = AgentService()
                    context = await service.build_context(
                        conversation_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
                        phase=ConversationPhase.DISCOVERY,
                    )

                    assert len(context) >= 1
                    assert context[0]["role"] == "system"
                    assert "Autopilot" in context[0]["content"]

    @pytest.mark.asyncio
    async def test_includes_conversation_history(self) -> None:
        """Test that context includes message history."""
        mock_settings = MagicMock()
        mock_settings.max_context_messages = 20

        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        with patch("src.services.agent_service.get_openai_client"):
            with patch("src.services.agent_service.get_settings", return_value=mock_settings):
                with patch(
                    "src.services.agent_service.ConversationService"
                ) as mock_conv_service:
                    mock_conv_service.return_value.get_recent_messages.return_value = history

                    service = AgentService()
                    context = await service.build_context(
                        conversation_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
                        phase=ConversationPhase.DISCOVERY,
                    )

                    # System prompt + 2 history messages
                    assert len(context) == 3
                    assert context[1]["role"] == "user"
                    assert context[1]["content"] == "Hello"
                    assert context[2]["role"] == "assistant"
                    assert context[2]["content"] == "Hi there!"

    @pytest.mark.asyncio
    async def test_respects_message_limit(self) -> None:
        """Test that context respects max_context_messages setting."""
        mock_settings = MagicMock()
        mock_settings.max_context_messages = 5

        with patch("src.services.agent_service.get_openai_client"):
            with patch("src.services.agent_service.get_settings", return_value=mock_settings):
                with patch(
                    "src.services.agent_service.ConversationService"
                ) as mock_conv_service:
                    # Verify limit is passed to get_recent_messages
                    mock_conv_service.return_value.get_recent_messages.return_value = []

                    service = AgentService()
                    await service.build_context(
                        conversation_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
                        phase=ConversationPhase.DISCOVERY,
                    )

                    mock_conv_service.return_value.get_recent_messages.assert_called_once_with(
                        UUID("770e8400-e29b-41d4-a716-446655440000"), limit=5
                    )


class TestGenerateResponse:
    """Tests for generate_response method."""

    @pytest.mark.asyncio
    async def test_stores_user_message(self) -> None:
        """Test that user message is stored before generating response."""
        mock_settings = MagicMock()
        mock_settings.max_context_messages = 20
        mock_settings.openai_model = "gpt-4o"

        mock_openai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Agent response"
        mock_openai.chat.completions.create.return_value = mock_response

        conversation = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "phase": "discovery",
        }

        user_message = {
            "id": "880e8400-e29b-41d4-a716-446655440000",
            "conversation_id": "770e8400-e29b-41d4-a716-446655440000",
            "role": "user",
            "content": "Test message",
            "metadata": {},
            "created_at": "2024-01-01T00:00:00Z",
        }

        agent_message = {
            "id": "990e8400-e29b-41d4-a716-446655440000",
            "conversation_id": "770e8400-e29b-41d4-a716-446655440000",
            "role": "assistant",
            "content": "Agent response",
            "metadata": {"model": "gpt-4o"},
            "created_at": "2024-01-01T00:00:01Z",
        }

        with patch(
            "src.services.agent_service.get_openai_client", return_value=mock_openai
        ):
            with patch("src.services.agent_service.get_settings", return_value=mock_settings):
                with patch(
                    "src.services.agent_service.ConversationService"
                ) as mock_conv_service:
                    mock_conv_service.return_value.get_conversation.return_value = conversation
                    mock_conv_service.return_value.get_recent_messages.return_value = []
                    mock_conv_service.return_value.add_message.side_effect = [
                        user_message,
                        agent_message,
                    ]

                    service = AgentService()
                    user_msg, agent_msg = await service.generate_response(
                        conversation_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
                        user_message="Test message",
                    )

                    assert user_msg.content == "Test message"
                    assert agent_msg.content == "Agent response"

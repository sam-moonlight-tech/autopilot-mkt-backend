"""Integration tests for agent service with RAG context."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.models.conversation import ConversationPhase
from src.services.agent_service import AgentService


@pytest.fixture
def mock_openai_client() -> MagicMock:
    """Create mock OpenAI client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Agent response"))]
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_rag_service() -> MagicMock:
    """Create mock RAG service."""
    rag_service = MagicMock()
    rag_service.get_relevant_products_for_context = AsyncMock(
        return_value="Relevant products from our catalog:\n1. UR10e by Universal Robots (Collaborative Robot)"
    )
    return rag_service


@pytest.fixture
def mock_conversation_service() -> MagicMock:
    """Create mock conversation service."""
    conv_service = MagicMock()
    conv_service.get_conversation = AsyncMock(
        return_value={
            "id": str(uuid4()),
            "user_id": str(uuid4()),
            "phase": "selection",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
    )
    conv_service.get_recent_messages = AsyncMock(return_value=[])
    conv_service.add_message = AsyncMock(
        return_value={
            "id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "role": "user",
            "content": "test",
            "metadata": {},
            "created_at": "2024-01-01T00:00:00Z",
        }
    )
    return conv_service


class TestAgentServiceRAGIntegration:
    """Tests for AgentService with RAG integration."""

    @pytest.mark.asyncio
    async def test_build_context_includes_rag_for_selection_phase(
        self, mock_rag_service: MagicMock
    ) -> None:
        """Test that build_context includes RAG context in selection phase."""
        with patch("src.services.agent_service.get_openai_client"):
            with patch("src.services.agent_service.ConversationService") as mock_conv_cls:
                mock_conv = MagicMock()
                mock_conv.get_recent_messages = AsyncMock(return_value=[])
                mock_conv_cls.return_value = mock_conv

                service = AgentService(rag_service=mock_rag_service)
                conversation_id = uuid4()

                context = await service.build_context(
                    conversation_id=conversation_id,
                    phase=ConversationPhase.SELECTION,
                    current_message="I need a collaborative robot for palletizing",
                )

                # Verify RAG service was called
                mock_rag_service.get_relevant_products_for_context.assert_called_once_with(
                    query="I need a collaborative robot for palletizing",
                    top_k=5,
                )

                # Verify system prompt includes product context
                system_message = context[0]
                assert system_message["role"] == "system"
                assert "Relevant products from our catalog" in system_message["content"]
                assert "UR10e" in system_message["content"]

    @pytest.mark.asyncio
    async def test_build_context_includes_rag_for_roi_phase(
        self, mock_rag_service: MagicMock
    ) -> None:
        """Test that build_context includes RAG context in ROI phase."""
        with patch("src.services.agent_service.get_openai_client"):
            with patch("src.services.agent_service.ConversationService") as mock_conv_cls:
                mock_conv = MagicMock()
                mock_conv.get_recent_messages = AsyncMock(return_value=[])
                mock_conv_cls.return_value = mock_conv

                service = AgentService(rag_service=mock_rag_service)
                conversation_id = uuid4()

                context = await service.build_context(
                    conversation_id=conversation_id,
                    phase=ConversationPhase.ROI,
                    current_message="What's the ROI for a cobot?",
                )

                # Verify RAG service was called
                mock_rag_service.get_relevant_products_for_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_context_no_rag_for_discovery_phase(
        self, mock_rag_service: MagicMock
    ) -> None:
        """Test that build_context does not include RAG in discovery phase."""
        with patch("src.services.agent_service.get_openai_client"):
            with patch("src.services.agent_service.ConversationService") as mock_conv_cls:
                mock_conv = MagicMock()
                mock_conv.get_recent_messages = AsyncMock(return_value=[])
                mock_conv_cls.return_value = mock_conv

                service = AgentService(rag_service=mock_rag_service)
                conversation_id = uuid4()

                await service.build_context(
                    conversation_id=conversation_id,
                    phase=ConversationPhase.DISCOVERY,
                    current_message="Tell me about your company",
                )

                # RAG service should not be called in discovery phase
                mock_rag_service.get_relevant_products_for_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_build_context_no_rag_without_message(
        self, mock_rag_service: MagicMock
    ) -> None:
        """Test that build_context does not call RAG without current message."""
        with patch("src.services.agent_service.get_openai_client"):
            with patch("src.services.agent_service.ConversationService") as mock_conv_cls:
                mock_conv = MagicMock()
                mock_conv.get_recent_messages = AsyncMock(return_value=[])
                mock_conv_cls.return_value = mock_conv

                service = AgentService(rag_service=mock_rag_service)
                conversation_id = uuid4()

                await service.build_context(
                    conversation_id=conversation_id,
                    phase=ConversationPhase.SELECTION,
                    current_message=None,
                )

                # RAG service should not be called without a message
                mock_rag_service.get_relevant_products_for_context.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_response_with_rag_context(
        self,
        mock_openai_client: MagicMock,
        mock_rag_service: MagicMock,
        mock_conversation_service: MagicMock,
    ) -> None:
        """Test generate_response includes RAG context for product queries."""
        with patch("src.services.agent_service.get_openai_client", return_value=mock_openai_client):
            service = AgentService(rag_service=mock_rag_service)
            service.conversation_service = mock_conversation_service

            conversation_id = uuid4()

            user_msg, agent_msg = await service.generate_response(
                conversation_id=conversation_id,
                user_message="What collaborative robots do you have?",
            )

            # Verify RAG service was called
            mock_rag_service.get_relevant_products_for_context.assert_called_once()

            # Verify OpenAI was called
            mock_openai_client.chat.completions.create.assert_called_once()

            # Check the messages passed to OpenAI include product context
            call_args = mock_openai_client.chat.completions.create.call_args
            messages = call_args.kwargs["messages"]
            system_message = messages[0]["content"]
            assert "Relevant products from our catalog" in system_message

    @pytest.mark.asyncio
    async def test_rag_error_handled_gracefully(
        self,
        mock_openai_client: MagicMock,
        mock_conversation_service: MagicMock,
    ) -> None:
        """Test that RAG errors don't break the agent response."""
        # Create a RAG service that raises an error
        failing_rag_service = MagicMock()
        failing_rag_service.get_relevant_products_for_context = AsyncMock(
            return_value=""  # RAGService returns empty string on error
        )

        with patch("src.services.agent_service.get_openai_client", return_value=mock_openai_client):
            service = AgentService(rag_service=failing_rag_service)
            service.conversation_service = mock_conversation_service

            conversation_id = uuid4()

            # Should not raise, just proceed without RAG context
            user_msg, agent_msg = await service.generate_response(
                conversation_id=conversation_id,
                user_message="What robots do you have?",
            )

            # Verify response was still generated
            assert agent_msg.content == "Agent response"


class TestRAGContextFormatting:
    """Tests for RAG context formatting in agent prompts."""

    @pytest.mark.asyncio
    async def test_product_context_appended_to_system_prompt(self) -> None:
        """Test that product context is properly appended to system prompt."""
        mock_rag_service = MagicMock()
        mock_rag_service.get_relevant_products_for_context = AsyncMock(
            return_value="Relevant products from our catalog:\n1. Product A\n2. Product B"
        )

        with patch("src.services.agent_service.get_openai_client"):
            with patch("src.services.agent_service.ConversationService") as mock_conv_cls:
                mock_conv = MagicMock()
                mock_conv.get_recent_messages = AsyncMock(return_value=[])
                mock_conv_cls.return_value = mock_conv

                service = AgentService(rag_service=mock_rag_service)

                context = await service.build_context(
                    conversation_id=uuid4(),
                    phase=ConversationPhase.SELECTION,
                    current_message="Show me robots",
                )

                system_content = context[0]["content"]

                # Should contain both original system prompt and product context
                assert "You are Autopilot" in system_content
                assert "Relevant products from our catalog" in system_content
                assert "Product A" in system_content
                assert "Product B" in system_content

    @pytest.mark.asyncio
    async def test_empty_rag_context_not_appended(self) -> None:
        """Test that empty RAG context is not appended to system prompt."""
        mock_rag_service = MagicMock()
        mock_rag_service.get_relevant_products_for_context = AsyncMock(return_value="")

        with patch("src.services.agent_service.get_openai_client"):
            with patch("src.services.agent_service.ConversationService") as mock_conv_cls:
                mock_conv = MagicMock()
                mock_conv.get_recent_messages = AsyncMock(return_value=[])
                mock_conv_cls.return_value = mock_conv

                service = AgentService(rag_service=mock_rag_service)

                context = await service.build_context(
                    conversation_id=uuid4(),
                    phase=ConversationPhase.SELECTION,
                    current_message="Show me robots",
                )

                system_content = context[0]["content"]

                # Should only contain original system prompt
                assert "You are Autopilot" in system_content
                assert "Relevant products" not in system_content

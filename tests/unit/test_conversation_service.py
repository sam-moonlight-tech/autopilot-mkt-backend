"""Unit tests for ConversationService."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from src.models.conversation import ConversationPhase
from src.services.conversation_service import ConversationService


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Create a mock Supabase client."""
    return MagicMock()


@pytest.fixture
def conversation_service(mock_supabase: MagicMock) -> ConversationService:
    """Create ConversationService with mocked client."""
    with patch(
        "src.services.conversation_service.get_supabase_client", return_value=mock_supabase
    ):
        with patch("src.services.conversation_service.CompanyService"):
            return ConversationService()


class TestCreateConversation:
    """Tests for create_conversation method."""

    @pytest.mark.asyncio
    async def test_creates_with_defaults(
        self, conversation_service: ConversationService, mock_supabase: MagicMock
    ) -> None:
        """Test that conversation is created with default values."""
        created_conversation = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "New Conversation",
            "phase": "discovery",
            "metadata": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        mock_response = MagicMock()
        mock_response.data = [created_conversation]
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            mock_response
        )

        result = await conversation_service.create_conversation(
            user_profile_id=UUID("550e8400-e29b-41d4-a716-446655440000")
        )

        assert result["title"] == "New Conversation"
        assert result["phase"] == "discovery"

    @pytest.mark.asyncio
    async def test_creates_with_custom_title(
        self, conversation_service: ConversationService, mock_supabase: MagicMock
    ) -> None:
        """Test that custom title is used when provided."""
        from src.schemas.conversation import ConversationCreate

        created_conversation = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "Custom Title",
            "phase": "discovery",
            "metadata": {},
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        mock_response = MagicMock()
        mock_response.data = [created_conversation]
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            mock_response
        )

        result = await conversation_service.create_conversation(
            user_profile_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            data=ConversationCreate(title="Custom Title"),
        )

        assert result["title"] == "Custom Title"


class TestCanAccess:
    """Tests for can_access method."""

    @pytest.mark.asyncio
    async def test_returns_true_for_owner(
        self, conversation_service: ConversationService, mock_supabase: MagicMock
    ) -> None:
        """Test that True is returned for conversation owner."""
        conversation = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "company_id": None,
        }

        mock_response = MagicMock()
        mock_response.data = conversation
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_response
        )

        result = await conversation_service.can_access(
            conversation_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
            profile_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_non_owner(
        self, conversation_service: ConversationService, mock_supabase: MagicMock
    ) -> None:
        """Test that False is returned for non-owner without company access."""
        conversation = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "company_id": None,
        }

        mock_response = MagicMock()
        mock_response.data = conversation
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_response
        )

        result = await conversation_service.can_access(
            conversation_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
            profile_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
        )

        assert result is False


class TestListConversations:
    """Tests for list_conversations method."""

    @pytest.mark.asyncio
    async def test_returns_paginated_results(
        self, conversation_service: ConversationService, mock_supabase: MagicMock
    ) -> None:
        """Test that conversations are returned with pagination."""
        conversations = [
            {
                "id": "770e8400-e29b-41d4-a716-446655440000",
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Test Conversation",
                "phase": "discovery",
                "metadata": {},
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "messages": [{"count": 5}],
            }
        ]

        mock_response = MagicMock()
        mock_response.data = conversations
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            mock_response
        )

        # Mock for last message time
        mock_msg_response = MagicMock()
        mock_msg_response.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = (
            mock_msg_response
        )

        result, next_cursor, has_more = await conversation_service.list_conversations(
            profile_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            limit=20,
        )

        assert len(result) == 1
        assert result[0].title == "Test Conversation"

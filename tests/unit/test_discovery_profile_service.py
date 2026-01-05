"""Unit tests for DiscoveryProfileService."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from src.services.discovery_profile_service import DiscoveryProfileService


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Create a mock Supabase client."""
    return MagicMock()


@pytest.fixture
def discovery_service(mock_supabase: MagicMock) -> DiscoveryProfileService:
    """Create DiscoveryProfileService with mocked client."""
    with patch(
        "src.services.discovery_profile_service.get_supabase_client",
        return_value=mock_supabase,
    ):
        return DiscoveryProfileService()


class TestGetOrCreate:
    """Tests for get_or_create method."""

    @pytest.mark.asyncio
    async def test_returns_existing_profile(
        self, discovery_service: DiscoveryProfileService, mock_supabase: MagicMock
    ) -> None:
        """Test that existing discovery profile is returned."""
        existing_profile = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "profile_id": "660e8400-e29b-41d4-a716-446655440000",
            "phase": "discovery",
            "answers": {},
        }

        mock_response = MagicMock()
        mock_response.data = [existing_profile]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        result = await discovery_service.get_or_create(
            profile_id=UUID("660e8400-e29b-41d4-a716-446655440000")
        )

        assert result == existing_profile
        mock_supabase.table.assert_called_with("discovery_profiles")

    @pytest.mark.asyncio
    async def test_creates_new_profile_when_not_exists(
        self, discovery_service: DiscoveryProfileService, mock_supabase: MagicMock
    ) -> None:
        """Test that new discovery profile is created when none exists."""
        new_profile = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "profile_id": "660e8400-e29b-41d4-a716-446655440000",
            "current_question_index": 0,
            "phase": "discovery",
            "answers": {},
        }

        # First call returns empty (no existing profile)
        empty_response = MagicMock()
        empty_response.data = []

        # Second call returns created profile
        create_response = MagicMock()
        create_response.data = [new_profile]

        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            empty_response
        )
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            create_response
        )

        result = await discovery_service.get_or_create(
            profile_id=UUID("660e8400-e29b-41d4-a716-446655440000")
        )

        assert result == new_profile


class TestUpdate:
    """Tests for update method."""

    @pytest.mark.asyncio
    async def test_updates_allowed_fields(
        self, discovery_service: DiscoveryProfileService, mock_supabase: MagicMock
    ) -> None:
        """Test that discovery profile is updated with allowed fields."""
        from src.schemas.discovery import DiscoveryProfileUpdate

        updated_profile = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "profile_id": "660e8400-e29b-41d4-a716-446655440000",
            "phase": "roi",
            "current_question_index": 10,
        }

        mock_response = MagicMock()
        mock_response.data = [updated_profile]
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        update_data = DiscoveryProfileUpdate(phase="roi", current_question_index=10)
        result = await discovery_service.update(
            profile_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            data=update_data,
        )

        assert result["phase"] == "roi"
        assert result["current_question_index"] == 10

    @pytest.mark.asyncio
    async def test_returns_current_profile_when_no_changes(
        self, discovery_service: DiscoveryProfileService, mock_supabase: MagicMock
    ) -> None:
        """Test that current profile is returned when no changes provided."""
        from src.schemas.discovery import DiscoveryProfileUpdate

        existing_profile = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "profile_id": "660e8400-e29b-41d4-a716-446655440000",
            "phase": "discovery",
        }

        mock_response = MagicMock()
        mock_response.data = existing_profile
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        update_data = DiscoveryProfileUpdate()  # Empty update
        result = await discovery_service.update(
            profile_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            data=update_data,
        )

        assert result == existing_profile


class TestCreateFromSession:
    """Tests for create_from_session method."""

    @pytest.mark.asyncio
    async def test_creates_profile_from_session_data(
        self, discovery_service: DiscoveryProfileService, mock_supabase: MagicMock
    ) -> None:
        """Test that discovery profile is created from session data."""
        session_data = {
            "current_question_index": 5,
            "phase": "roi",
            "answers": {"q1": {"key": "val"}},
            "roi_inputs": {"laborRate": 50.0},
            "selected_product_ids": ["product-id-1"],
            "timeframe": "monthly",
        }

        new_profile = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "profile_id": "660e8400-e29b-41d4-a716-446655440000",
            **session_data,
        }

        # First check returns no existing profile
        empty_response = MagicMock()
        empty_response.data = None
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            empty_response
        )

        # Then create returns new profile
        create_response = MagicMock()
        create_response.data = [new_profile]
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            create_response
        )

        result = await discovery_service.create_from_session(
            profile_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            session_data=session_data,
        )

        assert result["phase"] == "roi"
        assert result["current_question_index"] == 5

    @pytest.mark.asyncio
    async def test_updates_existing_profile_from_session_data(
        self, discovery_service: DiscoveryProfileService, mock_supabase: MagicMock
    ) -> None:
        """Test that existing discovery profile is updated from session data."""
        session_data = {
            "current_question_index": 5,
            "phase": "roi",
            "answers": {},
            "roi_inputs": None,
            "selected_product_ids": [],
            "timeframe": None,
        }

        existing_profile = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "profile_id": "660e8400-e29b-41d4-a716-446655440000",
            "phase": "discovery",
        }

        updated_profile = {
            **existing_profile,
            **session_data,
        }

        # First check returns existing profile
        existing_response = MagicMock()
        existing_response.data = existing_profile
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            existing_response
        )

        # Then update returns updated profile
        update_response = MagicMock()
        update_response.data = [updated_profile]
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            update_response
        )

        result = await discovery_service.create_from_session(
            profile_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            session_data=session_data,
        )

        assert result["phase"] == "roi"

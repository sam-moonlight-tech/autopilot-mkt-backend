"""Unit tests for ProfileService."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from src.services.profile_service import ProfileService


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Create a mock Supabase client."""
    return MagicMock()


@pytest.fixture
def profile_service(mock_supabase: MagicMock) -> ProfileService:
    """Create ProfileService with mocked client."""
    with patch("src.services.profile_service.get_supabase_client", return_value=mock_supabase):
        return ProfileService()


class TestGetOrCreateProfile:
    """Tests for get_or_create_profile method."""

    @pytest.mark.asyncio
    async def test_returns_existing_profile(
        self, profile_service: ProfileService, mock_supabase: MagicMock
    ) -> None:
        """Test that existing profile is returned."""
        existing_profile = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "660e8400-e29b-41d4-a716-446655440000",
            "display_name": "Test User",
            "email": "test@example.com",
        }

        mock_response = MagicMock()
        mock_response.data = [existing_profile]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        result = await profile_service.get_or_create_profile(
            user_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            email="test@example.com",
        )

        assert result == existing_profile
        mock_supabase.table.assert_called_with("profiles")

    @pytest.mark.asyncio
    async def test_creates_new_profile_when_not_exists(
        self, profile_service: ProfileService, mock_supabase: MagicMock
    ) -> None:
        """Test that new profile is created when none exists."""
        new_profile = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "660e8400-e29b-41d4-a716-446655440000",
            "display_name": "new@example.com",
            "email": "new@example.com",
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

        result = await profile_service.get_or_create_profile(
            user_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            email="new@example.com",
        )

        assert result == new_profile


class TestUpdateProfile:
    """Tests for update_profile method."""

    @pytest.mark.asyncio
    async def test_updates_allowed_fields(
        self, profile_service: ProfileService, mock_supabase: MagicMock
    ) -> None:
        """Test that profile is updated with allowed fields."""
        from src.schemas.profile import ProfileUpdate

        updated_profile = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "660e8400-e29b-41d4-a716-446655440000",
            "display_name": "Updated Name",
            "email": "test@example.com",
        }

        mock_response = MagicMock()
        mock_response.data = [updated_profile]
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        update_data = ProfileUpdate(display_name="Updated Name")
        result = await profile_service.update_profile(
            user_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            data=update_data,
        )

        assert result["display_name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_returns_current_profile_when_no_changes(
        self, profile_service: ProfileService, mock_supabase: MagicMock
    ) -> None:
        """Test that current profile is returned when no changes provided."""
        from src.schemas.profile import ProfileUpdate

        existing_profile = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "660e8400-e29b-41d4-a716-446655440000",
            "display_name": "Test User",
        }

        mock_response = MagicMock()
        mock_response.data = existing_profile
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        update_data = ProfileUpdate()  # Empty update
        result = await profile_service.update_profile(
            user_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            data=update_data,
        )

        assert result == existing_profile


class TestGetUserCompanies:
    """Tests for get_user_companies method."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_profile(
        self, profile_service: ProfileService, mock_supabase: MagicMock
    ) -> None:
        """Test that empty list is returned when user has no profile."""
        mock_response = MagicMock()
        mock_response.data = None
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        result = await profile_service.get_user_companies(
            user_id=UUID("660e8400-e29b-41d4-a716-446655440000")
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_companies_with_roles(
        self, profile_service: ProfileService, mock_supabase: MagicMock
    ) -> None:
        """Test that companies are returned with user roles."""
        profile = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "660e8400-e29b-41d4-a716-446655440000",
        }

        memberships = [
            {
                "role": "owner",
                "joined_at": "2024-01-01T00:00:00Z",
                "companies": {"id": "770e8400-e29b-41d4-a716-446655440000", "name": "Test Co"},
            }
        ]

        profile_response = MagicMock()
        profile_response.data = profile

        membership_response = MagicMock()
        membership_response.data = memberships

        # Set up the mock chain for profile fetch
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            profile_response
        )
        # Set up the mock chain for membership fetch
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            membership_response
        )

        result = await profile_service.get_user_companies(
            user_id=UUID("660e8400-e29b-41d4-a716-446655440000")
        )

        assert len(result) == 1
        assert result[0].name == "Test Co"
        assert result[0].role == "owner"

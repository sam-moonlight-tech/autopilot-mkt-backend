"""Unit tests for CompanyService."""

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from src.api.middleware.error_handler import AuthorizationError, NotFoundError
from src.services.company_service import CompanyService


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Create a mock Supabase client."""
    return MagicMock()


@pytest.fixture
def company_service(mock_supabase: MagicMock) -> CompanyService:
    """Create CompanyService with mocked client."""
    with patch("src.services.company_service.get_supabase_client", return_value=mock_supabase):
        return CompanyService()


class TestCreateCompany:
    """Tests for create_company method."""

    @pytest.mark.asyncio
    async def test_creates_company_and_adds_owner_as_member(
        self, company_service: CompanyService, mock_supabase: MagicMock
    ) -> None:
        """Test that company is created and owner is added as member."""
        from src.schemas.company import CompanyCreate

        created_company = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "name": "Test Company",
            "owner_id": "550e8400-e29b-41d4-a716-446655440000",
        }

        company_response = MagicMock()
        company_response.data = [created_company]
        mock_supabase.table.return_value.insert.return_value.execute.return_value = (
            company_response
        )

        result = await company_service.create_company(
            data=CompanyCreate(name="Test Company"),
            owner_profile_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        )

        assert result["name"] == "Test Company"
        # Verify member was added
        calls = mock_supabase.table.call_args_list
        assert any(call[0][0] == "company_members" for call in calls)


class TestIsMember:
    """Tests for is_member method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_member(
        self, company_service: CompanyService, mock_supabase: MagicMock
    ) -> None:
        """Test that True is returned when user is a member."""
        mock_response = MagicMock()
        mock_response.data = [{"id": "some-id"}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        result = await company_service.is_member(
            company_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
            profile_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_member(
        self, company_service: CompanyService, mock_supabase: MagicMock
    ) -> None:
        """Test that False is returned when user is not a member."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        result = await company_service.is_member(
            company_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
            profile_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        )

        assert result is False


class TestIsOwner:
    """Tests for is_owner method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_owner(
        self, company_service: CompanyService, mock_supabase: MagicMock
    ) -> None:
        """Test that True is returned when user is the owner."""
        mock_response = MagicMock()
        mock_response.data = [{"id": "770e8400-e29b-41d4-a716-446655440000"}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        result = await company_service.is_owner(
            company_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
            profile_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_owner(
        self, company_service: CompanyService, mock_supabase: MagicMock
    ) -> None:
        """Test that False is returned when user is not the owner."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        result = await company_service.is_owner(
            company_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
            profile_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        )

        assert result is False


class TestRemoveMember:
    """Tests for remove_member method."""

    @pytest.mark.asyncio
    async def test_prevents_owner_removal(
        self, company_service: CompanyService, mock_supabase: MagicMock
    ) -> None:
        """Test that owner cannot be removed."""
        # Mock is_owner to return True for requester (first call) and target (second call)
        mock_response = MagicMock()
        mock_response.data = [{"id": "some-id"}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        with pytest.raises(AuthorizationError) as exc_info:
            await company_service.remove_member(
                company_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
                profile_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                requester_profile_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            )

        assert "Cannot remove company owner" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_raises_authorization_error_when_not_owner(
        self, company_service: CompanyService, mock_supabase: MagicMock
    ) -> None:
        """Test that non-owner cannot remove members."""
        mock_response = MagicMock()
        mock_response.data = []  # Not owner
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        with pytest.raises(AuthorizationError) as exc_info:
            await company_service.remove_member(
                company_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
                profile_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
                requester_profile_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            )

        assert "Only company owner" in str(exc_info.value.message)

"""Unit tests for RobotCatalogService."""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from src.services.robot_catalog_service import RobotCatalogService


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Create a mock Supabase client."""
    return MagicMock()


@pytest.fixture
def robot_catalog_service(mock_supabase: MagicMock) -> RobotCatalogService:
    """Create RobotCatalogService with mocked client."""
    with patch("src.services.robot_catalog_service.get_supabase_client", return_value=mock_supabase):
        return RobotCatalogService()


@pytest.fixture
def sample_robot() -> dict:
    """Create a sample robot for testing."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Pudu CC1 Pro",
        "category": "Floor Cleaner",
        "best_for": "Large commercial spaces",
        "modes": ["Scrub", "Vacuum", "Sweep"],
        "surfaces": ["Hard Floor", "Carpet"],
        "monthly_lease": Decimal("1200.00"),
        "purchase_price": Decimal("45000.00"),
        "time_efficiency": Decimal("0.75"),
        "key_reasons": ["Industrial grade", "Large capacity"],
        "specs": ["Battery: 8 hours", "Tank: 100L"],
        "image_url": "https://example.com/robot.jpg",
        "stripe_product_id": "prod_123",
        "stripe_lease_price_id": "price_123",
        "active": True,
    }


@pytest.fixture
def sample_robots(sample_robot: dict) -> list[dict]:
    """Create a list of sample robots."""
    inactive_robot = sample_robot.copy()
    inactive_robot["id"] = "660e8400-e29b-41d4-a716-446655440000"
    inactive_robot["name"] = "Inactive Robot"
    inactive_robot["active"] = False

    second_robot = sample_robot.copy()
    second_robot["id"] = "770e8400-e29b-41d4-a716-446655440000"
    second_robot["name"] = "BudgetVac Mini"

    return [sample_robot, second_robot, inactive_robot]


class TestListRobots:
    """Tests for list_robots method."""

    @pytest.mark.asyncio
    async def test_returns_active_robots_by_default(
        self,
        robot_catalog_service: RobotCatalogService,
        mock_supabase: MagicMock,
        sample_robots: list[dict],
    ) -> None:
        """Test that only active robots are returned by default."""
        active_robots = [r for r in sample_robots if r["active"]]

        mock_response = MagicMock()
        mock_response.data = active_robots
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = (
            mock_response
        )

        result = await robot_catalog_service.list_robots()

        assert len(result) == 2
        assert all(r["active"] for r in result)

    @pytest.mark.asyncio
    async def test_returns_all_robots_when_active_only_false(
        self,
        robot_catalog_service: RobotCatalogService,
        mock_supabase: MagicMock,
        sample_robots: list[dict],
    ) -> None:
        """Test that all robots are returned when active_only=False."""
        mock_response = MagicMock()
        mock_response.data = sample_robots
        mock_supabase.table.return_value.select.return_value.order.return_value.execute.return_value = (
            mock_response
        )

        result = await robot_catalog_service.list_robots(active_only=False)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_robots(
        self,
        robot_catalog_service: RobotCatalogService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that empty list is returned when no robots exist."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = (
            mock_response
        )

        result = await robot_catalog_service.list_robots()

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_none_response_data(
        self,
        robot_catalog_service: RobotCatalogService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that None response data returns empty list."""
        mock_response = MagicMock()
        mock_response.data = None
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = (
            mock_response
        )

        result = await robot_catalog_service.list_robots()

        assert result == []


class TestGetRobot:
    """Tests for get_robot method."""

    @pytest.mark.asyncio
    async def test_returns_robot_when_found(
        self,
        robot_catalog_service: RobotCatalogService,
        mock_supabase: MagicMock,
        sample_robot: dict,
    ) -> None:
        """Test that robot is returned when ID is valid."""
        mock_response = MagicMock()
        mock_response.data = sample_robot
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        result = await robot_catalog_service.get_robot(
            UUID("550e8400-e29b-41d4-a716-446655440000")
        )

        assert result == sample_robot
        assert result["name"] == "Pudu CC1 Pro"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(
        self,
        robot_catalog_service: RobotCatalogService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that None is returned when robot not found."""
        mock_response = MagicMock()
        mock_response.data = None
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        result = await robot_catalog_service.get_robot(
            UUID("550e8400-e29b-41d4-a716-446655440000")
        )

        assert result is None


class TestGetRobotWithStripeIds:
    """Tests for get_robot_with_stripe_ids method."""

    @pytest.mark.asyncio
    async def test_returns_robot_with_stripe_fields(
        self,
        robot_catalog_service: RobotCatalogService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that robot with Stripe IDs is returned."""
        stripe_robot = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Pudu CC1 Pro",
            "monthly_lease": Decimal("1200.00"),
            "stripe_product_id": "prod_123",
            "stripe_lease_price_id": "price_123",
            "active": True,
        }

        mock_response = MagicMock()
        mock_response.data = stripe_robot
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        result = await robot_catalog_service.get_robot_with_stripe_ids(
            UUID("550e8400-e29b-41d4-a716-446655440000")
        )

        assert result is not None
        assert result["stripe_product_id"] == "prod_123"
        assert result["stripe_lease_price_id"] == "price_123"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(
        self,
        robot_catalog_service: RobotCatalogService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that None is returned when robot not found."""
        mock_response = MagicMock()
        mock_response.data = None
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        result = await robot_catalog_service.get_robot_with_stripe_ids(
            UUID("550e8400-e29b-41d4-a716-446655440000")
        )

        assert result is None


class TestGetRobotsByIds:
    """Tests for get_robots_by_ids method."""

    @pytest.mark.asyncio
    async def test_returns_robots_for_valid_ids(
        self,
        robot_catalog_service: RobotCatalogService,
        mock_supabase: MagicMock,
        sample_robots: list[dict],
    ) -> None:
        """Test that robots are returned for valid IDs."""
        mock_response = MagicMock()
        mock_response.data = sample_robots[:2]
        mock_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value = (
            mock_response
        )

        result = await robot_catalog_service.get_robots_by_ids([
            UUID("550e8400-e29b-41d4-a716-446655440000"),
            UUID("770e8400-e29b-41d4-a716-446655440000"),
        ])

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_empty_input(
        self,
        robot_catalog_service: RobotCatalogService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that empty list is returned for empty input."""
        result = await robot_catalog_service.get_robots_by_ids([])

        assert result == []
        # Verify no database call was made
        mock_supabase.table.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_none_response_data(
        self,
        robot_catalog_service: RobotCatalogService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that None response data returns empty list."""
        mock_response = MagicMock()
        mock_response.data = None
        mock_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value = (
            mock_response
        )

        result = await robot_catalog_service.get_robots_by_ids([
            UUID("550e8400-e29b-41d4-a716-446655440000"),
        ])

        assert result == []

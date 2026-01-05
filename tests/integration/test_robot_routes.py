"""Integration tests for robot catalog API endpoints."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


@patch("src.services.robot_catalog_service.get_supabase_client")
class TestListRobots:
    """Tests for GET /api/v1/robots endpoint."""

    def test_returns_list_of_robots(
        self, mock_supabase: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that list of robots is returned."""
        robots = [
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Pudu CC1 Pro",
                "category": "Floor Cleaner",
                "best_for": "Large commercial spaces",
                "modes": ["Scrub", "Vacuum"],
                "surfaces": ["Hard Floor", "Carpet"],
                "monthly_lease": Decimal("1200.00"),
                "purchase_price": Decimal("45000.00"),
                "time_efficiency": Decimal("0.75"),
                "key_reasons": ["Industrial grade"],
                "specs": ["Battery: 8 hours"],
                "image_url": "https://example.com/robot.jpg",
                "active": True,
            },
            {
                "id": "660e8400-e29b-41d4-a716-446655440000",
                "name": "BudgetVac Mini",
                "category": "Floor Cleaner",
                "best_for": "Small offices",
                "modes": ["Vacuum"],
                "surfaces": ["Hard Floor"],
                "monthly_lease": Decimal("700.00"),
                "purchase_price": Decimal("25000.00"),
                "time_efficiency": Decimal("0.60"),
                "key_reasons": ["Budget friendly"],
                "specs": ["Battery: 4 hours"],
                "image_url": None,
                "active": True,
            },
        ]

        mock_response = MagicMock()
        mock_response.data = robots
        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = (
            mock_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/robots")

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["items"][0]["name"] == "Pudu CC1 Pro"
            assert data["items"][1]["name"] == "BudgetVac Mini"

    def test_returns_camelcase_fields(
        self, mock_supabase: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that response includes camelCase computed fields."""
        robots = [
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Pudu CC1 Pro",
                "category": "Floor Cleaner",
                "best_for": "Large commercial spaces",
                "modes": ["Scrub"],
                "surfaces": ["Hard Floor"],
                "monthly_lease": Decimal("1200.00"),
                "purchase_price": Decimal("45000.00"),
                "time_efficiency": Decimal("0.75"),
                "key_reasons": ["Industrial grade"],
                "specs": ["Battery: 8 hours"],
                "image_url": None,
                "active": True,
            },
        ]

        mock_response = MagicMock()
        mock_response.data = robots
        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = (
            mock_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/robots")

            assert response.status_code == 200
            robot = response.json()["items"][0]

            # Check camelCase computed fields exist
            assert "monthlyLease" in robot
            assert "purchasePrice" in robot
            assert "timeEfficiency" in robot
            assert "bestFor" in robot
            assert "keyReasons" in robot

            # Check values are correct
            assert robot["monthlyLease"] == 1200.00
            assert robot["purchasePrice"] == 45000.00
            assert robot["timeEfficiency"] == 0.75

    def test_returns_empty_list_when_no_robots(
        self, mock_supabase: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that empty list is returned when no robots exist."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = (
            mock_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/robots")

            assert response.status_code == 200
            data = response.json()
            assert data["items"] == []


@patch("src.services.robot_catalog_service.get_supabase_client")
class TestGetRobot:
    """Tests for GET /api/v1/robots/{robot_id} endpoint."""

    def test_returns_robot_for_valid_id(
        self, mock_supabase: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that robot is returned for valid ID."""
        robot = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Pudu CC1 Pro",
            "category": "Floor Cleaner",
            "best_for": "Large commercial spaces",
            "modes": ["Scrub", "Vacuum"],
            "surfaces": ["Hard Floor", "Carpet"],
            "monthly_lease": Decimal("1200.00"),
            "purchase_price": Decimal("45000.00"),
            "time_efficiency": Decimal("0.75"),
            "key_reasons": ["Industrial grade"],
            "specs": ["Battery: 8 hours"],
            "image_url": "https://example.com/robot.jpg",
            "active": True,
        }

        mock_response = MagicMock()
        mock_response.data = robot
        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/robots/550e8400-e29b-41d4-a716-446655440000")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Pudu CC1 Pro"
            assert data["category"] == "Floor Cleaner"

    def test_returns_404_for_invalid_id(
        self, mock_supabase: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that 404 is returned for invalid ID."""
        mock_response = MagicMock()
        mock_response.data = None
        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/robots/550e8400-e29b-41d4-a716-446655440000")

            assert response.status_code == 404
            assert response.json()["detail"] == "Robot not found"

    def test_returns_422_for_invalid_uuid_format(
        self, mock_supabase: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that 422 is returned for invalid UUID format."""
        from src.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/robots/not-a-valid-uuid")

            assert response.status_code == 422

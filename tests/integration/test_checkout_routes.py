"""Integration tests for checkout API endpoints."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestCreateCheckoutSession:
    """Tests for POST /api/v1/checkout/session endpoint."""

    @patch("src.services.checkout_service.get_stripe")
    @patch("src.services.checkout_service.get_supabase_client")
    @patch("src.services.robot_catalog_service.get_supabase_client")
    @patch("src.services.session_service.get_supabase_client")
    def test_creates_checkout_session_for_anonymous_user(
        self,
        mock_session_supabase: MagicMock,
        mock_robot_supabase: MagicMock,
        mock_checkout_supabase: MagicMock,
        mock_stripe: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test checkout session creation for anonymous user with session cookie."""
        session_token = "a" * 64
        session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": session_token,
            "phase": "greenlight",
            "claimed_by_profile_id": None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }

        robot = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "name": "Pudu CC1 Pro",
            "monthly_lease": Decimal("1200.00"),
            "stripe_product_id": "prod_123",
            "stripe_lease_price_id": "price_123",
            "active": True,
        }

        order = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "status": "pending",
        }

        # Mock session lookup
        session_response = MagicMock()
        session_response.data = session
        mock_session_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            session_response
        )

        # Mock robot lookup
        robot_response = MagicMock()
        robot_response.data = robot
        mock_robot_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            robot_response
        )

        # Mock order creation
        order_response = MagicMock()
        order_response.data = [order]
        mock_checkout_supabase.return_value.table.return_value.insert.return_value.execute.return_value = (
            order_response
        )

        # Mock order update
        mock_checkout_supabase.return_value.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            MagicMock()
        )

        # Mock Stripe checkout session
        mock_stripe_session = MagicMock()
        mock_stripe_session.id = "cs_test_123"
        mock_stripe_session.url = "https://checkout.stripe.com/cs_test_123"
        mock_stripe.return_value.checkout.Session.create.return_value = mock_stripe_session

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/checkout/session",
                json={
                    "product_id": "660e8400-e29b-41d4-a716-446655440000",
                    "success_url": "https://example.com/success",
                    "cancel_url": "https://example.com/cancel",
                },
                cookies={"autopilot_session": session_token},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["checkout_url"] == "https://checkout.stripe.com/cs_test_123"
            assert data["stripe_session_id"] == "cs_test_123"

    @patch("src.services.checkout_service.get_stripe")
    @patch("src.services.checkout_service.get_supabase_client")
    @patch("src.services.robot_catalog_service.get_supabase_client")
    def test_returns_400_for_inactive_product(
        self,
        mock_robot_supabase: MagicMock,
        mock_checkout_supabase: MagicMock,
        mock_stripe: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that 400 is returned for inactive product."""
        inactive_robot = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "name": "Inactive Robot",
            "monthly_lease": Decimal("1200.00"),
            "stripe_product_id": "prod_123",
            "stripe_lease_price_id": "price_123",
            "active": False,
        }

        robot_response = MagicMock()
        robot_response.data = inactive_robot
        mock_robot_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            robot_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/checkout/session",
                json={
                    "product_id": "660e8400-e29b-41d4-a716-446655440000",
                    "success_url": "https://example.com/success",
                    "cancel_url": "https://example.com/cancel",
                },
            )

            assert response.status_code == 400
            assert "no longer available" in response.json()["detail"]

    @patch("src.services.robot_catalog_service.get_supabase_client")
    def test_returns_400_for_nonexistent_product(
        self,
        mock_robot_supabase: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that 400 is returned for non-existent product."""
        robot_response = MagicMock()
        robot_response.data = None
        mock_robot_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            robot_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/checkout/session",
                json={
                    "product_id": "660e8400-e29b-41d4-a716-446655440000",
                    "success_url": "https://example.com/success",
                    "cancel_url": "https://example.com/cancel",
                },
            )

            assert response.status_code == 400
            assert "not found" in response.json()["detail"]

    def test_returns_422_for_invalid_url_format(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Test that 422 is returned for invalid URL format."""
        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/checkout/session",
                json={
                    "product_id": "660e8400-e29b-41d4-a716-446655440000",
                    "success_url": "not-a-valid-url",
                    "cancel_url": "https://example.com/cancel",
                },
            )

            assert response.status_code == 422

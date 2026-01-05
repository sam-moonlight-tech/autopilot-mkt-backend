"""Integration tests for order API endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestListOrders:
    """Tests for GET /api/v1/orders endpoint."""

    @patch("src.services.checkout_service.get_supabase_client")
    @patch("src.services.session_service.get_supabase_client")
    def test_returns_orders_for_session(
        self,
        mock_session_supabase: MagicMock,
        mock_checkout_supabase: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that orders are returned for session owner."""
        session_token = "a" * 64
        session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": session_token,
            "phase": "greenlight",
            "claimed_by_profile_id": None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }

        orders = [
            {
                "id": "660e8400-e29b-41d4-a716-446655440000",
                "profile_id": None,
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "completed",
                "line_items": [
                    {
                        "product_id": "770e8400-e29b-41d4-a716-446655440000",
                        "product_name": "Pudu CC1 Pro",
                        "quantity": 1,
                        "unit_amount_cents": 120000,
                        "stripe_price_id": "price_123",
                    }
                ],
                "total_cents": 120000,
                "currency": "usd",
                "customer_email": "test@example.com",
                "stripe_subscription_id": "sub_123",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

        # Mock session lookup
        session_response = MagicMock()
        session_response.data = session
        mock_session_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            session_response
        )

        # Mock order lookup
        order_response = MagicMock()
        order_response.data = orders
        mock_checkout_supabase.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = (
            order_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/orders",
                cookies={"autopilot_session": session_token},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["status"] == "completed"

    @patch("src.services.checkout_service.get_supabase_client")
    @patch("src.services.session_service.get_supabase_client")
    def test_returns_empty_list_when_no_orders(
        self,
        mock_session_supabase: MagicMock,
        mock_checkout_supabase: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that empty list is returned when no orders exist."""
        session_token = "a" * 64
        session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": session_token,
            "phase": "discovery",
            "claimed_by_profile_id": None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }

        # Mock session lookup
        session_response = MagicMock()
        session_response.data = session
        mock_session_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            session_response
        )

        # Mock order lookup
        order_response = MagicMock()
        order_response.data = []
        mock_checkout_supabase.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = (
            order_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/orders",
                cookies={"autopilot_session": session_token},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["items"] == []


class TestGetOrder:
    """Tests for GET /api/v1/orders/{order_id} endpoint."""

    @patch("src.services.checkout_service.get_supabase_client")
    @patch("src.services.session_service.get_supabase_client")
    def test_returns_order_for_owner(
        self,
        mock_session_supabase: MagicMock,
        mock_checkout_supabase: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that order is returned for session owner."""
        session_token = "a" * 64
        session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": session_token,
            "phase": "greenlight",
            "claimed_by_profile_id": None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }

        order = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "profile_id": None,
            "session_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "completed",
            "line_items": [
                {
                    "product_id": "770e8400-e29b-41d4-a716-446655440000",
                    "product_name": "Pudu CC1 Pro",
                    "quantity": 1,
                    "unit_amount_cents": 120000,
                    "stripe_price_id": "price_123",
                }
            ],
            "total_cents": 120000,
            "currency": "usd",
            "customer_email": "test@example.com",
            "stripe_subscription_id": "sub_123",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Mock session lookup
        session_response = MagicMock()
        session_response.data = session
        mock_session_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            session_response
        )

        # Mock order lookup
        order_response = MagicMock()
        order_response.data = order
        mock_checkout_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            order_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/orders/660e8400-e29b-41d4-a716-446655440000",
                cookies={"autopilot_session": session_token},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"

    @patch("src.services.checkout_service.get_supabase_client")
    @patch("src.services.session_service.get_supabase_client")
    def test_returns_403_for_non_owner(
        self,
        mock_session_supabase: MagicMock,
        mock_checkout_supabase: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that 403 is returned for non-owner."""
        session_token = "a" * 64
        session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": session_token,
            "phase": "discovery",
            "claimed_by_profile_id": None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }

        # Order belongs to a different session
        order = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "profile_id": None,
            "session_id": "880e8400-e29b-41d4-a716-446655440000",  # Different session
            "status": "completed",
            "line_items": [],
            "total_cents": 120000,
            "currency": "usd",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Mock session lookup
        session_response = MagicMock()
        session_response.data = session
        mock_session_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            session_response
        )

        # Mock order lookup
        order_response = MagicMock()
        order_response.data = order
        mock_checkout_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            order_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/orders/660e8400-e29b-41d4-a716-446655440000",
                cookies={"autopilot_session": session_token},
            )

            assert response.status_code == 403
            assert "Not authorized" in response.json()["detail"]

    @patch("src.services.checkout_service.get_supabase_client")
    @patch("src.services.session_service.get_supabase_client")
    def test_returns_404_for_nonexistent_order(
        self,
        mock_session_supabase: MagicMock,
        mock_checkout_supabase: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that 404 is returned for non-existent order."""
        session_token = "a" * 64
        session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": session_token,
            "phase": "discovery",
            "claimed_by_profile_id": None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }

        # Mock session lookup
        session_response = MagicMock()
        session_response.data = session
        mock_session_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            session_response
        )

        # Mock order lookup - not found
        order_response = MagicMock()
        order_response.data = None
        mock_checkout_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            order_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/orders/660e8400-e29b-41d4-a716-446655440000",
                cookies={"autopilot_session": session_token},
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"]

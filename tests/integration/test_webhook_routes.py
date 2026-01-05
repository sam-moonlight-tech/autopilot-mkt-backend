"""Integration tests for webhook API endpoints."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import stripe
from fastapi.testclient import TestClient


class TestStripeWebhook:
    """Tests for POST /api/v1/webhooks/stripe endpoint."""

    @patch("src.services.checkout_service.get_settings")
    @patch("src.services.checkout_service.get_stripe")
    @patch("src.services.checkout_service.get_supabase_client")
    def test_handles_checkout_completed_event(
        self,
        mock_supabase: MagicMock,
        mock_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that checkout.session.completed event is processed."""
        mock_settings.return_value.stripe_webhook_secret = "whsec_test"

        event = {
            "id": "evt_123",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "metadata": {"order_id": "660e8400-e29b-41d4-a716-446655440000"},
                    "customer": "cus_123",
                    "subscription": "sub_123",
                    "customer_details": {"email": "test@example.com"},
                }
            },
        }

        # Mock signature verification
        mock_stripe.return_value.Webhook.construct_event.return_value = event

        # Mock order update
        order_response = MagicMock()
        order_response.data = [{"id": "660e8400-e29b-41d4-a716-446655440000", "status": "completed"}]
        mock_supabase.return_value.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            order_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/webhooks/stripe",
                content=b'{"test": "payload"}',
                headers={"stripe-signature": "valid_signature"},
            )

            assert response.status_code == 200
            assert response.json()["status"] == "received"

    @patch("src.services.checkout_service.get_settings")
    @patch("src.services.checkout_service.get_stripe")
    @patch("src.services.checkout_service.get_supabase_client")
    def test_handles_checkout_expired_event(
        self,
        mock_supabase: MagicMock,
        mock_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that checkout.session.expired event is processed."""
        mock_settings.return_value.stripe_webhook_secret = "whsec_test"

        event = {
            "id": "evt_123",
            "type": "checkout.session.expired",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "metadata": {"order_id": "660e8400-e29b-41d4-a716-446655440000"},
                }
            },
        }

        # Mock signature verification
        mock_stripe.return_value.Webhook.construct_event.return_value = event

        # Mock order update
        order_response = MagicMock()
        order_response.data = [{"id": "660e8400-e29b-41d4-a716-446655440000", "status": "cancelled"}]
        mock_supabase.return_value.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            order_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/webhooks/stripe",
                content=b'{"test": "payload"}',
                headers={"stripe-signature": "valid_signature"},
            )

            assert response.status_code == 200
            assert response.json()["status"] == "received"

    @patch("src.services.checkout_service.get_settings")
    @patch("src.services.checkout_service.get_stripe")
    def test_returns_400_for_invalid_signature(
        self,
        mock_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that 400 is returned for invalid signature."""
        mock_settings.return_value.stripe_webhook_secret = "whsec_test"

        # Mock signature verification failure
        mock_stripe.return_value.Webhook.construct_event.side_effect = (
            stripe.error.SignatureVerificationError("Invalid", "sig")
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/webhooks/stripe",
                content=b'{"test": "payload"}',
                headers={"stripe-signature": "invalid_signature"},
            )

            assert response.status_code == 400
            assert "Invalid signature" in response.json()["detail"]

    def test_returns_400_for_missing_signature_header(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Test that 400 is returned for missing signature header."""
        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/webhooks/stripe",
                content=b'{"test": "payload"}',
                # No stripe-signature header
            )

            assert response.status_code == 400
            assert "Missing Stripe-Signature" in response.json()["detail"]

    @patch("src.services.checkout_service.get_settings")
    @patch("src.services.checkout_service.get_stripe")
    def test_returns_200_for_unhandled_event_types(
        self,
        mock_stripe: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that 200 is returned for unhandled event types (idempotent)."""
        mock_settings.return_value.stripe_webhook_secret = "whsec_test"

        event = {
            "id": "evt_123",
            "type": "customer.created",  # Unhandled event type
            "data": {
                "object": {"id": "cus_123"}
            },
        }

        # Mock signature verification
        mock_stripe.return_value.Webhook.construct_event.return_value = event

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/webhooks/stripe",
                content=b'{"test": "payload"}',
                headers={"stripe-signature": "valid_signature"},
            )

            # Should return 200 even for unhandled events
            assert response.status_code == 200
            assert response.json()["status"] == "received"

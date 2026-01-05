"""Unit tests for CheckoutService."""

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
import stripe

from src.services.checkout_service import CheckoutService


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Create a mock Supabase client."""
    return MagicMock()


@pytest.fixture
def mock_stripe() -> MagicMock:
    """Create a mock Stripe client."""
    return MagicMock()


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings."""
    settings = MagicMock()
    settings.stripe_webhook_secret = "whsec_test_secret"
    return settings


@pytest.fixture
def checkout_service(
    mock_supabase: MagicMock, mock_stripe: MagicMock, mock_settings: MagicMock
) -> CheckoutService:
    """Create CheckoutService with mocked dependencies."""
    with patch("src.services.checkout_service.get_supabase_client", return_value=mock_supabase), \
         patch("src.services.checkout_service.get_stripe", return_value=mock_stripe), \
         patch("src.services.checkout_service.get_settings", return_value=mock_settings):
        return CheckoutService()


@pytest.fixture
def sample_robot() -> dict:
    """Create a sample robot for testing."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Pudu CC1 Pro",
        "monthly_lease": Decimal("1200.00"),
        "stripe_product_id": "prod_123",
        "stripe_lease_price_id": "price_123",
        "active": True,
    }


@pytest.fixture
def sample_order() -> dict:
    """Create a sample order for testing."""
    return {
        "id": "660e8400-e29b-41d4-a716-446655440000",
        "profile_id": "770e8400-e29b-41d4-a716-446655440000",
        "session_id": None,
        "stripe_checkout_session_id": "cs_test_123",
        "status": "pending",
        "line_items": [
            {
                "product_id": "550e8400-e29b-41d4-a716-446655440000",
                "product_name": "Pudu CC1 Pro",
                "quantity": 1,
                "unit_amount_cents": 120000,
                "stripe_price_id": "price_123",
            }
        ],
        "total_cents": 120000,
        "currency": "usd",
    }


class TestCreateCheckoutSession:
    """Tests for create_checkout_session method."""

    @pytest.mark.asyncio
    async def test_creates_checkout_session_for_authenticated_user(
        self,
        checkout_service: CheckoutService,
        mock_supabase: MagicMock,
        mock_stripe: MagicMock,
        sample_robot: dict,
    ) -> None:
        """Test checkout session creation for authenticated user."""
        # Mock robot catalog service
        with patch.object(
            checkout_service.robot_service,
            "get_robot_with_stripe_ids",
            return_value=sample_robot,
        ):
            # Mock order creation
            order_response = MagicMock()
            order_response.data = [{"id": "order-123"}]
            mock_supabase.table.return_value.insert.return_value.execute.return_value = (
                order_response
            )

            # Mock Stripe checkout session
            mock_stripe_session = MagicMock()
            mock_stripe_session.id = "cs_test_123"
            mock_stripe_session.url = "https://checkout.stripe.com/cs_test_123"
            mock_stripe.checkout.Session.create.return_value = mock_stripe_session

            # Mock order update
            mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = (
                MagicMock()
            )

            result = await checkout_service.create_checkout_session(
                product_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                profile_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
            )

            assert result["checkout_url"] == "https://checkout.stripe.com/cs_test_123"
            assert result["stripe_session_id"] == "cs_test_123"
            assert result["order_id"] == UUID("order-123")

    @pytest.mark.asyncio
    async def test_raises_error_for_inactive_product(
        self,
        checkout_service: CheckoutService,
        mock_supabase: MagicMock,
        sample_robot: dict,
    ) -> None:
        """Test that ValueError is raised for inactive product."""
        inactive_robot = sample_robot.copy()
        inactive_robot["active"] = False

        with patch.object(
            checkout_service.robot_service,
            "get_robot_with_stripe_ids",
            return_value=inactive_robot,
        ):
            with pytest.raises(ValueError, match="no longer available"):
                await checkout_service.create_checkout_session(
                    product_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                    success_url="https://example.com/success",
                    cancel_url="https://example.com/cancel",
                )

    @pytest.mark.asyncio
    async def test_raises_error_for_nonexistent_product(
        self,
        checkout_service: CheckoutService,
    ) -> None:
        """Test that ValueError is raised for non-existent product."""
        with patch.object(
            checkout_service.robot_service,
            "get_robot_with_stripe_ids",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="Product not found"):
                await checkout_service.create_checkout_session(
                    product_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                    success_url="https://example.com/success",
                    cancel_url="https://example.com/cancel",
                )


class TestVerifyWebhookSignature:
    """Tests for verify_webhook_signature method."""

    def test_returns_event_for_valid_signature(
        self,
        checkout_service: CheckoutService,
        mock_stripe: MagicMock,
    ) -> None:
        """Test that event is returned for valid signature."""
        expected_event = {
            "id": "evt_123",
            "type": "checkout.session.completed",
            "data": {"object": {}},
        }
        mock_stripe.Webhook.construct_event.return_value = expected_event

        result = checkout_service.verify_webhook_signature(
            payload=b"test_payload",
            sig_header="test_signature",
        )

        assert result == expected_event

    def test_raises_error_for_invalid_signature(
        self,
        checkout_service: CheckoutService,
        mock_stripe: MagicMock,
    ) -> None:
        """Test that ValueError is raised for invalid signature."""
        mock_stripe.Webhook.construct_event.side_effect = (
            stripe.error.SignatureVerificationError("Invalid", "sig_header")
        )

        with pytest.raises(ValueError, match="Invalid webhook signature"):
            checkout_service.verify_webhook_signature(
                payload=b"test_payload",
                sig_header="invalid_signature",
            )


class TestHandleCheckoutCompleted:
    """Tests for handle_checkout_completed method."""

    @pytest.mark.asyncio
    async def test_updates_order_on_completion(
        self,
        checkout_service: CheckoutService,
        mock_supabase: MagicMock,
        sample_order: dict,
    ) -> None:
        """Test that order is updated when checkout completes."""
        event = {
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

        completed_order = sample_order.copy()
        completed_order["status"] = "completed"

        mock_response = MagicMock()
        mock_response.data = [completed_order]
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        result = await checkout_service.handle_checkout_completed(event)

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_order_id(
        self,
        checkout_service: CheckoutService,
    ) -> None:
        """Test that empty dict is returned when order_id missing from metadata."""
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "metadata": {},  # No order_id
                }
            },
        }

        result = await checkout_service.handle_checkout_completed(event)

        assert result == {}


class TestHandleCheckoutExpired:
    """Tests for handle_checkout_expired method."""

    @pytest.mark.asyncio
    async def test_cancels_order_on_expiration(
        self,
        checkout_service: CheckoutService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that order is cancelled when checkout expires."""
        event = {
            "type": "checkout.session.expired",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "metadata": {"order_id": "660e8400-e29b-41d4-a716-446655440000"},
                }
            },
        }

        mock_response = MagicMock()
        mock_response.data = [{"id": "order-123", "status": "cancelled"}]
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        # Should not raise
        await checkout_service.handle_checkout_expired(event)

        # Verify update was called with cancelled status
        update_call = mock_supabase.table.return_value.update.call_args
        assert update_call[0][0]["status"] == "cancelled"


class TestGetOrder:
    """Tests for get_order method."""

    @pytest.mark.asyncio
    async def test_returns_order_when_found(
        self,
        checkout_service: CheckoutService,
        mock_supabase: MagicMock,
        sample_order: dict,
    ) -> None:
        """Test that order is returned when found."""
        mock_response = MagicMock()
        mock_response.data = sample_order
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        result = await checkout_service.get_order(
            UUID("660e8400-e29b-41d4-a716-446655440000")
        )

        assert result == sample_order

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(
        self,
        checkout_service: CheckoutService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that None is returned when order not found."""
        mock_response = MagicMock()
        mock_response.data = None
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        result = await checkout_service.get_order(
            UUID("660e8400-e29b-41d4-a716-446655440000")
        )

        assert result is None


class TestTransferOrdersToProfile:
    """Tests for transfer_orders_to_profile method."""

    @pytest.mark.asyncio
    async def test_returns_count_of_transferred_orders(
        self,
        checkout_service: CheckoutService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that count of transferred orders is returned."""
        transferred_orders = [{"id": "order-1"}, {"id": "order-2"}]

        mock_response = MagicMock()
        mock_response.data = transferred_orders
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        result = await checkout_service.transfer_orders_to_profile(
            session_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            profile_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
        )

        assert result == 2

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_orders(
        self,
        checkout_service: CheckoutService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that zero is returned when no orders to transfer."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            mock_response
        )

        result = await checkout_service.transfer_orders_to_profile(
            session_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
            profile_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
        )

        assert result == 0


class TestCanAccessOrder:
    """Tests for can_access_order method."""

    @pytest.mark.asyncio
    async def test_returns_true_for_profile_owner(
        self,
        checkout_service: CheckoutService,
        mock_supabase: MagicMock,
        sample_order: dict,
    ) -> None:
        """Test that True is returned for profile owner."""
        mock_response = MagicMock()
        mock_response.data = sample_order
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        result = await checkout_service.can_access_order(
            order_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            profile_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_for_session_owner(
        self,
        checkout_service: CheckoutService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that True is returned for session owner."""
        order_with_session = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "profile_id": None,
            "session_id": "880e8400-e29b-41d4-a716-446655440000",
            "status": "pending",
        }

        mock_response = MagicMock()
        mock_response.data = order_with_session
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        result = await checkout_service.can_access_order(
            order_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            session_id=UUID("880e8400-e29b-41d4-a716-446655440000"),
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_for_non_owner(
        self,
        checkout_service: CheckoutService,
        mock_supabase: MagicMock,
        sample_order: dict,
    ) -> None:
        """Test that False is returned for non-owner."""
        mock_response = MagicMock()
        mock_response.data = sample_order
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        result = await checkout_service.can_access_order(
            order_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            profile_id=UUID("990e8400-e29b-41d4-a716-446655440000"),  # Different profile
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_order(
        self,
        checkout_service: CheckoutService,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that False is returned for non-existent order."""
        mock_response = MagicMock()
        mock_response.data = None
        mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
            mock_response
        )

        result = await checkout_service.can_access_order(
            order_id=UUID("660e8400-e29b-41d4-a716-446655440000"),
            profile_id=UUID("770e8400-e29b-41d4-a716-446655440000"),
        )

        assert result is False

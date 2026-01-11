"""Checkout and order business logic service."""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import stripe

from src.core.config import get_settings
from src.core.stripe import get_stripe
from src.core.supabase import get_supabase_client
from src.services.robot_catalog_service import RobotCatalogService

logger = logging.getLogger(__name__)


class CheckoutService:
    """Service for Stripe checkout and order management."""

    def __init__(self) -> None:
        """Initialize checkout service with clients."""
        self.client = get_supabase_client()
        self.stripe = get_stripe()
        self.settings = get_settings()
        self.robot_service = RobotCatalogService()

    async def create_checkout_session(
        self,
        product_id: UUID,
        success_url: str,
        cancel_url: str,
        profile_id: UUID | None = None,
        session_id: UUID | None = None,
        customer_email: str | None = None,
    ) -> dict[str, Any]:
        """Create a Stripe Checkout Session and pending order.

        Args:
            product_id: Robot product UUID.
            success_url: URL to redirect after successful checkout.
            cancel_url: URL to redirect if checkout is cancelled.
            profile_id: Optional profile ID for authenticated users.
            session_id: Optional session ID for anonymous users.
            customer_email: Optional pre-fill email.

        Returns:
            dict: Contains checkout_url, order_id, stripe_session_id.

        Raises:
            ValueError: If product not found or inactive, or Stripe not configured.
            Exception: If Stripe API call fails.
        """
        if not self.settings.stripe_secret_key:
            raise ValueError("Stripe is not configured. Please set STRIPE_SECRET_KEY environment variable.")
        
        # Get product with Stripe IDs
        robot = await self.robot_service.get_robot_with_stripe_ids(product_id)
        if not robot:
            raise ValueError("Product not found")

        if not robot.get("active", False):
            raise ValueError("Product is no longer available")

        # Calculate total in cents
        monthly_lease = robot.get("monthly_lease", 0)
        if isinstance(monthly_lease, str):
            monthly_lease = Decimal(monthly_lease)
        total_cents = int(monthly_lease * 100)

        # Create line items for the order
        line_items = [
            {
                "product_id": str(product_id),
                "product_name": robot["name"],
                "quantity": 1,
                "unit_amount_cents": total_cents,
                "stripe_price_id": robot["stripe_lease_price_id"],
            }
        ]

        # Create pending order first
        order_data = {
            "profile_id": str(profile_id) if profile_id else None,
            "session_id": str(session_id) if session_id else None,
            "stripe_checkout_session_id": None,  # Will update after Stripe call
            "status": "pending",
            "line_items": line_items,
            "total_cents": total_cents,
            "currency": "usd",
            "customer_email": customer_email,
            "metadata": {},
        }

        order_response = self.client.table("orders").insert(order_data).execute()
        order = order_response.data[0]
        order_id = order["id"]

        try:
            # Create Stripe Checkout Session
            checkout_params: dict[str, Any] = {
                "mode": "subscription",
                "line_items": [
                    {
                        "price": robot["stripe_lease_price_id"],
                        "quantity": 1,
                    }
                ],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "order_id": str(order_id),
                    "session_id": str(session_id) if session_id else "",
                },
            }

            # For Stripe Accounts V2 in test mode, we need to create a customer first
            # In production mode, Stripe handles customer creation automatically
            if customer_email:
                # Create or find existing customer
                existing_customers = self.stripe.Customer.list(email=customer_email, limit=1)
                if existing_customers.data:
                    checkout_params["customer"] = existing_customers.data[0].id
                else:
                    customer = self.stripe.Customer.create(email=customer_email)
                    checkout_params["customer"] = customer.id
            else:
                # Create anonymous customer for test mode compatibility
                customer = self.stripe.Customer.create()
                checkout_params["customer"] = customer.id

            stripe_session = self.stripe.checkout.Session.create(**checkout_params)

            # Update order with Stripe session ID
            self.client.table("orders").update(
                {"stripe_checkout_session_id": stripe_session.id}
            ).eq("id", order_id).execute()

            return {
                "checkout_url": stripe_session.url,
                "order_id": UUID(order_id),
                "stripe_session_id": stripe_session.id,
            }

        except stripe.error.StripeError as e:
            # Clean up the order if Stripe fails
            logger.error("Stripe error creating checkout session: %s", str(e))
            self.client.table("orders").update(
                {"status": "cancelled"}
            ).eq("id", order_id).execute()
            raise

    async def handle_checkout_completed(self, event: dict[str, Any]) -> dict[str, Any]:
        """Process checkout.session.completed webhook event.

        Args:
            event: Stripe webhook event data.

        Returns:
            dict: Updated order data.
        """
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")

        if not order_id:
            logger.warning("Webhook missing order_id in metadata: %s", session.get("id"))
            return {}

        customer_email = None
        customer_details = session.get("customer_details", {})
        if customer_details:
            customer_email = customer_details.get("email")

        update_data = {
            "status": "completed",
            "stripe_customer_id": session.get("customer"),
            "stripe_subscription_id": session.get("subscription"),
            "customer_email": customer_email,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

        response = (
            self.client.table("orders")
            .update(update_data)
            .eq("id", order_id)
            .execute()
        )

        if response.data:
            logger.info("Order %s marked as completed", order_id)
            return response.data[0]

        logger.warning("Order not found for completion: %s", order_id)
        return {}

    async def handle_checkout_expired(self, event: dict[str, Any]) -> None:
        """Process checkout.session.expired webhook event.

        Args:
            event: Stripe webhook event data.
        """
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")

        if not order_id:
            logger.warning("Webhook missing order_id in metadata: %s", session.get("id"))
            return

        self.client.table("orders").update(
            {"status": "cancelled"}
        ).eq("id", order_id).execute()

        logger.info("Order %s marked as cancelled (expired)", order_id)

    async def get_order(self, order_id: UUID) -> dict[str, Any] | None:
        """Get an order by ID.

        Args:
            order_id: The order's UUID.

        Returns:
            dict | None: The order data or None if not found.
        """
        response = (
            self.client.table("orders")
            .select("*")
            .eq("id", str(order_id))
            .maybe_single()
            .execute()
        )

        return response.data if response and response.data else None

    async def get_orders_for_profile(self, profile_id: UUID) -> list[dict[str, Any]]:
        """Get all orders for a profile.

        Args:
            profile_id: The profile's UUID.

        Returns:
            list[dict]: List of order data.
        """
        response = (
            self.client.table("orders")
            .select("*")
            .eq("profile_id", str(profile_id))
            .order("created_at", desc=True)
            .execute()
        )

        return response.data or []

    async def get_orders_for_session(self, session_id: UUID) -> list[dict[str, Any]]:
        """Get all orders for a session.

        Args:
            session_id: The session's UUID.

        Returns:
            list[dict]: List of order data.
        """
        response = (
            self.client.table("orders")
            .select("*")
            .eq("session_id", str(session_id))
            .order("created_at", desc=True)
            .execute()
        )

        return response.data or []

    async def transfer_orders_to_profile(
        self, session_id: UUID, profile_id: UUID
    ) -> int:
        """Transfer session orders to a profile.

        Called when a session is claimed by an authenticated user.

        Args:
            session_id: The session's UUID.
            profile_id: The profile's UUID to transfer to.

        Returns:
            int: Number of orders transferred.
        """
        response = (
            self.client.table("orders")
            .update({"profile_id": str(profile_id)})
            .eq("session_id", str(session_id))
            .execute()
        )

        return len(response.data) if response.data else 0

    def verify_webhook_signature(
        self, payload: bytes, sig_header: str
    ) -> dict[str, Any]:
        """Verify Stripe webhook signature and return event.

        Args:
            payload: Raw webhook payload bytes.
            sig_header: Stripe-Signature header value.

        Returns:
            dict: Verified Stripe event.

        Raises:
            ValueError: If signature is invalid or Stripe not configured.
        """
        if not self.settings.stripe_webhook_secret:
            raise ValueError("Stripe webhook secret is not configured. Please set STRIPE_WEBHOOK_SECRET environment variable.")
        
        try:
            event = self.stripe.Webhook.construct_event(
                payload, sig_header, self.settings.stripe_webhook_secret
            )
            return event
        except stripe.error.SignatureVerificationError as e:
            logger.warning("Invalid webhook signature: %s", str(e))
            raise ValueError("Invalid webhook signature") from e

    async def can_access_order(
        self,
        order_id: UUID,
        profile_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> bool:
        """Check if a user or session can access an order.

        Args:
            order_id: The order's UUID.
            profile_id: Optional profile ID for authenticated users.
            session_id: Optional session ID for anonymous users.

        Returns:
            bool: True if access is allowed.
        """
        order = await self.get_order(order_id)
        if not order:
            return False

        # Check profile ownership
        if profile_id and order.get("profile_id") == str(profile_id):
            return True

        # Check session ownership
        if session_id and order.get("session_id") == str(session_id):
            return True

        return False

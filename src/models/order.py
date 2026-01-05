"""Order model type definitions for database operations."""

from datetime import datetime
from typing import Literal, TypedDict
from uuid import UUID


# Order status enum values matching database enum
OrderStatus = Literal["pending", "processing", "completed", "cancelled", "refunded"]


class OrderLineItem(TypedDict):
    """Structure for a single line item in an order.

    Stored as part of the line_items JSONB array.
    """

    product_id: str
    product_name: str
    quantity: int
    unit_amount_cents: int
    stripe_price_id: str


class Order(TypedDict):
    """Order table row representation.

    Represents an order stored in the orders table.
    Maps directly to the database schema.
    """

    id: UUID
    profile_id: UUID | None
    session_id: UUID | None
    stripe_checkout_session_id: str
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    status: OrderStatus
    line_items: list[OrderLineItem]
    total_cents: int
    currency: str
    customer_email: str | None
    metadata: dict
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OrderCreate(TypedDict, total=False):
    """Data required to create a new order.

    Used when inserting a new order during checkout session creation.
    """

    profile_id: UUID | None
    session_id: UUID | None
    stripe_checkout_session_id: str
    status: OrderStatus
    line_items: list[OrderLineItem]
    total_cents: int
    currency: str
    customer_email: str | None
    metadata: dict


class OrderUpdate(TypedDict, total=False):
    """Data that can be updated on an order.

    Used when updating order status after webhooks.
    """

    status: OrderStatus
    stripe_customer_id: str
    stripe_subscription_id: str
    customer_email: str
    completed_at: datetime

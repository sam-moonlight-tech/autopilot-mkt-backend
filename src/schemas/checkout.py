"""Checkout and order Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


# Order status literal type for validation
OrderStatus = Literal["pending", "processing", "completed", "cancelled", "refunded"]


class OrderLineItemSchema(BaseModel):
    """Schema for a single line item in an order."""

    model_config = ConfigDict(from_attributes=True)

    product_id: str = Field(description="Product UUID")
    product_name: str = Field(description="Product name")
    quantity: int = Field(ge=1, description="Quantity ordered")
    unit_amount_cents: int = Field(ge=0, description="Unit price in cents")
    stripe_price_id: str = Field(description="Stripe Price ID")


class CheckoutSessionCreate(BaseModel):
    """Schema for creating a checkout session via POST /checkout/session."""

    model_config = ConfigDict(from_attributes=True)

    product_id: UUID = Field(description="Robot product UUID to checkout")
    success_url: HttpUrl = Field(description="URL to redirect after successful checkout")
    cancel_url: HttpUrl = Field(description="URL to redirect if checkout is cancelled")
    customer_email: str | None = Field(default=None, description="Pre-fill customer email")


class CheckoutSessionResponse(BaseModel):
    """Schema for checkout session creation response."""

    model_config = ConfigDict(from_attributes=True)

    checkout_url: str = Field(description="Stripe Checkout URL to redirect to")
    order_id: UUID = Field(description="Created order UUID")
    stripe_session_id: str = Field(description="Stripe Checkout Session ID")


class OrderResponse(BaseModel):
    """Schema for order API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Order unique identifier")
    profile_id: UUID | None = Field(default=None, description="Associated profile ID")
    session_id: UUID | None = Field(default=None, description="Associated session ID")
    status: str = Field(description="Order status")
    line_items: list[OrderLineItemSchema] = Field(description="Order line items")
    total_cents: int = Field(description="Total amount in cents")
    currency: str = Field(default="usd", description="Currency code")
    customer_email: str | None = Field(default=None, description="Customer email")
    stripe_subscription_id: str | None = Field(default=None, description="Stripe subscription ID")
    completed_at: datetime | None = Field(default=None, description="Completion timestamp")
    created_at: datetime = Field(description="Creation timestamp")


class OrderListResponse(BaseModel):
    """Schema for order list API responses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[OrderResponse] = Field(description="List of orders")

"""Robot model type definitions for database operations."""

from datetime import datetime
from decimal import Decimal
from typing import TypedDict
from uuid import UUID


class Robot(TypedDict):
    """Robot catalog table row representation.

    Represents a robot product stored in the robot_catalog table.
    Maps directly to the database schema.
    """

    id: UUID
    sku: str | None
    name: str
    manufacturer: str | None
    category: str
    best_for: str | None
    modes: list[str]
    surfaces: list[str]
    monthly_lease: Decimal
    purchase_price: Decimal
    time_efficiency: Decimal
    key_reasons: list[str]
    specs: list[str]
    image_url: str | None
    stripe_product_id: str
    stripe_lease_price_id: str
    embedding_id: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


class RobotWithStripeIds(TypedDict):
    """Robot with Stripe IDs for checkout operations.

    A subset of Robot fields needed for creating checkout sessions.
    """

    id: UUID
    name: str
    monthly_lease: Decimal
    stripe_product_id: str
    stripe_lease_price_id: str
    active: bool

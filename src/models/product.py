"""Product model type definitions for database operations."""

from datetime import datetime
from enum import Enum
from typing import Any, TypedDict
from uuid import UUID


class ProductCategory(str, Enum):
    """Product category values."""

    COLLABORATIVE_ROBOT = "collaborative_robot"
    INDUSTRIAL_ROBOT = "industrial_robot"
    AMR = "amr"
    INSPECTION_ROBOT = "inspection_robot"
    VISION_SYSTEM = "vision_system"
    END_EFFECTOR = "end_effector"
    SENSOR = "sensor"
    CONTROLLER = "controller"
    OTHER = "other"


class Product(TypedDict):
    """Product table row representation.

    Represents a product stored in the products table.
    """

    id: UUID
    name: str
    description: str | None
    category: str
    specs: dict[str, Any]
    pricing: dict[str, Any]
    image_url: str | None
    manufacturer: str | None
    model_number: str | None
    embedding_id: str | None
    created_at: datetime
    updated_at: datetime


class ProductCreate(TypedDict, total=False):
    """Data required to create a new product."""

    name: str
    description: str | None
    category: str
    specs: dict[str, Any]
    pricing: dict[str, Any]
    image_url: str | None
    manufacturer: str | None
    model_number: str | None


class ProductUpdate(TypedDict, total=False):
    """Data that can be updated on a product."""

    name: str
    description: str | None
    category: str
    specs: dict[str, Any]
    pricing: dict[str, Any]
    image_url: str | None
    manufacturer: str | None
    model_number: str | None

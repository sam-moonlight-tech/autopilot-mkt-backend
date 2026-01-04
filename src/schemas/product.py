"""Product Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    """Base product fields shared across schemas."""

    name: str = Field(..., min_length=1, max_length=255, description="Product name")
    description: str | None = Field(default=None, description="Product description")
    category: str = Field(..., description="Product category")
    specs: dict[str, Any] = Field(default_factory=dict, description="Technical specifications")
    pricing: dict[str, Any] = Field(default_factory=dict, description="Pricing information")
    image_url: str | None = Field(default=None, description="Product image URL")
    manufacturer: str | None = Field(default=None, max_length=255, description="Manufacturer name")
    model_number: str | None = Field(default=None, max_length=100, description="Model number")


class ProductCreate(ProductBase):
    """Schema for creating a new product."""

    model_config = ConfigDict(from_attributes=True)


class ProductResponse(ProductBase):
    """Schema for product API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Product unique identifier")
    embedding_id: str | None = Field(default=None, description="Pinecone embedding ID")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class ProductSearchRequest(BaseModel):
    """Schema for semantic product search request."""

    model_config = ConfigDict(from_attributes=True)

    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    category: str | None = Field(default=None, description="Filter by category")
    top_k: int = Field(default=10, ge=1, le=50, description="Number of results to return")


class ProductSearchResult(BaseModel):
    """Schema for a single search result."""

    model_config = ConfigDict(from_attributes=True)

    product: ProductResponse = Field(description="The matched product")
    score: float = Field(description="Similarity score (0-1)")


class ProductSearchResponse(BaseModel):
    """Schema for product search response."""

    model_config = ConfigDict(from_attributes=True)

    results: list[ProductSearchResult] = Field(description="Search results")
    query: str = Field(description="Original query")
    total: int = Field(description="Number of results returned")


class ProductListResponse(BaseModel):
    """Schema for paginated product list response."""

    model_config = ConfigDict(from_attributes=True)

    products: list[ProductResponse] = Field(description="List of products")
    next_cursor: str | None = Field(default=None, description="Cursor for next page")
    has_more: bool = Field(default=False, description="Whether more results exist")

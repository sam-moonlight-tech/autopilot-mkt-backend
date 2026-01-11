"""Robot Pydantic schemas for API request/response models."""

from decimal import Decimal
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


class RobotSortField(str, Enum):
    """Available sort options for robots."""

    FEATURED = "featured"
    PRICE_LOW = "price_low"
    PRICE_HIGH = "price_high"
    NAME_AZ = "name_az"
    NAME_ZA = "name_za"
    EFFICIENCY = "efficiency"


class RobotFilters(BaseModel):
    """Query parameters for filtering robots."""

    model_config = ConfigDict(from_attributes=True)

    # Sorting
    sort: RobotSortField = Field(
        default=RobotSortField.FEATURED,
        description="Sort order for results"
    )

    # Price filter
    price_min: float | None = Field(
        default=None,
        ge=0,
        description="Minimum monthly lease price"
    )
    price_max: float | None = Field(
        default=None,
        ge=0,
        description="Maximum monthly lease price"
    )

    # Size/coverage filter
    size: str | None = Field(
        default=None,
        description="Size category: small, medium, large, enterprise"
    )

    # Cleaning methods filter (multiple allowed)
    methods: list[str] | None = Field(
        default=None,
        description="Filter by cleaning modes (e.g., vacuum, mop, scrub)"
    )

    # Surfaces filter (multiple allowed)
    surfaces: list[str] | None = Field(
        default=None,
        description="Filter by supported surfaces"
    )

    # Category filter
    category: str | None = Field(
        default=None,
        description="Filter by robot category"
    )

    # Shipping/availability filter
    ship: str | None = Field(
        default=None,
        description="Shipping option: in_stock, ships_soon, pre_order"
    )

    # Search query
    search: str | None = Field(
        default=None,
        description="Text search in name, category, best_for"
    )


class RobotResponse(BaseModel):
    """Schema for robot API responses.

    Includes both snake_case database fields and camelCase computed
    fields for frontend compatibility with RobotOption interface.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Robot unique identifier")
    name: str = Field(description="Robot name")
    category: str = Field(description="Robot category")
    best_for: str | None = Field(default=None, description="Best use case")
    modes: list[str] = Field(default_factory=list, description="Cleaning modes")
    surfaces: list[str] = Field(default_factory=list, description="Supported surfaces")
    monthly_lease: Decimal = Field(description="Monthly lease price in dollars")
    purchase_price: Decimal = Field(description="One-time purchase price in dollars")
    time_efficiency: Decimal = Field(description="Time efficiency factor (0-1)")
    key_reasons: list[str] = Field(default_factory=list, description="Key selling points")
    specs: list[str] = Field(default_factory=list, description="Technical specifications")
    image_url: str | None = Field(default=None, description="Product image URL")
    active: bool = Field(default=True, description="Whether product is active")

    # Computed fields for frontend camelCase compatibility
    @computed_field
    @property
    def monthlyLease(self) -> float:
        """Monthly lease price as float for frontend."""
        return float(self.monthly_lease)

    @computed_field
    @property
    def purchasePrice(self) -> float:
        """Purchase price as float for frontend."""
        return float(self.purchase_price)

    @computed_field
    @property
    def timeEfficiency(self) -> float:
        """Time efficiency as float for frontend."""
        return float(self.time_efficiency)

    @computed_field
    @property
    def bestFor(self) -> str | None:
        """Best use case in camelCase for frontend."""
        return self.best_for

    @computed_field
    @property
    def keyReasons(self) -> list[str]:
        """Key reasons in camelCase for frontend."""
        return self.key_reasons


class FilterOption(BaseModel):
    """A single filter option for dropdowns."""

    value: str = Field(description="Filter value to send to API")
    label: str = Field(description="Display label for UI")
    count: int = Field(default=0, description="Number of robots matching this filter")


class FilterMetadata(BaseModel):
    """Available filter options based on current robot catalog."""

    model_config = ConfigDict(from_attributes=True)

    sort_options: list[FilterOption] = Field(
        default_factory=list,
        description="Available sort options"
    )
    price_ranges: list[FilterOption] = Field(
        default_factory=list,
        description="Price range options"
    )
    sizes: list[FilterOption] = Field(
        default_factory=list,
        description="Size category options"
    )
    methods: list[FilterOption] = Field(
        default_factory=list,
        description="Cleaning method options"
    )
    surfaces: list[FilterOption] = Field(
        default_factory=list,
        description="Surface type options"
    )
    categories: list[FilterOption] = Field(
        default_factory=list,
        description="Robot category options"
    )
    ship_options: list[FilterOption] = Field(
        default_factory=list,
        description="Shipping/availability options"
    )


class RobotListResponse(BaseModel):
    """Schema for robot list API responses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RobotResponse] = Field(description="List of robots")
    total: int = Field(default=0, description="Total number of matching robots")
    filters_applied: RobotFilters | None = Field(
        default=None,
        description="Filters that were applied"
    )

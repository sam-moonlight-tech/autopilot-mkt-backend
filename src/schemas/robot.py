"""Robot Pydantic schemas for API request/response models."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


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


class RobotListResponse(BaseModel):
    """Schema for robot list API responses."""

    model_config = ConfigDict(from_attributes=True)

    items: list[RobotResponse] = Field(description="List of robots")

"""Discovery profile Pydantic schemas for API request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.session import (
    DiscoveryAnswerSchema,
    GreenlightSchema,
    ROIInputsSchema,
    SessionPhase,
    Timeframe,
)


class DiscoveryProfileUpdate(BaseModel):
    """Schema for updating a discovery profile via PUT /discovery.

    All fields are optional for partial updates.
    """

    model_config = ConfigDict(from_attributes=True)

    current_question_index: int | None = Field(default=None, ge=0, description="Current question index in discovery flow")
    phase: SessionPhase | None = Field(default=None, description="Current discovery phase")
    answers: dict[str, DiscoveryAnswerSchema] | None = Field(default=None, description="Discovery answers keyed by question key")
    roi_inputs: ROIInputsSchema | None = Field(default=None, description="ROI calculation inputs")
    selected_product_ids: list[UUID] | None = Field(default=None, description="Selected product/robot IDs")
    timeframe: Timeframe | None = Field(default=None, description="ROI calculation timeframe")
    greenlight: GreenlightSchema | None = Field(default=None, description="Greenlight phase data")


class DiscoveryProfileResponse(BaseModel):
    """Schema for discovery profile API responses via GET /discovery."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Discovery profile unique identifier")
    profile_id: UUID = Field(description="Associated user profile ID")
    current_question_index: int = Field(description="Current question index in discovery flow")
    phase: str = Field(description="Current discovery phase")
    answers: dict[str, DiscoveryAnswerSchema] = Field(default_factory=dict, description="Discovery answers")
    roi_inputs: ROIInputsSchema | None = Field(default=None, description="ROI calculation inputs")
    selected_product_ids: list[UUID] = Field(default_factory=list, description="Selected product/robot IDs")
    timeframe: str | None = Field(default=None, description="ROI calculation timeframe")
    greenlight: GreenlightSchema | None = Field(default=None, description="Greenlight phase data")
    created_at: datetime = Field(description="Profile creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")

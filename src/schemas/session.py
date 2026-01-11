"""Session Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Phase literal type for validation
SessionPhase = Literal["discovery", "roi", "greenlight"]

# Discovery answer group values
DiscoveryAnswerGroup = Literal["Company", "Facility", "Operations", "Economics", "Context"]

# Timeframe options
Timeframe = Literal["monthly", "yearly"]


class DiscoveryAnswerSchema(BaseModel):
    """Schema for a single discovery answer.

    Matches the frontend DiscoveryAnswer interface.
    """

    model_config = ConfigDict(from_attributes=True)

    questionId: int = Field(description="Question ID from the discovery questions")
    key: str = Field(description="Answer key identifier")
    label: str = Field(description="Human-readable label for the answer")
    value: str = Field(description="The actual answer value")
    group: DiscoveryAnswerGroup = Field(description="Question group category")


class ROIInputsSchema(BaseModel):
    """Schema for ROI calculation inputs.

    Matches the frontend ROIInputs interface.
    """

    model_config = ConfigDict(from_attributes=True)

    laborRate: float = Field(ge=0, description="Hourly labor rate in dollars")
    utilization: float = Field(ge=0, le=1, description="Utilization factor (0-1)")
    maintenanceFactor: float = Field(ge=0, description="Maintenance cost factor")
    manualMonthlySpend: float = Field(ge=0, description="Current monthly spend on manual cleaning")
    manualMonthlyHours: float = Field(ge=0, description="Current monthly hours spent on manual cleaning")


# Payment method options
PaymentMethod = Literal["card", "paypal", "bank"]


class TeamMemberSchema(BaseModel):
    """Schema for a team member in greenlight phase."""

    model_config = ConfigDict(from_attributes=True)

    email: str = Field(description="Team member email address")
    name: str = Field(description="Team member display name")
    role: str = Field(description="Team member role/title")


class GreenlightSchema(BaseModel):
    """Schema for greenlight phase data.

    Matches the frontend greenlight interface.
    """

    model_config = ConfigDict(from_attributes=True)

    target_start_date: str | None = Field(default=None, description="Target deployment start date (ISO format)")
    team_members: list[TeamMemberSchema] = Field(default_factory=list, description="Team members for deployment")
    payment_method: PaymentMethod | None = Field(default=None, description="Selected payment method")


class SessionUpdate(BaseModel):
    """Schema for updating a session via PUT /sessions/me.

    All fields are optional for partial updates.
    """

    model_config = ConfigDict(from_attributes=True)

    current_question_index: int | None = Field(default=None, ge=0, description="Current question index in discovery flow")
    phase: SessionPhase | None = Field(default=None, description="Current session phase")
    answers: dict[str, DiscoveryAnswerSchema] | None = Field(default=None, description="Discovery answers keyed by question key")
    roi_inputs: ROIInputsSchema | None = Field(default=None, description="ROI calculation inputs")
    selected_product_ids: list[UUID] | None = Field(default=None, description="Selected product/robot IDs")
    timeframe: Timeframe | None = Field(default=None, description="ROI calculation timeframe")
    greenlight: GreenlightSchema | None = Field(default=None, description="Greenlight phase data")


class SessionResponse(BaseModel):
    """Schema for session API responses via GET /sessions/me."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Session unique identifier")
    current_question_index: int = Field(description="Current question index in discovery flow")
    phase: str = Field(description="Current session phase")
    answers: dict[str, DiscoveryAnswerSchema] = Field(default_factory=dict, description="Discovery answers")
    roi_inputs: ROIInputsSchema | None = Field(default=None, description="ROI calculation inputs")
    selected_product_ids: list[UUID] = Field(default_factory=list, description="Selected product/robot IDs")
    timeframe: str | None = Field(default=None, description="ROI calculation timeframe")
    greenlight: GreenlightSchema | None = Field(default=None, description="Greenlight phase data")
    conversation_id: UUID | None = Field(default=None, description="Associated conversation ID")
    expires_at: datetime = Field(description="Session expiration timestamp")
    created_at: datetime = Field(description="Session creation timestamp")


class SessionClaimResponse(BaseModel):
    """Schema for session claim response via POST /sessions/claim.

    Returns the discovery profile created from the claimed session.
    """

    model_config = ConfigDict(from_attributes=True)

    message: str = Field(default="Session claimed successfully", description="Status message")
    discovery_profile_id: UUID = Field(description="Created discovery profile ID")
    conversation_transferred: bool = Field(default=False, description="Whether a conversation was transferred")
    orders_transferred: int = Field(default=0, description="Number of orders transferred to the user's profile")

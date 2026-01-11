"""ROI and Recommendation Pydantic schemas for API request/response models."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.models.session import DiscoveryAnswer


class ROIInputs(BaseModel):
    """ROI calculation inputs from discovery answers."""

    model_config = ConfigDict(from_attributes=True)

    labor_rate: float = Field(
        default=25.0,
        ge=0,
        description="Hourly labor rate in dollars"
    )
    utilization: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="Utilization factor (0-1)"
    )
    maintenance_factor: float = Field(
        default=0.05,
        ge=0,
        le=1,
        description="Maintenance cost factor (0-1)"
    )
    manual_monthly_spend: float = Field(
        ge=0,
        description="Current monthly cleaning spend in dollars"
    )
    manual_monthly_hours: float = Field(
        ge=0,
        description="Current monthly hours spent on cleaning"
    )


class ROICalculationRequest(BaseModel):
    """Request schema for ROI calculation."""

    model_config = ConfigDict(from_attributes=True)

    robot_id: UUID = Field(description="Robot to calculate ROI for")
    answers: dict[str, DiscoveryAnswer] = Field(
        description="Discovery answers for context"
    )
    roi_inputs: ROIInputs | None = Field(
        default=None,
        description="Optional ROI inputs (will be derived from answers if not provided)"
    )
    timeframe: Literal["monthly", "yearly"] = Field(
        default="monthly",
        description="Timeframe for ROI projections"
    )


class ROICalculation(BaseModel):
    """ROI calculation result for a specific robot."""

    model_config = ConfigDict(from_attributes=True)

    # Core metrics
    current_monthly_cost: float = Field(
        description="Current monthly cleaning cost"
    )
    robot_monthly_cost: float = Field(
        description="Monthly cost of robot (lease)"
    )
    estimated_monthly_savings: float = Field(
        description="Projected monthly savings (can be negative if robot costs more than savings)"
    )
    estimated_yearly_savings: float = Field(
        description="Projected yearly savings (can be negative if robot costs more than savings)"
    )

    # Time metrics
    current_monthly_hours: float = Field(
        description="Current monthly hours spent on cleaning"
    )
    hours_saved_monthly: float = Field(
        description="Monthly hours saved with automation"
    )

    # ROI metrics
    roi_percent: float = Field(
        description="Return on investment percentage (can be negative if robot costs more than savings)"
    )
    payback_months: float | None = Field(
        default=None,
        description="Months until robot pays for itself (null if no savings)"
    )

    # Metadata
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level in the calculation"
    )
    algorithm_version: str = Field(
        default="1.0.0",
        description="Version of the ROI calculation algorithm"
    )
    factors_considered: list[str] = Field(
        default_factory=list,
        description="Factors included in the calculation"
    )


class ROICalculationResponse(BaseModel):
    """Response schema for ROI calculation endpoint."""

    model_config = ConfigDict(from_attributes=True)

    robot_id: UUID = Field(description="Robot ID this calculation is for")
    robot_name: str = Field(description="Robot name")
    calculation: ROICalculation = Field(description="ROI calculation result")
    inputs_used: ROIInputs = Field(description="Inputs used for calculation")
    calculated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the calculation was performed"
    )


class RecommendationReason(BaseModel):
    """A reason for recommending a robot."""

    model_config = ConfigDict(from_attributes=True)

    factor: str = Field(description="What factor influenced this recommendation")
    explanation: str = Field(description="Why this factor matters for the user")
    score_impact: float = Field(description="How much this affected the score (0-100)")


class RobotRecommendation(BaseModel):
    """A robot recommendation with scoring and reasoning."""

    model_config = ConfigDict(from_attributes=True)

    robot_id: UUID = Field(description="Robot ID")
    robot_name: str = Field(description="Robot name")
    vendor: str = Field(description="Robot vendor/manufacturer")
    category: str = Field(description="Robot category")
    monthly_lease: float = Field(description="Monthly lease price")
    time_efficiency: float = Field(description="Time efficiency factor")
    image_urls: list[str] = Field(default_factory=list, description="Product image URLs")

    # Recommendation metadata
    rank: int = Field(description="Recommendation rank (1=best)")
    label: Literal["RECOMMENDED", "BEST VALUE", "UPGRADE", "ALTERNATIVE"] = Field(
        description="Display label for this recommendation"
    )
    match_score: float = Field(
        ge=0,
        le=100,
        description="How well this robot matches the user's needs (0-100)"
    )

    # Reasoning
    reasons: list[RecommendationReason] = Field(
        default_factory=list,
        description="Reasons for this recommendation"
    )
    summary: str = Field(
        description="One-line summary of why this robot is recommended"
    )

    # Projected ROI
    projected_roi: ROICalculation = Field(
        description="Projected ROI for this robot"
    )

    # Full robot data for display
    modes: list[str] = Field(default_factory=list, description="Cleaning modes")
    surfaces: list[str] = Field(default_factory=list, description="Supported surfaces")
    key_reasons: list[str] = Field(default_factory=list, description="Key selling points")
    specs: list[str] = Field(default_factory=list, description="Technical specifications")


class RecommendationsRequest(BaseModel):
    """Request schema for robot recommendations."""

    model_config = ConfigDict(from_attributes=True)

    answers: dict[str, DiscoveryAnswer] = Field(
        description="Discovery answers for matching"
    )
    roi_inputs: ROIInputs | None = Field(
        default=None,
        description="Optional ROI inputs (will be derived from answers if not provided)"
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=50,
        description="Number of recommendations to return"
    )
    timeframe: Literal["monthly", "yearly"] = Field(
        default="monthly",
        description="Timeframe for ROI projections"
    )


class OtherRobotOption(BaseModel):
    """A robot option that wasn't in the top recommendations."""

    model_config = ConfigDict(from_attributes=True)

    robot_id: UUID = Field(description="Robot ID")
    robot_name: str = Field(description="Robot name")
    vendor: str = Field(description="Robot vendor/manufacturer")
    category: str = Field(description="Robot category")
    monthly_lease: float = Field(description="Monthly lease price")
    time_efficiency: float = Field(description="Time efficiency factor")
    image_urls: list[str] = Field(default_factory=list, description="Product image URLs")
    match_score: float = Field(ge=0, le=100, description="Match score (0-100)")
    modes: list[str] = Field(default_factory=list, description="Cleaning modes")
    surfaces: list[str] = Field(default_factory=list, description="Supported surfaces")
    key_reasons: list[str] = Field(default_factory=list, description="Key selling points")
    specs: list[str] = Field(default_factory=list, description="Technical specifications")


class RecommendationsResponse(BaseModel):
    """Response schema for robot recommendations endpoint."""

    model_config = ConfigDict(from_attributes=True)

    recommendations: list[RobotRecommendation] = Field(
        description="Ranked list of top robot recommendations"
    )
    other_options: list[OtherRobotOption] = Field(
        default_factory=list,
        description="Other available robots not in top recommendations"
    )
    total_robots_evaluated: int = Field(
        description="Total number of robots considered"
    )
    algorithm_version: str = Field(
        default="1.0.0",
        description="Version of the recommendation algorithm"
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When recommendations were generated"
    )


class GreenlightValidationRequest(BaseModel):
    """Request schema for greenlight phase validation."""

    model_config = ConfigDict(from_attributes=True)

    selected_robot_id: UUID = Field(description="Selected robot ID")
    target_start_date: str | None = Field(
        default=None,
        description="Target deployment start date (ISO format)"
    )
    team_members: list[dict] = Field(
        default_factory=list,
        description="Team members to notify"
    )
    payment_method: Literal["card", "paypal", "bank"] | None = Field(
        default=None,
        description="Selected payment method"
    )


class GreenlightValidationResponse(BaseModel):
    """Response schema for greenlight validation."""

    model_config = ConfigDict(from_attributes=True)

    valid: bool = Field(description="Whether greenlight data is valid")
    errors: list[str] = Field(
        default_factory=list,
        description="Validation errors if any"
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings that don't block proceeding"
    )
    robot_available: bool = Field(
        default=True,
        description="Whether the selected robot is available"
    )
    estimated_delivery: str | None = Field(
        default=None,
        description="Estimated delivery date"
    )


class GreenlightConfirmRequest(BaseModel):
    """Request schema for greenlight confirmation (creates order intent)."""

    model_config = ConfigDict(from_attributes=True)

    selected_robot_id: UUID = Field(description="Selected robot ID")
    target_start_date: str | None = Field(
        default=None,
        description="Target deployment start date"
    )
    team_members: list[dict] = Field(
        default_factory=list,
        description="Team members to notify"
    )
    payment_method: Literal["card", "paypal", "bank"] = Field(
        description="Selected payment method"
    )
    customer_email: str = Field(description="Customer email for order")


class GreenlightConfirmResponse(BaseModel):
    """Response schema for greenlight confirmation."""

    model_config = ConfigDict(from_attributes=True)

    success: bool = Field(description="Whether confirmation succeeded")
    order_intent_id: UUID | None = Field(
        default=None,
        description="Created order intent ID"
    )
    message: str = Field(description="Status message")
    next_step: Literal["checkout", "contact_sales", "schedule_demo"] = Field(
        description="What the user should do next"
    )
    checkout_url: str | None = Field(
        default=None,
        description="URL to proceed to checkout (if applicable)"
    )

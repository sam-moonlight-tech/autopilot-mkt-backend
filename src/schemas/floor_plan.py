"""Floor plan analysis Pydantic schemas for API request/response models."""

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# === Enums ===


class FloorPlanStatus(str, Enum):
    """Status of floor plan analysis."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ZoneType(str, Enum):
    """Types of zones in a facility."""

    COURT = "court"
    CIRCULATION = "circulation"
    AUXILIARY = "auxiliary"
    EXCLUDED = "excluded"


class SurfaceType(str, Enum):
    """Types of floor surfaces."""

    SPORT_COURT_ACRYLIC = "sport_court_acrylic"
    RUBBER_TILE = "rubber_tile"
    MODULAR = "modular"
    CONCRETE = "concrete"
    OTHER = "other"


class CleaningMode(str, Enum):
    """Robot cleaning modes."""

    DRY_VACUUM = "dry_vacuum"
    DRY_SWEEP = "dry_sweep"
    WET_SCRUB = "wet_scrub"
    WET_VACUUM = "wet_vacuum"


class ObstructionType(str, Enum):
    """Types of obstructions in a facility."""

    NET = "net"
    BENCH = "bench"
    POST = "post"
    EQUIPMENT = "equipment"
    OTHER = "other"


class ObstructionHandling(str, Enum):
    """How robots handle obstructions."""

    VIRTUAL_BOUNDARY = "virtual_boundary"
    NO_GO_ZONE = "no_go_zone"
    NAVIGATE_AROUND = "navigate_around"


class ExclusionReason(str, Enum):
    """Reasons for excluding areas from robot cleaning."""

    MANUAL_ONLY = "manual_only"
    ACCESS_RESTRICTED = "access_restricted"
    HAZARDOUS = "hazardous"


# === Extracted Feature Schemas ===


class DimensionsSchema(BaseModel):
    """Dimensions in feet."""

    length_ft: float = Field(ge=0, description="Length in feet")
    width_ft: float = Field(ge=0, description="Width in feet")


class FacilityDimensionsSchema(BaseModel):
    """Overall facility dimensions."""

    length_ft: float = Field(ge=0, description="Facility length in feet")
    width_ft: float = Field(ge=0, description="Facility width in feet")
    total_sqft: float = Field(ge=0, description="Total square footage")
    confidence: float = Field(ge=0, le=1, description="Extraction confidence score")


class CourtSchema(BaseModel):
    """Individual court data."""

    label: str = Field(description="Court label (e.g., 'Court 1')")
    dimensions: DimensionsSchema | None = Field(default=None, description="Court dimensions")
    sqft: float = Field(ge=0, description="Court square footage")
    surface_type: SurfaceType = Field(default=SurfaceType.SPORT_COURT_ACRYLIC, description="Surface material")
    max_occupancy: int | None = Field(default=None, description="Maximum occupancy if labeled")
    has_net: bool = Field(default=True, description="Whether court has a net")
    confidence: float = Field(ge=0, le=1, description="Extraction confidence score")


class BufferZoneSchema(BaseModel):
    """Buffer zone between courts."""

    between_courts: list[str] = Field(description="Courts this buffer is between")
    width_ft: float = Field(ge=0, description="Buffer width in feet")
    length_ft: float = Field(ge=0, description="Buffer length in feet")
    sqft: float = Field(ge=0, description="Buffer square footage")
    confidence: float = Field(ge=0, le=1, description="Extraction confidence score")


class CirculationAreaSchema(BaseModel):
    """Circulation/walkway area."""

    label: str = Field(description="Area label (e.g., 'Main Walkway')")
    sqft: float = Field(ge=0, description="Area square footage")
    surface_type: SurfaceType = Field(default=SurfaceType.RUBBER_TILE, description="Surface material")
    is_hex_textured: bool = Field(default=False, description="Whether surface has hex texture pattern")
    confidence: float = Field(ge=0, le=1, description="Extraction confidence score")


class AuxiliaryAreaSchema(BaseModel):
    """Auxiliary area (pro shop, office, etc.)."""

    label: str = Field(description="Area label (e.g., 'Pro Shop')")
    sqft: float = Field(ge=0, description="Area square footage")
    surface_type: SurfaceType = Field(default=SurfaceType.OTHER, description="Surface material")
    cleanable_by_robot: bool = Field(default=True, description="Whether robots can clean this area")
    confidence: float = Field(ge=0, le=1, description="Extraction confidence score")


class ExcludedAreaSchema(BaseModel):
    """Area excluded from robot cleaning."""

    label: str = Field(description="Area label (e.g., 'Restrooms')")
    sqft: float = Field(ge=0, description="Area square footage")
    reason: ExclusionReason = Field(description="Reason for exclusion")
    confidence: float = Field(ge=0, le=1, description="Extraction confidence score")


class ObstructionSchema(BaseModel):
    """Obstruction that affects robot navigation."""

    type: ObstructionType = Field(description="Type of obstruction")
    location: str = Field(description="Location description (e.g., 'Court 1')")
    handling: ObstructionHandling = Field(description="How robot handles this obstruction")


class FeatureSummarySchema(BaseModel):
    """Summary of extracted features."""

    total_court_sqft: float = Field(ge=0, description="Total court square footage")
    total_circulation_sqft: float = Field(ge=0, description="Total circulation/buffer square footage")
    total_auxiliary_sqft: float = Field(ge=0, description="Total auxiliary area square footage")
    total_excluded_sqft: float = Field(ge=0, description="Total excluded area square footage")
    total_cleanable_sqft: float = Field(ge=0, description="Total cleanable square footage")
    court_count: int = Field(ge=0, description="Number of courts detected")


class ExtractedFeaturesSchema(BaseModel):
    """All features extracted from floor plan."""

    facility_dimensions: FacilityDimensionsSchema | None = Field(
        default=None, description="Overall facility dimensions"
    )
    courts: list[CourtSchema] = Field(default_factory=list, description="Detected courts")
    buffer_zones: list[BufferZoneSchema] = Field(default_factory=list, description="Buffer zones between courts")
    circulation_areas: list[CirculationAreaSchema] = Field(
        default_factory=list, description="Circulation/walkway areas"
    )
    auxiliary_areas: list[AuxiliaryAreaSchema] = Field(default_factory=list, description="Auxiliary areas")
    excluded_areas: list[ExcludedAreaSchema] = Field(
        default_factory=list, description="Areas excluded from robot cleaning"
    )
    obstructions: list[ObstructionSchema] = Field(default_factory=list, description="Obstructions affecting navigation")
    summary: FeatureSummarySchema = Field(description="Summary of all extracted features")
    extraction_notes: str | None = Field(default=None, description="Notes about assumptions or unclear elements")


# === Cost Estimate Schemas ===


class ZoneCostBreakdownSchema(BaseModel):
    """Cost breakdown for a single zone."""

    zone_type: ZoneType = Field(description="Type of zone")
    zone_label: str = Field(description="Label/name of the zone")
    sqft: float = Field(ge=0, description="Zone square footage")
    cleaning_mode: CleaningMode = Field(description="Cleaning mode used")
    frequency_per_month: int = Field(ge=0, description="Cleaning frequency per month")
    cost_per_cleaning: float = Field(ge=0, description="Cost per cleaning session")
    monthly_cost: float = Field(ge=0, description="Total monthly cost for this zone")


class ModeCostBreakdownSchema(BaseModel):
    """Cost breakdown by cleaning mode."""

    mode: CleaningMode = Field(description="Cleaning mode")
    total_sqft: float = Field(ge=0, description="Total square footage for this mode")
    rate_per_sqft: float = Field(ge=0, description="Rate per square foot")
    cleanings_per_month: int = Field(ge=0, description="Number of cleanings per month")
    monthly_cost: float = Field(ge=0, description="Total monthly cost for this mode")


class CostEstimateSchema(BaseModel):
    """Complete cost estimate."""

    total_monthly_cost: float = Field(ge=0, description="Total monthly cleaning cost")
    total_daily_cost: float = Field(ge=0, description="Average daily cleaning cost")
    breakdown_by_zone: list[ZoneCostBreakdownSchema] = Field(
        default_factory=list, description="Cost breakdown by zone"
    )
    breakdown_by_mode: list[ModeCostBreakdownSchema] = Field(
        default_factory=list, description="Cost breakdown by cleaning mode"
    )
    estimated_daily_cleaning_hours: float | None = Field(default=None, description="Estimated daily cleaning hours")
    estimated_robot_count: int | None = Field(default=None, description="Estimated number of robots needed")
    rate_card_version: str = Field(default="1.0.0", description="Version of rate card used")


# === API Request/Response Schemas ===


class FloorPlanUploadResponse(BaseModel):
    """Response after uploading a floor plan."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Floor plan analysis ID")
    status: FloorPlanStatus = Field(description="Analysis status")
    file_name: str = Field(description="Uploaded file name")
    created_at: datetime = Field(description="Upload timestamp")
    message: str = Field(
        default="Floor plan uploaded successfully. Analysis in progress.",
        description="Status message",
    )


class FloorPlanAnalysisResponse(BaseModel):
    """Response with floor plan analysis results."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Floor plan analysis ID")
    status: FloorPlanStatus = Field(description="Analysis status")
    file_name: str = Field(description="Uploaded file name")

    # Extracted features (None if not yet analyzed)
    extracted_features: ExtractedFeaturesSchema | None = Field(
        default=None, description="GPT-4o extracted features"
    )
    extraction_confidence: Literal["high", "medium", "low"] | None = Field(
        default=None, description="Overall extraction confidence"
    )

    # Cost estimate (None if not yet calculated)
    cost_estimate: CostEstimateSchema | None = Field(default=None, description="Calculated cost estimate")

    # Error info (if failed)
    error_message: str | None = Field(default=None, description="Error message if analysis failed")

    # Metadata
    tokens_used: int | None = Field(default=None, description="GPT-4o tokens used")
    analysis_duration_ms: int | None = Field(default=None, description="Analysis duration in milliseconds")
    created_at: datetime = Field(description="Upload timestamp")


class FloorPlanWithRecommendationsResponse(BaseModel):
    """Response with floor plan analysis and robot recommendations."""

    model_config = ConfigDict(from_attributes=True)

    analysis: FloorPlanAnalysisResponse = Field(description="Floor plan analysis results")
    robot_recommendations: list | None = Field(
        default=None, description="Robot recommendations based on analysis"
    )
    image_url: str | None = Field(default=None, description="Signed URL for floor plan image")
    discovery_profile_updated: bool = Field(
        default=False, description="Whether discovery profile was updated with extracted data"
    )


class FloorPlanListResponse(BaseModel):
    """Response listing floor plan analyses."""

    analyses: list[FloorPlanAnalysisResponse] = Field(description="List of floor plan analyses")
    total: int = Field(description="Total number of analyses")

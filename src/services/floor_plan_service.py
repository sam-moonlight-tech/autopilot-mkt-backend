"""Floor plan analysis service using GPT-4o Vision."""

from __future__ import annotations

import base64
import json
import logging
import time
from math import ceil
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import UploadFile

from src.core.config import get_settings
from src.core.openai import get_openai_client
from src.core.supabase import get_supabase_client
from src.core.token_budget import TokenBudgetError, get_token_budget
from src.schemas.floor_plan import (
    CleaningMode,
    CostEstimateSchema,
    ExtractedFeaturesSchema,
    FeatureSummarySchema,
    FloorPlanAnalysisResponse,
    FloorPlanStatus,
    FloorPlanWithRecommendationsResponse,
    ModeCostBreakdownSchema,
    ZoneCostBreakdownSchema,
    ZoneType,
)
from src.services.floor_plan_prompts import (
    FLOOR_PLAN_ANALYSIS_SYSTEM_PROMPT,
    FLOOR_PLAN_ANALYSIS_USER_PROMPT,
    FLOOR_PLAN_EXTRACTION_SCHEMA,
)

if TYPE_CHECKING:
    from src.services.discovery_profile_service import DiscoveryProfileService

logger = logging.getLogger(__name__)

# Rate card version for tracking
RATE_CARD_VERSION = "1.0.0"

# Allowed MIME types for floor plan images
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg"}

# Maximum file size (10 MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Storage bucket name
STORAGE_BUCKET = "floor-plans"

# === Rate Card Configuration ===

# Base cost per sq ft per cleaning session (in dollars)
BASE_RATES: dict[str, float] = {
    "dry_vacuum": 0.02,
    "dry_sweep": 0.015,
    "wet_scrub": 0.04,
    "wet_vacuum": 0.03,
}

# Surface complexity multipliers
SURFACE_MULTIPLIERS: dict[str, float] = {
    "sport_court_acrylic": 1.2,  # Premium surface, requires care
    "rubber_tile": 1.0,  # Standard
    "modular": 0.9,  # Easy to clean
    "concrete": 0.8,  # Durable, simple
    "other": 1.0,
}

# Default cleaning frequencies (times per month)
DEFAULT_FREQUENCIES: dict[str, int] = {
    "court": 30,  # Daily
    "circulation": 20,  # 5x/week (includes buffer zones)
    "auxiliary": 12,  # 3x/week
}

# Default cleaning modes per zone type
DEFAULT_MODES: dict[str, str] = {
    "court": "dry_vacuum",  # Protect acrylic surface
    "circulation": "wet_scrub",  # High traffic, rubber tile
    "auxiliary": "wet_vacuum",  # General cleaning
}

# Robot coverage rates (sq ft per hour) for time estimation
ROBOT_COVERAGE_RATES: dict[str, float] = {
    "dry_vacuum": 2000,
    "dry_sweep": 2500,
    "wet_scrub": 1500,
    "wet_vacuum": 1800,
}


class FloorPlanServiceError(Exception):
    """Base exception for floor plan service errors."""

    pass


class FloorPlanUploadError(FloorPlanServiceError):
    """File upload failed."""

    pass


class FloorPlanAnalysisError(FloorPlanServiceError):
    """GPT-4o analysis failed."""

    pass


class FloorPlanService:
    """Service for floor plan upload, analysis, and cost calculation."""

    def __init__(
        self,
        discovery_profile_service: DiscoveryProfileService | None = None,
    ) -> None:
        """Initialize floor plan service.

        Args:
            discovery_profile_service: Optional service for updating discovery profiles.
        """
        self.client = get_supabase_client()
        self.openai_client = get_openai_client()
        self.settings = get_settings()
        self._discovery_profile_service = discovery_profile_service

    @property
    def discovery_profile_service(self) -> DiscoveryProfileService:
        """Get discovery profile service (lazy load)."""
        if self._discovery_profile_service is None:
            from src.services.discovery_profile_service import DiscoveryProfileService

            self._discovery_profile_service = DiscoveryProfileService()
        return self._discovery_profile_service

    async def upload_and_analyze(
        self,
        file: UploadFile,
        profile_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> FloorPlanWithRecommendationsResponse:
        """Upload a floor plan image, analyze it, and calculate costs.

        This is the main entry point - handles the full flow synchronously.

        Args:
            file: Uploaded floor plan image.
            profile_id: User's profile ID (for authenticated users).
            session_id: Session ID (for anonymous users).

        Returns:
            FloorPlanWithRecommendationsResponse with analysis, costs, and recommendations.

        Raises:
            FloorPlanUploadError: If file validation fails.
            FloorPlanAnalysisError: If GPT-4o analysis fails.
            TokenBudgetError: If token budget exceeded.
        """
        start_time = time.perf_counter()

        # Validate file
        await self._validate_file(file)

        # Read file content
        file_content = await file.read()
        await file.seek(0)

        # Create initial record
        analysis_id = await self._create_analysis_record(
            file_name=file.filename or "floor_plan.png",
            file_size=len(file_content),
            mime_type=file.content_type or "image/png",
            profile_id=profile_id,
            session_id=session_id,
        )

        try:
            # Update status to processing
            await self._update_status(analysis_id, FloorPlanStatus.PROCESSING)

            # Upload to storage
            storage_path = await self._upload_to_storage(
                analysis_id=analysis_id,
                file_content=file_content,
                file_name=file.filename or "floor_plan.png",
                mime_type=file.content_type or "image/png",
            )

            # Update record with storage path
            self.client.table("floor_plan_analyses").update(
                {"storage_path": storage_path}
            ).eq("id", str(analysis_id)).execute()

            # Check token budget
            budget_key = f"profile:{profile_id}" if profile_id else f"session:{session_id}"
            estimated_tokens = 5000  # Vision API tends to use more tokens
            token_budget = get_token_budget()
            allowed, remaining, limit = await token_budget.check_budget(
                budget_key, estimated_tokens, is_authenticated=profile_id is not None
            )

            if not allowed:
                raise TokenBudgetError(
                    message="Daily token budget exceeded for floor plan analysis.",
                    tokens_used=limit - remaining,
                    daily_limit=limit,
                )

            # Analyze with GPT-4o Vision
            extracted_features, tokens_used = await self._analyze_with_gpt4o(
                file_content=file_content,
                mime_type=file.content_type or "image/png",
            )

            # Record token usage
            if tokens_used:
                await token_budget.record_usage(budget_key, tokens_used)

            # Calculate costs
            cost_estimate = self._calculate_costs(extracted_features)

            # Determine overall confidence
            extraction_confidence = self._determine_overall_confidence(extracted_features)

            # Calculate duration
            analysis_duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Update record with results
            self.client.table("floor_plan_analyses").update(
                {
                    "status": FloorPlanStatus.COMPLETED.value,
                    "extracted_features": extracted_features.model_dump(),
                    "extraction_confidence": extraction_confidence,
                    "cost_estimate": cost_estimate.model_dump(),
                    "gpt_model_used": "gpt-4o",
                    "tokens_used": tokens_used,
                    "analysis_duration_ms": analysis_duration_ms,
                }
            ).eq("id", str(analysis_id)).execute()

            # Update discovery profile if authenticated
            discovery_updated = False
            if profile_id:
                try:
                    await self.discovery_profile_service.update_from_floor_plan(
                        profile_id=profile_id,
                        extracted_features=extracted_features,
                        cost_estimate=cost_estimate,
                    )
                    discovery_updated = True
                except Exception as e:
                    logger.warning("Failed to update discovery profile: %s", e)

            # Get robot recommendations
            recommendations = None
            if profile_id:
                try:
                    recommendations = await self._get_robot_recommendations(profile_id)
                except Exception as e:
                    logger.warning("Failed to get robot recommendations: %s", e)

            # Get signed URL for image
            image_url = await self._get_signed_url(storage_path)

            # Build response
            analysis_response = FloorPlanAnalysisResponse(
                id=analysis_id,
                status=FloorPlanStatus.COMPLETED,
                file_name=file.filename or "floor_plan.png",
                extracted_features=extracted_features,
                extraction_confidence=extraction_confidence,
                cost_estimate=cost_estimate,
                tokens_used=tokens_used,
                analysis_duration_ms=analysis_duration_ms,
                created_at=self._get_record(analysis_id)["created_at"],
            )

            return FloorPlanWithRecommendationsResponse(
                analysis=analysis_response,
                robot_recommendations=recommendations,
                image_url=image_url,
                discovery_profile_updated=discovery_updated,
            )

        except TokenBudgetError:
            await self._update_status(
                analysis_id, FloorPlanStatus.FAILED, "Token budget exceeded"
            )
            raise
        except Exception as e:
            logger.error("Floor plan analysis failed: %s", e)
            await self._update_status(analysis_id, FloorPlanStatus.FAILED, str(e))
            raise FloorPlanAnalysisError(f"Analysis failed: {e}") from e

    async def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file.

        Args:
            file: Uploaded file to validate.

        Raises:
            FloorPlanUploadError: If validation fails.
        """
        # Check MIME type
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise FloorPlanUploadError(
                f"Invalid file type: {file.content_type}. "
                f"Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
            )

        # Check file size
        content = await file.read()
        await file.seek(0)

        if len(content) > MAX_FILE_SIZE_BYTES:
            raise FloorPlanUploadError(
                f"File too large: {len(content) / (1024 * 1024):.1f} MB. "
                f"Maximum size: {MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f} MB"
            )

    async def _create_analysis_record(
        self,
        file_name: str,
        file_size: int,
        mime_type: str,
        profile_id: UUID | None,
        session_id: UUID | None,
    ) -> UUID:
        """Create initial floor plan analysis record.

        Args:
            file_name: Original file name.
            file_size: File size in bytes.
            mime_type: File MIME type.
            profile_id: User's profile ID.
            session_id: Session ID.

        Returns:
            UUID of created record.
        """
        data = {
            "file_name": file_name,
            "file_size_bytes": file_size,
            "file_mime_type": mime_type,
            "storage_path": "",  # Will be updated after upload
            "status": FloorPlanStatus.PENDING.value,
        }

        if profile_id:
            data["profile_id"] = str(profile_id)
        if session_id:
            data["session_id"] = str(session_id)

        response = self.client.table("floor_plan_analyses").insert(data).execute()
        return UUID(response.data[0]["id"])

    async def _upload_to_storage(
        self,
        analysis_id: UUID,
        file_content: bytes,
        file_name: str,
        mime_type: str,
    ) -> str:
        """Upload file to Supabase Storage.

        Args:
            analysis_id: Analysis record ID.
            file_content: File content bytes.
            file_name: Original file name.
            mime_type: File MIME type.

        Returns:
            Storage path.
        """
        # Generate storage path
        extension = file_name.split(".")[-1] if "." in file_name else "png"
        storage_path = f"{analysis_id}/floor_plan.{extension}"

        # Upload to storage
        self.client.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": mime_type},
        )

        return storage_path

    async def _get_signed_url(self, storage_path: str, expires_in: int = 3600) -> str:
        """Get signed URL for stored image.

        Args:
            storage_path: Path in storage bucket.
            expires_in: URL expiration time in seconds.

        Returns:
            Signed URL string.
        """
        response = self.client.storage.from_(STORAGE_BUCKET).create_signed_url(
            path=storage_path,
            expires_in=expires_in,
        )
        return response["signedURL"]

    async def _analyze_with_gpt4o(
        self,
        file_content: bytes,
        mime_type: str,
    ) -> tuple[ExtractedFeaturesSchema, int | None]:
        """Analyze floor plan with GPT-4o Vision API.

        Args:
            file_content: Image file content.
            mime_type: Image MIME type.

        Returns:
            Tuple of (extracted features, tokens used).
        """
        # Encode image as base64
        base64_image = base64.b64encode(file_content).decode("utf-8")
        image_url = f"data:{mime_type};base64,{base64_image}"

        # Call GPT-4o Vision
        response = self.openai_client.chat.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": FLOOR_PLAN_ANALYSIS_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": FLOOR_PLAN_ANALYSIS_USER_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url, "detail": "high"},
                        },
                    ],
                },
            ],
            response_format=FLOOR_PLAN_EXTRACTION_SCHEMA,
            max_tokens=4000,
        )

        # Parse response
        content = response.choices[0].message.content
        if not content:
            raise FloorPlanAnalysisError("GPT-4o returned empty response")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise FloorPlanAnalysisError(f"Failed to parse GPT-4o response: {e}") from e

        # Convert to Pydantic model
        features = self._parse_extracted_features(data)

        # Get token usage
        tokens_used = response.usage.total_tokens if response.usage else None

        return features, tokens_used

    def _parse_extracted_features(self, data: dict[str, Any]) -> ExtractedFeaturesSchema:
        """Parse GPT-4o response into ExtractedFeaturesSchema.

        Args:
            data: Raw JSON data from GPT-4o.

        Returns:
            Parsed ExtractedFeaturesSchema.
        """
        from src.schemas.floor_plan import (
            AuxiliaryAreaSchema,
            BufferZoneSchema,
            CirculationAreaSchema,
            CourtSchema,
            DimensionsSchema,
            ExcludedAreaSchema,
            ExclusionReason,
            FacilityDimensionsSchema,
            ObstructionHandling,
            ObstructionSchema,
            ObstructionType,
            SurfaceType,
        )

        # Parse facility dimensions
        facility_dims = None
        if data.get("facility_dimensions"):
            fd = data["facility_dimensions"]
            facility_dims = FacilityDimensionsSchema(
                length_ft=fd.get("length_ft", 0),
                width_ft=fd.get("width_ft", 0),
                total_sqft=fd.get("total_sqft", 0),
                confidence=fd.get("confidence", 0.5),
            )

        # Parse courts
        courts = []
        for court_data in data.get("courts", []):
            courts.append(
                CourtSchema(
                    label=court_data.get("label", "Court"),
                    dimensions=DimensionsSchema(
                        length_ft=court_data.get("length_ft", 44),
                        width_ft=court_data.get("width_ft", 20),
                    )
                    if court_data.get("length_ft") and court_data.get("width_ft")
                    else None,
                    sqft=court_data.get("sqft", 880),
                    surface_type=SurfaceType(
                        court_data.get("surface_type", "sport_court_acrylic")
                    ),
                    max_occupancy=court_data.get("max_occupancy"),
                    has_net=court_data.get("has_net", True),
                    confidence=court_data.get("confidence", 0.5),
                )
            )

        # Parse buffer zones
        buffer_zones = []
        for bz_data in data.get("buffer_zones", []):
            buffer_zones.append(
                BufferZoneSchema(
                    between_courts=bz_data.get("between_courts", []),
                    width_ft=bz_data.get("width_ft", 8),
                    length_ft=bz_data.get("length_ft", 44),
                    sqft=bz_data.get("sqft", 0),
                    confidence=bz_data.get("confidence", 0.5),
                )
            )

        # Parse circulation areas
        circulation_areas = []
        for ca_data in data.get("circulation_areas", []):
            circulation_areas.append(
                CirculationAreaSchema(
                    label=ca_data.get("label", "Circulation"),
                    sqft=ca_data.get("sqft", 0),
                    surface_type=SurfaceType(ca_data.get("surface_type", "rubber_tile")),
                    is_hex_textured=ca_data.get("is_hex_textured", False),
                    confidence=ca_data.get("confidence", 0.5),
                )
            )

        # Parse auxiliary areas
        auxiliary_areas = []
        for aa_data in data.get("auxiliary_areas", []):
            auxiliary_areas.append(
                AuxiliaryAreaSchema(
                    label=aa_data.get("label", "Auxiliary"),
                    sqft=aa_data.get("sqft", 0),
                    surface_type=SurfaceType(aa_data.get("surface_type", "other")),
                    cleanable_by_robot=aa_data.get("cleanable_by_robot", True),
                    confidence=aa_data.get("confidence", 0.5),
                )
            )

        # Parse excluded areas
        excluded_areas = []
        for ea_data in data.get("excluded_areas", []):
            excluded_areas.append(
                ExcludedAreaSchema(
                    label=ea_data.get("label", "Excluded"),
                    sqft=ea_data.get("sqft", 0),
                    reason=ExclusionReason(ea_data.get("reason", "manual_only")),
                    confidence=ea_data.get("confidence", 0.5),
                )
            )

        # Parse obstructions
        obstructions = []
        for obs_data in data.get("obstructions", []):
            obstructions.append(
                ObstructionSchema(
                    type=ObstructionType(obs_data.get("type", "other")),
                    location=obs_data.get("location", ""),
                    handling=ObstructionHandling(
                        obs_data.get("handling", "navigate_around")
                    ),
                )
            )

        # Parse or calculate summary
        summary_data = data.get("summary", {})
        summary = FeatureSummarySchema(
            total_court_sqft=summary_data.get(
                "total_court_sqft", sum(c.sqft for c in courts)
            ),
            total_circulation_sqft=summary_data.get(
                "total_circulation_sqft",
                sum(ca.sqft for ca in circulation_areas)
                + sum(bz.sqft for bz in buffer_zones),
            ),
            total_auxiliary_sqft=summary_data.get(
                "total_auxiliary_sqft",
                sum(aa.sqft for aa in auxiliary_areas if aa.cleanable_by_robot),
            ),
            total_excluded_sqft=summary_data.get(
                "total_excluded_sqft", sum(ea.sqft for ea in excluded_areas)
            ),
            total_cleanable_sqft=summary_data.get("total_cleanable_sqft", 0),
            court_count=summary_data.get("court_count", len(courts)),
        )

        # Calculate total cleanable if not provided
        if summary.total_cleanable_sqft == 0:
            summary = FeatureSummarySchema(
                total_court_sqft=summary.total_court_sqft,
                total_circulation_sqft=summary.total_circulation_sqft,
                total_auxiliary_sqft=summary.total_auxiliary_sqft,
                total_excluded_sqft=summary.total_excluded_sqft,
                total_cleanable_sqft=(
                    summary.total_court_sqft
                    + summary.total_circulation_sqft
                    + summary.total_auxiliary_sqft
                ),
                court_count=summary.court_count,
            )

        return ExtractedFeaturesSchema(
            facility_dimensions=facility_dims,
            courts=courts,
            buffer_zones=buffer_zones,
            circulation_areas=circulation_areas,
            auxiliary_areas=auxiliary_areas,
            excluded_areas=excluded_areas,
            obstructions=obstructions,
            summary=summary,
            extraction_notes=data.get("extraction_notes"),
        )

    def _calculate_costs(
        self,
        features: ExtractedFeaturesSchema,
    ) -> CostEstimateSchema:
        """Calculate cleaning costs from extracted features.

        Args:
            features: Extracted floor plan features.

        Returns:
            CostEstimateSchema with full breakdown.
        """
        zone_breakdown: list[ZoneCostBreakdownSchema] = []
        mode_totals: dict[str, dict[str, float]] = {}

        # Calculate court costs (daily, dry vacuum)
        court_mode = CleaningMode.DRY_VACUUM
        court_freq = DEFAULT_FREQUENCIES["court"]
        court_rate = BASE_RATES[court_mode.value]

        for court in features.courts:
            surface_mult = SURFACE_MULTIPLIERS.get(court.surface_type.value, 1.0)
            cost_per_cleaning = court.sqft * court_rate * surface_mult
            monthly_cost = cost_per_cleaning * court_freq

            zone_breakdown.append(
                ZoneCostBreakdownSchema(
                    zone_type=ZoneType.COURT,
                    zone_label=court.label,
                    sqft=court.sqft,
                    cleaning_mode=court_mode,
                    frequency_per_month=court_freq,
                    cost_per_cleaning=round(cost_per_cleaning, 2),
                    monthly_cost=round(monthly_cost, 2),
                )
            )

            # Aggregate by mode
            if court_mode.value not in mode_totals:
                mode_totals[court_mode.value] = {"sqft": 0, "monthly_cost": 0}
            mode_totals[court_mode.value]["sqft"] += court.sqft
            mode_totals[court_mode.value]["monthly_cost"] += monthly_cost

        # Calculate buffer zone costs (circulation frequency, dry sweep)
        buffer_mode = CleaningMode.DRY_SWEEP
        buffer_freq = DEFAULT_FREQUENCIES["circulation"]
        buffer_rate = BASE_RATES[buffer_mode.value]

        for buffer in features.buffer_zones:
            cost_per_cleaning = buffer.sqft * buffer_rate
            monthly_cost = cost_per_cleaning * buffer_freq

            zone_breakdown.append(
                ZoneCostBreakdownSchema(
                    zone_type=ZoneType.CIRCULATION,
                    zone_label=f"Buffer: {', '.join(buffer.between_courts)}",
                    sqft=buffer.sqft,
                    cleaning_mode=buffer_mode,
                    frequency_per_month=buffer_freq,
                    cost_per_cleaning=round(cost_per_cleaning, 2),
                    monthly_cost=round(monthly_cost, 2),
                )
            )

            if buffer_mode.value not in mode_totals:
                mode_totals[buffer_mode.value] = {"sqft": 0, "monthly_cost": 0}
            mode_totals[buffer_mode.value]["sqft"] += buffer.sqft
            mode_totals[buffer_mode.value]["monthly_cost"] += monthly_cost

        # Calculate circulation costs (5x/week, wet scrub)
        circ_mode = CleaningMode.WET_SCRUB
        circ_freq = DEFAULT_FREQUENCIES["circulation"]
        circ_rate = BASE_RATES[circ_mode.value]

        for area in features.circulation_areas:
            surface_mult = SURFACE_MULTIPLIERS.get(area.surface_type.value, 1.0)
            cost_per_cleaning = area.sqft * circ_rate * surface_mult
            monthly_cost = cost_per_cleaning * circ_freq

            zone_breakdown.append(
                ZoneCostBreakdownSchema(
                    zone_type=ZoneType.CIRCULATION,
                    zone_label=area.label,
                    sqft=area.sqft,
                    cleaning_mode=circ_mode,
                    frequency_per_month=circ_freq,
                    cost_per_cleaning=round(cost_per_cleaning, 2),
                    monthly_cost=round(monthly_cost, 2),
                )
            )

            if circ_mode.value not in mode_totals:
                mode_totals[circ_mode.value] = {"sqft": 0, "monthly_cost": 0}
            mode_totals[circ_mode.value]["sqft"] += area.sqft
            mode_totals[circ_mode.value]["monthly_cost"] += monthly_cost

        # Calculate auxiliary costs (3x/week, wet vacuum)
        aux_mode = CleaningMode.WET_VACUUM
        aux_freq = DEFAULT_FREQUENCIES["auxiliary"]
        aux_rate = BASE_RATES[aux_mode.value]

        for area in features.auxiliary_areas:
            if not area.cleanable_by_robot:
                continue

            surface_mult = SURFACE_MULTIPLIERS.get(area.surface_type.value, 1.0)
            cost_per_cleaning = area.sqft * aux_rate * surface_mult
            monthly_cost = cost_per_cleaning * aux_freq

            zone_breakdown.append(
                ZoneCostBreakdownSchema(
                    zone_type=ZoneType.AUXILIARY,
                    zone_label=area.label,
                    sqft=area.sqft,
                    cleaning_mode=aux_mode,
                    frequency_per_month=aux_freq,
                    cost_per_cleaning=round(cost_per_cleaning, 2),
                    monthly_cost=round(monthly_cost, 2),
                )
            )

            if aux_mode.value not in mode_totals:
                mode_totals[aux_mode.value] = {"sqft": 0, "monthly_cost": 0}
            mode_totals[aux_mode.value]["sqft"] += area.sqft
            mode_totals[aux_mode.value]["monthly_cost"] += monthly_cost

        # Build mode breakdown
        mode_breakdown = []
        for mode_name, totals in mode_totals.items():
            mode_breakdown.append(
                ModeCostBreakdownSchema(
                    mode=CleaningMode(mode_name),
                    total_sqft=round(totals["sqft"], 2),
                    rate_per_sqft=BASE_RATES[mode_name],
                    cleanings_per_month=DEFAULT_FREQUENCIES.get(
                        "court" if mode_name == "dry_vacuum" else "circulation", 20
                    ),
                    monthly_cost=round(totals["monthly_cost"], 2),
                )
            )

        # Calculate totals
        total_monthly = sum(z.monthly_cost for z in zone_breakdown)
        total_daily = total_monthly / 30

        # Estimate cleaning time
        daily_hours = self._estimate_cleaning_time(features)
        robot_count = max(1, ceil(daily_hours / 6))  # 6-hour shifts

        return CostEstimateSchema(
            total_monthly_cost=round(total_monthly, 2),
            total_daily_cost=round(total_daily, 2),
            breakdown_by_zone=zone_breakdown,
            breakdown_by_mode=mode_breakdown,
            estimated_daily_cleaning_hours=round(daily_hours, 2),
            estimated_robot_count=robot_count,
            rate_card_version=RATE_CARD_VERSION,
        )

    def _estimate_cleaning_time(self, features: ExtractedFeaturesSchema) -> float:
        """Estimate daily cleaning time in hours.

        Args:
            features: Extracted floor plan features.

        Returns:
            Estimated hours per day.
        """
        total_hours = 0.0

        # Courts (daily)
        court_sqft = features.summary.total_court_sqft
        court_hours = court_sqft / ROBOT_COVERAGE_RATES["dry_vacuum"]
        total_hours += court_hours

        # Circulation (daily portion - ~5/7 days = 0.71)
        circ_sqft = features.summary.total_circulation_sqft
        circ_hours = circ_sqft / ROBOT_COVERAGE_RATES["wet_scrub"]
        total_hours += circ_hours * 0.71

        # Auxiliary (3x/week = ~0.43 daily)
        aux_sqft = features.summary.total_auxiliary_sqft
        aux_hours = aux_sqft / ROBOT_COVERAGE_RATES["wet_vacuum"]
        total_hours += aux_hours * 0.43

        # Add 15% for transitions/setup
        total_hours *= 1.15

        return total_hours

    def _determine_overall_confidence(
        self,
        features: ExtractedFeaturesSchema,
    ) -> str:
        """Determine overall extraction confidence.

        Args:
            features: Extracted features.

        Returns:
            Confidence level string: 'high', 'medium', or 'low'.
        """
        confidences = []

        # Collect all confidence scores
        if features.facility_dimensions:
            confidences.append(features.facility_dimensions.confidence)
        for court in features.courts:
            confidences.append(court.confidence)
        for area in features.circulation_areas:
            confidences.append(area.confidence)

        if not confidences:
            return "low"

        avg_confidence = sum(confidences) / len(confidences)

        if avg_confidence >= 0.85:
            return "high"
        elif avg_confidence >= 0.6:
            return "medium"
        else:
            return "low"

    async def _get_robot_recommendations(self, profile_id: UUID) -> list[dict] | None:
        """Get robot recommendations based on discovery profile.

        Args:
            profile_id: User's profile ID.

        Returns:
            List of robot recommendations or None.
        """
        from src.schemas.roi import RecommendationsRequest
        from src.services.roi_service import get_roi_service

        # Get discovery profile with updated answers
        profile = await self.discovery_profile_service.get_by_profile_id(profile_id)
        if not profile:
            return None

        answers = profile.get("answers", {})
        if not answers:
            return None

        # Get recommendations
        roi_service = get_roi_service()
        try:
            response = await roi_service.get_recommendations(
                RecommendationsRequest(answers=answers, top_k=3),
                profile_id=profile_id,
            )
            return [r.model_dump() for r in response.recommendations]
        except Exception as e:
            logger.warning("Failed to get recommendations: %s", e)
            return None

    async def _update_status(
        self,
        analysis_id: UUID,
        status: FloorPlanStatus,
        error_message: str | None = None,
    ) -> None:
        """Update analysis record status.

        Args:
            analysis_id: Analysis record ID.
            status: New status.
            error_message: Optional error message.
        """
        data: dict[str, Any] = {"status": status.value}
        if error_message:
            data["error_message"] = error_message

        self.client.table("floor_plan_analyses").update(data).eq(
            "id", str(analysis_id)
        ).execute()

    def _get_record(self, analysis_id: UUID) -> dict[str, Any]:
        """Get analysis record by ID.

        Args:
            analysis_id: Analysis record ID.

        Returns:
            Record data.
        """
        response = (
            self.client.table("floor_plan_analyses")
            .select("*")
            .eq("id", str(analysis_id))
            .single()
            .execute()
        )
        return response.data

    async def get_analysis(
        self,
        analysis_id: UUID,
        profile_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> FloorPlanAnalysisResponse | None:
        """Get floor plan analysis by ID.

        Args:
            analysis_id: Analysis record ID.
            profile_id: User's profile ID for access control.
            session_id: Session ID for access control.

        Returns:
            FloorPlanAnalysisResponse or None if not found/not authorized.
        """
        query = self.client.table("floor_plan_analyses").select("*").eq("id", str(analysis_id))

        # Add ownership filter
        if profile_id:
            query = query.eq("profile_id", str(profile_id))
        elif session_id:
            query = query.eq("session_id", str(session_id))

        response = query.maybe_single().execute()

        if not response.data:
            return None

        data = response.data
        return FloorPlanAnalysisResponse(
            id=UUID(data["id"]),
            status=FloorPlanStatus(data["status"]),
            file_name=data["file_name"],
            extracted_features=(
                ExtractedFeaturesSchema(**data["extracted_features"])
                if data.get("extracted_features")
                else None
            ),
            extraction_confidence=data.get("extraction_confidence"),
            cost_estimate=(
                CostEstimateSchema(**data["cost_estimate"])
                if data.get("cost_estimate")
                else None
            ),
            error_message=data.get("error_message"),
            tokens_used=data.get("tokens_used"),
            analysis_duration_ms=data.get("analysis_duration_ms"),
            created_at=data["created_at"],
        )

    async def list_analyses(
        self,
        profile_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> list[FloorPlanAnalysisResponse]:
        """List floor plan analyses for a user/session.

        Args:
            profile_id: User's profile ID.
            session_id: Session ID.

        Returns:
            List of FloorPlanAnalysisResponse.
        """
        query = self.client.table("floor_plan_analyses").select("*")

        if profile_id:
            query = query.eq("profile_id", str(profile_id))
        elif session_id:
            query = query.eq("session_id", str(session_id))
        else:
            return []

        query = query.order("created_at", desc=True)
        response = query.execute()

        analyses = []
        for data in response.data:
            analyses.append(
                FloorPlanAnalysisResponse(
                    id=UUID(data["id"]),
                    status=FloorPlanStatus(data["status"]),
                    file_name=data["file_name"],
                    extracted_features=(
                        ExtractedFeaturesSchema(**data["extracted_features"])
                        if data.get("extracted_features")
                        else None
                    ),
                    extraction_confidence=data.get("extraction_confidence"),
                    cost_estimate=(
                        CostEstimateSchema(**data["cost_estimate"])
                        if data.get("cost_estimate")
                        else None
                    ),
                    error_message=data.get("error_message"),
                    tokens_used=data.get("tokens_used"),
                    analysis_duration_ms=data.get("analysis_duration_ms"),
                    created_at=data["created_at"],
                )
            )

        return analyses

    async def delete_analysis(
        self,
        analysis_id: UUID,
        profile_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> bool:
        """Delete floor plan analysis and associated storage.

        Args:
            analysis_id: Analysis record ID.
            profile_id: User's profile ID for access control.
            session_id: Session ID for access control.

        Returns:
            True if deleted, False if not found/not authorized.
        """
        # Get record first to check ownership and get storage path
        query = self.client.table("floor_plan_analyses").select("*").eq("id", str(analysis_id))

        if profile_id:
            query = query.eq("profile_id", str(profile_id))
        elif session_id:
            query = query.eq("session_id", str(session_id))

        response = query.maybe_single().execute()

        if not response.data:
            return False

        storage_path = response.data.get("storage_path")

        # Delete from storage
        if storage_path:
            try:
                self.client.storage.from_(STORAGE_BUCKET).remove([storage_path])
            except Exception as e:
                logger.warning("Failed to delete from storage: %s", e)

        # Delete record
        self.client.table("floor_plan_analyses").delete().eq(
            "id", str(analysis_id)
        ).execute()

        return True


# Singleton instance
_floor_plan_service: FloorPlanService | None = None


def get_floor_plan_service() -> FloorPlanService:
    """Get or create the floor plan service singleton."""
    global _floor_plan_service
    if _floor_plan_service is None:
        _floor_plan_service = FloorPlanService()
    return _floor_plan_service

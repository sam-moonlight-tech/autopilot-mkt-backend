"""Discovery profile business logic service."""

from __future__ import annotations

import json
import logging
from hashlib import sha256
from typing import TYPE_CHECKING, Any
from uuid import UUID

from src.core.supabase import get_supabase_client
from src.schemas.discovery import DiscoveryProfileUpdate

if TYPE_CHECKING:
    from src.schemas.floor_plan import CostEstimateSchema, ExtractedFeaturesSchema

logger = logging.getLogger(__name__)


def compute_answers_hash(answers: dict[str, Any]) -> str:
    """Compute a deterministic hash of discovery answers.

    Args:
        answers: Discovery answers dictionary.

    Returns:
        16-character hex hash string.
    """
    # Extract just the values for consistent hashing
    simplified = {}
    for k, v in sorted(answers.items()):
        if isinstance(v, dict):
            simplified[k] = v.get("value", "")
        else:
            simplified[k] = str(v) if v else ""

    # Create deterministic JSON string
    json_str = json.dumps(simplified, sort_keys=True)
    return sha256(json_str.encode()).hexdigest()[:16]


class DiscoveryProfileService:
    """Service for managing authenticated user discovery profiles."""

    def __init__(self) -> None:
        """Initialize discovery profile service with Supabase client."""
        self.client = get_supabase_client()

    async def get_or_create(self, profile_id: UUID) -> dict[str, Any]:
        """Get existing discovery profile or create a new one.

        Args:
            profile_id: The user's profile UUID.

        Returns:
            dict: The discovery profile data.
        """
        # First try to get existing profile
        response = (
            self.client.table("discovery_profiles")
            .select("*")
            .eq("profile_id", str(profile_id))
            .execute()
        )

        if response.data:
            return response.data[0]

        # Create new discovery profile if not exists
        profile_data = {
            "profile_id": str(profile_id),
            "current_question_index": 0,
            "phase": "discovery",
            "answers": {},
            "selected_product_ids": [],
        }

        response = (
            self.client.table("discovery_profiles")
            .insert(profile_data)
            .execute()
        )

        return response.data[0]

    async def get_by_profile_id(self, profile_id: UUID) -> dict[str, Any] | None:
        """Get a discovery profile by profile ID.

        Args:
            profile_id: The user's profile UUID.

        Returns:
            dict | None: The discovery profile data or None if not found.
        """
        logger.debug("Looking up discovery_profile for profile_id=%s", profile_id)
        response = (
            self.client.table("discovery_profiles")
            .select("*")
            .eq("profile_id", str(profile_id))
            .maybe_single()
            .execute()
        )

        if response and response.data:
            answers = response.data.get("answers", {})
            logger.debug(
                "Found discovery_profile id=%s with %d answers",
                response.data.get("id"),
                len(answers) if answers else 0,
            )
            return response.data
        else:
            logger.warning("No discovery_profile found for profile_id=%s", profile_id)
            return None

    async def update(
        self,
        profile_id: UUID,
        data: DiscoveryProfileUpdate,
    ) -> dict[str, Any] | None:
        """Update a discovery profile.

        Args:
            profile_id: The user's profile UUID.
            data: The fields to update.

        Returns:
            dict | None: The updated discovery profile data or None if not found.
        """
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)

        # Convert nested Pydantic models to dicts for JSONB storage
        if "answers" in update_data:
            update_data["answers"] = {
                k: v.model_dump() if hasattr(v, "model_dump") else v
                for k, v in update_data["answers"].items()
            }
        if "roi_inputs" in update_data and update_data["roi_inputs"]:
            roi = update_data["roi_inputs"]
            update_data["roi_inputs"] = roi.model_dump() if hasattr(roi, "model_dump") else roi
        if "greenlight" in update_data and update_data["greenlight"]:
            greenlight = update_data["greenlight"]
            if hasattr(greenlight, "model_dump"):
                greenlight_dict = greenlight.model_dump()
                # Convert nested team_members Pydantic models
                if "team_members" in greenlight_dict:
                    greenlight_dict["team_members"] = [
                        m.model_dump() if hasattr(m, "model_dump") else m
                        for m in greenlight_dict["team_members"]
                    ]
                update_data["greenlight"] = greenlight_dict
            else:
                update_data["greenlight"] = greenlight

        # Convert UUID list to string list for PostgreSQL
        if "selected_product_ids" in update_data:
            update_data["selected_product_ids"] = [
                str(uid) for uid in update_data["selected_product_ids"]
            ]

        if not update_data:
            # No changes, return current profile
            return await self.get_by_profile_id(profile_id)

        response = (
            self.client.table("discovery_profiles")
            .update(update_data)
            .eq("profile_id", str(profile_id))
            .execute()
        )

        return response.data[0] if response.data else None

    async def create_from_session(
        self,
        profile_id: UUID,
        session_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a discovery profile from session data.

        Used when claiming a session to transfer data to user profile.

        Args:
            profile_id: The user's profile UUID.
            session_data: The session data to copy.

        Returns:
            dict: The created discovery profile.
        """
        # Check if discovery profile already exists
        existing = await self.get_by_profile_id(profile_id)

        profile_data = {
            "current_question_index": session_data.get("current_question_index", 0),
            "phase": session_data.get("phase", "discovery"),
            "answers": session_data.get("answers", {}),
            "roi_inputs": session_data.get("roi_inputs"),
            "selected_product_ids": session_data.get("selected_product_ids", []),
            "timeframe": session_data.get("timeframe"),
            "greenlight": session_data.get("greenlight"),
        }

        if existing:
            # Update existing profile (merge session data)
            response = (
                self.client.table("discovery_profiles")
                .update(profile_data)
                .eq("profile_id", str(profile_id))
                .execute()
            )
        else:
            # Create new profile
            profile_data["profile_id"] = str(profile_id)
            response = (
                self.client.table("discovery_profiles")
                .insert(profile_data)
                .execute()
            )

        return response.data[0]

    async def get_cached_recommendations(
        self,
        profile_id: UUID,
        current_answers: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Get cached recommendations if the answers hash matches.

        Args:
            profile_id: The user's profile UUID.
            current_answers: Current discovery answers to validate cache.

        Returns:
            Cached recommendations dict or None if cache is invalid.
        """
        profile = await self.get_by_profile_id(profile_id)
        if not profile:
            return None

        stored_hash = profile.get("answers_hash")
        cached = profile.get("cached_recommendations")

        if not stored_hash or not cached:
            logger.debug("No cached recommendations for profile %s", profile_id)
            return None

        # Compute hash of current answers
        current_hash = compute_answers_hash(current_answers)

        if stored_hash != current_hash:
            logger.debug(
                "Cached recommendations stale for profile %s (hash mismatch: %s vs %s)",
                profile_id, stored_hash, current_hash
            )
            return None

        logger.info("Returning cached recommendations for profile %s", profile_id)
        return cached

    async def set_cached_recommendations(
        self,
        profile_id: UUID,
        answers: dict[str, Any],
        recommendations: dict[str, Any],
    ) -> None:
        """Store cached recommendations with answers hash.

        Args:
            profile_id: The user's profile UUID.
            answers: Current discovery answers (used for hash).
            recommendations: Recommendations response to cache.
        """
        answers_hash = compute_answers_hash(answers)

        try:
            self.client.table("discovery_profiles").update({
                "answers_hash": answers_hash,
                "cached_recommendations": recommendations,
            }).eq("profile_id", str(profile_id)).execute()

            logger.info(
                "Cached recommendations for profile %s (hash: %s)",
                profile_id, answers_hash
            )
        except Exception as e:
            # Don't fail the request if caching fails
            logger.error("Failed to cache recommendations: %s", e)

    async def invalidate_recommendations_cache(self, profile_id: UUID) -> None:
        """Invalidate cached recommendations when answers change.

        Args:
            profile_id: The user's profile UUID.
        """
        try:
            self.client.table("discovery_profiles").update({
                "answers_hash": None,
                "cached_recommendations": None,
            }).eq("profile_id", str(profile_id)).execute()

            logger.debug("Invalidated recommendations cache for profile %s", profile_id)
        except Exception as e:
            logger.error("Failed to invalidate cache: %s", e)

    async def update_from_floor_plan(
        self,
        profile_id: UUID,
        extracted_features: ExtractedFeaturesSchema,
        cost_estimate: CostEstimateSchema,
    ) -> dict[str, Any] | None:
        """Update discovery profile with data extracted from floor plan analysis.

        This method auto-populates discovery answers based on the extracted
        floor plan features, accelerating users through the discovery flow.

        Args:
            profile_id: The user's profile UUID.
            extracted_features: Features extracted from floor plan via GPT-4o.
            cost_estimate: Calculated cleaning cost estimate.

        Returns:
            Updated discovery profile or None if update fails.
        """
        # Ensure profile exists
        profile = await self.get_or_create(profile_id)

        # Get existing answers
        existing_answers = profile.get("answers", {})

        # Build new answers from floor plan data
        new_answers = self._build_answers_from_floor_plan(extracted_features, cost_estimate)

        # Merge with existing answers (floor plan data takes precedence)
        merged_answers = {**existing_answers, **new_answers}

        # Build ROI inputs from cost estimate
        roi_inputs = {
            "labor_rate": 25.0,  # Default labor rate
            "utilization": 1.0,
            "maintenance_factor": 0.05,
            "manual_monthly_spend": cost_estimate.total_monthly_cost,
            "manual_monthly_hours": (
                cost_estimate.estimated_daily_cleaning_hours * 30
                if cost_estimate.estimated_daily_cleaning_hours
                else 60.0
            ),
        }

        # Update discovery profile
        update_data = {
            "answers": merged_answers,
            "roi_inputs": roi_inputs,
        }

        try:
            response = (
                self.client.table("discovery_profiles")
                .update(update_data)
                .eq("profile_id", str(profile_id))
                .execute()
            )

            # Invalidate recommendations cache since answers changed
            await self.invalidate_recommendations_cache(profile_id)

            logger.info(
                "Updated discovery profile %s from floor plan: %d answers populated",
                profile_id,
                len(new_answers),
            )

            return response.data[0] if response.data else None

        except Exception as e:
            logger.error("Failed to update discovery profile from floor plan: %s", e)
            return None

    def _build_answers_from_floor_plan(
        self,
        features: ExtractedFeaturesSchema,
        cost_estimate: CostEstimateSchema,
    ) -> dict[str, dict[str, Any]]:
        """Build discovery answers from floor plan extracted features.

        Args:
            features: Extracted floor plan features.
            cost_estimate: Calculated cost estimate.

        Returns:
            Dictionary of discovery answers.
        """
        answers: dict[str, dict[str, Any]] = {}

        # Infer company type from courts
        if features.courts:
            # Check for pickleball vs tennis based on dimensions
            first_court = features.courts[0]
            if first_court.sqft < 1500:  # Pickleball courts are ~880 sq ft
                company_type = "Pickleball Club"
            else:
                company_type = "Tennis Club"

            answers["company_type"] = {
                "questionId": 2,
                "key": "company_type",
                "label": "Company Type",
                "value": company_type,
                "group": "Company",
                "source": "floor_plan_analysis",
            }

        # Courts count
        court_count = features.summary.court_count
        if court_count > 0:
            if court_count < 4:
                courts_value = "<4"
            elif court_count <= 6:
                courts_value = "6"
            elif court_count <= 8:
                courts_value = "8"
            else:
                courts_value = "12+"

            answers["courts_count"] = {
                "questionId": 6,
                "key": "courts_count",
                "label": "Indoor Courts",
                "value": courts_value,
                "group": "Facility",
                "source": "floor_plan_analysis",
            }

        # Total square footage
        total_sqft = features.summary.total_cleanable_sqft
        if total_sqft > 0:
            answers["sqft"] = {
                "questionId": 8,
                "key": "sqft",
                "label": "Total Sq Ft",
                "value": f"{int(total_sqft):,} sq ft",
                "group": "Facility",
                "source": "floor_plan_analysis",
            }

        # Surface types
        surface_types = set()
        for court in features.courts:
            if court.surface_type.value == "sport_court_acrylic":
                surface_types.add("Acrylic Court")
        for area in features.circulation_areas:
            if area.surface_type.value == "rubber_tile":
                surface_types.add("Rubber Tile")
            elif area.surface_type.value == "modular":
                surface_types.add("Modular Flooring")

        if surface_types:
            answers["surfaces"] = {
                "questionId": 7,
                "key": "surfaces",
                "label": "Surface Types",
                "value": ", ".join(sorted(surface_types)),
                "group": "Facility",
                "source": "floor_plan_analysis",
            }

        # Cleaning method (inferred from surfaces)
        methods = set()
        if features.summary.total_court_sqft > 0:
            methods.add("Vacuum")
        if features.summary.total_circulation_sqft > 0:
            methods.add("Mop")

        if methods:
            answers["method"] = {
                "questionId": 9,
                "key": "method",
                "label": "Cleaning Method",
                "value": " and ".join(sorted(methods)),
                "group": "Operations",
                "source": "floor_plan_analysis",
            }

        # Monthly spend bracket
        monthly_cost = cost_estimate.total_monthly_cost
        spend_bracket = self._estimate_spend_bracket(monthly_cost)
        answers["monthly_spend"] = {
            "questionId": 12,
            "key": "monthly_spend",
            "label": "Monthly Spend",
            "value": spend_bracket,
            "group": "Economics",
            "source": "floor_plan_analysis",
        }

        # Cleaning frequency (default for courts)
        answers["frequency"] = {
            "questionId": 13,
            "key": "frequency",
            "label": "Cleaning Frequency",
            "value": "Daily",
            "group": "Operations",
            "source": "floor_plan_analysis",
        }

        # Cleaning duration
        if cost_estimate.estimated_daily_cleaning_hours:
            hours = cost_estimate.estimated_daily_cleaning_hours
            if hours <= 1.5:
                duration = "1 hr"
            elif hours <= 3:
                duration = "2 hr"
            else:
                duration = "4 hr"

            answers["duration"] = {
                "questionId": 15,
                "key": "duration",
                "label": "Session Duration",
                "value": duration,
                "group": "Operations",
                "source": "floor_plan_analysis",
            }

        return answers

    @staticmethod
    def _estimate_spend_bracket(monthly_cost: float) -> str:
        """Convert monthly cost to spend bracket for discovery answers.

        Args:
            monthly_cost: Calculated monthly cleaning cost.

        Returns:
            Spend bracket string matching discovery answer options.
        """
        if monthly_cost < 2000:
            return "<$2,000"
        elif monthly_cost < 5000:
            return "$2,000 - $5,000"
        elif monthly_cost < 10000:
            return "$5,000 - $10,000"
        else:
            return "$10,000+"

"""Discovery profile business logic service."""

import json
import logging
from hashlib import sha256
from typing import Any
from uuid import UUID

from src.core.supabase import get_supabase_client
from src.schemas.discovery import DiscoveryProfileUpdate

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

"""Discovery profile business logic service."""

from typing import Any
from uuid import UUID

from src.core.supabase import get_supabase_client
from src.schemas.discovery import DiscoveryProfileUpdate


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
        response = (
            self.client.table("discovery_profiles")
            .select("*")
            .eq("profile_id", str(profile_id))
            .maybe_single()
            .execute()
        )

        return response.data if response and response.data else None

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

"""Profile business logic service."""

from typing import Any
from uuid import UUID

from src.core.supabase import get_supabase_client
from src.schemas.profile import CompanySummary, ProfileResponse, ProfileUpdate


class ProfileService:
    """Service for managing user profiles."""

    def __init__(self) -> None:
        """Initialize profile service with Supabase client."""
        self.client = get_supabase_client()

    async def get_or_create_profile(
        self,
        user_id: UUID,
        email: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """Get existing profile or create a new one.

        Uses upsert logic to atomically create or return existing profile.

        Args:
            user_id: The auth user ID.
            email: User's email address.
            display_name: User's display name.

        Returns:
            dict: The profile data.
        """
        # First try to get existing profile
        response = (
            self.client.table("profiles")
            .select("*")
            .eq("user_id", str(user_id))
            .execute()
        )

        if response.data:
            return response.data[0]

        # Create new profile if not exists
        profile_data = {
            "user_id": str(user_id),
            "email": email,
            "display_name": display_name or email,
        }

        response = (
            self.client.table("profiles")
            .insert(profile_data)
            .execute()
        )

        return response.data[0]

    async def get_profile(self, user_id: UUID) -> dict[str, Any] | None:
        """Get a profile by user ID.

        Args:
            user_id: The auth user ID.

        Returns:
            dict | None: The profile data or None if not found.
        """
        response = (
            self.client.table("profiles")
            .select("*")
            .eq("user_id", str(user_id))
            .single()
            .execute()
        )

        return response.data if response.data else None

    async def get_profile_by_id(self, profile_id: UUID) -> dict[str, Any] | None:
        """Get a profile by profile ID.

        Args:
            profile_id: The profile's UUID.

        Returns:
            dict | None: The profile data or None if not found.
        """
        response = (
            self.client.table("profiles")
            .select("*")
            .eq("id", str(profile_id))
            .single()
            .execute()
        )

        return response.data if response.data else None

    async def update_profile(
        self,
        user_id: UUID,
        data: ProfileUpdate,
    ) -> dict[str, Any] | None:
        """Update a profile.

        Args:
            user_id: The auth user ID.
            data: The fields to update.

        Returns:
            dict | None: The updated profile data or None if not found.
        """
        update_data = data.model_dump(exclude_unset=True, exclude_none=True)

        if not update_data:
            # No changes, return current profile
            return await self.get_profile(user_id)

        response = (
            self.client.table("profiles")
            .update(update_data)
            .eq("user_id", str(user_id))
            .execute()
        )

        return response.data[0] if response.data else None

    async def get_user_companies(self, user_id: UUID) -> list[CompanySummary]:
        """Get all companies a user belongs to.

        Args:
            user_id: The auth user ID.

        Returns:
            list[CompanySummary]: List of companies with user's role.
        """
        # First get the user's profile ID
        profile = await self.get_profile(user_id)
        if not profile:
            return []

        profile_id = profile["id"]

        # Get company memberships with company details
        response = (
            self.client.table("company_members")
            .select("role, joined_at, companies(id, name)")
            .eq("profile_id", str(profile_id))
            .execute()
        )

        companies = []
        for membership in response.data or []:
            company_data = membership.get("companies")
            if company_data:
                companies.append(
                    CompanySummary(
                        id=company_data["id"],
                        name=company_data["name"],
                        role=membership["role"],
                        joined_at=membership["joined_at"],
                    )
                )

        return companies

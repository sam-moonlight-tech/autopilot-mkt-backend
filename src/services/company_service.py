"""Company business logic service."""

from typing import Any
from uuid import UUID

from src.api.middleware.error_handler import AuthorizationError, NotFoundError
from src.core.supabase import get_supabase_client
from src.schemas.company import CompanyCreate, CompanyMemberResponse, MemberProfile


class CompanyService:
    """Service for managing companies and their members."""

    def __init__(self) -> None:
        """Initialize company service with Supabase client."""
        self.client = get_supabase_client()

    async def create_company(
        self,
        data: CompanyCreate,
        owner_profile_id: UUID,
    ) -> dict[str, Any]:
        """Create a new company and add owner as member.

        Args:
            data: Company creation data.
            owner_profile_id: Profile ID of the company owner.

        Returns:
            dict: The created company data.
        """
        # Create the company
        company_data = {
            "name": data.name,
            "owner_id": str(owner_profile_id),
        }

        company_response = (
            self.client.table("companies")
            .insert(company_data)
            .execute()
        )

        company = company_response.data[0]

        # Add owner as first member with 'owner' role
        member_data = {
            "company_id": company["id"],
            "profile_id": str(owner_profile_id),
            "role": "owner",
        }

        self.client.table("company_members").insert(member_data).execute()

        return company

    async def get_company(self, company_id: UUID) -> dict[str, Any] | None:
        """Get a company by ID.

        Args:
            company_id: The company's UUID.

        Returns:
            dict | None: The company data or None if not found.
        """
        response = (
            self.client.table("companies")
            .select("*")
            .eq("id", str(company_id))
            .maybe_single()
            .execute()
        )

        return response.data if response and response.data else None

    async def is_member(self, company_id: UUID, profile_id: UUID) -> bool:
        """Check if a profile is a member of a company.

        Args:
            company_id: The company's UUID.
            profile_id: The profile's UUID.

        Returns:
            bool: True if the profile is a member.
        """
        response = (
            self.client.table("company_members")
            .select("id")
            .eq("company_id", str(company_id))
            .eq("profile_id", str(profile_id))
            .execute()
        )

        return len(response.data) > 0

    async def is_owner(self, company_id: UUID, profile_id: UUID) -> bool:
        """Check if a profile is the owner of a company.

        Args:
            company_id: The company's UUID.
            profile_id: The profile's UUID.

        Returns:
            bool: True if the profile is the owner.
        """
        response = (
            self.client.table("companies")
            .select("id")
            .eq("id", str(company_id))
            .eq("owner_id", str(profile_id))
            .execute()
        )

        return len(response.data) > 0

    async def get_member_role(self, company_id: UUID, profile_id: UUID) -> str | None:
        """Get a member's role in a company.

        Args:
            company_id: The company's UUID.
            profile_id: The profile's UUID.

        Returns:
            str | None: The member's role or None if not a member.
        """
        response = (
            self.client.table("company_members")
            .select("role")
            .eq("company_id", str(company_id))
            .eq("profile_id", str(profile_id))
            .maybe_single()
            .execute()
        )

        return response.data["role"] if response.data else None

    async def get_members(self, company_id: UUID) -> list[CompanyMemberResponse]:
        """Get all members of a company with their profiles.

        Args:
            company_id: The company's UUID.

        Returns:
            list[CompanyMemberResponse]: List of company members with profiles.
        """
        response = (
            self.client.table("company_members")
            .select("id, company_id, profile_id, role, joined_at, profiles(id, display_name, email, avatar_url)")
            .eq("company_id", str(company_id))
            .execute()
        )

        members = []
        for row in response.data or []:
            profile_data = row.get("profiles", {})
            members.append(
                CompanyMemberResponse(
                    id=row["id"],
                    company_id=row["company_id"],
                    profile_id=row["profile_id"],
                    role=row["role"],
                    joined_at=row["joined_at"],
                    profile=MemberProfile(
                        id=profile_data.get("id"),
                        display_name=profile_data.get("display_name"),
                        email=profile_data.get("email"),
                        avatar_url=profile_data.get("avatar_url"),
                    ),
                )
            )

        return members

    async def add_member(
        self,
        company_id: UUID,
        profile_id: UUID,
        role: str = "member",
    ) -> dict[str, Any]:
        """Add a member to a company.

        Args:
            company_id: The company's UUID.
            profile_id: The profile's UUID.
            role: The member's role (default: 'member').

        Returns:
            dict: The created membership data.
        """
        member_data = {
            "company_id": str(company_id),
            "profile_id": str(profile_id),
            "role": role,
        }

        response = (
            self.client.table("company_members")
            .insert(member_data)
            .execute()
        )

        return response.data[0]

    async def remove_member(
        self,
        company_id: UUID,
        profile_id: UUID,
        requester_profile_id: UUID,
    ) -> bool:
        """Remove a member from a company.

        Args:
            company_id: The company's UUID.
            profile_id: The profile ID of member to remove.
            requester_profile_id: The profile ID of the requester.

        Returns:
            bool: True if member was removed.

        Raises:
            NotFoundError: If member not found.
            AuthorizationError: If trying to remove owner or not authorized.
        """
        # Check if requester is owner
        if not await self.is_owner(company_id, requester_profile_id):
            raise AuthorizationError("Only company owner can remove members")

        # Prevent removing the owner
        if await self.is_owner(company_id, profile_id):
            raise AuthorizationError("Cannot remove company owner")

        # Check if target is actually a member
        if not await self.is_member(company_id, profile_id):
            raise NotFoundError("Member not found in company")

        # Remove the member
        self.client.table("company_members").delete().eq(
            "company_id", str(company_id)
        ).eq("profile_id", str(profile_id)).execute()

        return True

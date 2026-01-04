"""Invitation business logic service."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from src.api.middleware.error_handler import NotFoundError, ValidationError
from src.core.supabase import get_supabase_client
from src.models.company import InvitationStatus
from src.schemas.company import InvitationCreate


class InvitationService:
    """Service for managing company invitations."""

    DEFAULT_EXPIRATION_DAYS = 7

    def __init__(self) -> None:
        """Initialize invitation service with Supabase client."""
        self.client = get_supabase_client()

    async def create_invitation(
        self,
        company_id: UUID,
        data: InvitationCreate,
        invited_by: UUID,
    ) -> dict[str, Any]:
        """Create a new invitation to join a company.

        Args:
            company_id: The company's UUID.
            data: Invitation creation data with email.
            invited_by: Profile ID of the inviter.

        Returns:
            dict: The created invitation data.
        """
        # Calculate expiration (7 days from now)
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.DEFAULT_EXPIRATION_DAYS)

        invitation_data = {
            "company_id": str(company_id),
            "email": data.email,
            "invited_by": str(invited_by),
            "status": InvitationStatus.PENDING.value,
            "expires_at": expires_at.isoformat(),
        }

        response = (
            self.client.table("invitations")
            .insert(invitation_data)
            .execute()
        )

        return response.data[0]

    async def get_invitation(self, invitation_id: UUID) -> dict[str, Any] | None:
        """Get an invitation by ID.

        Args:
            invitation_id: The invitation's UUID.

        Returns:
            dict | None: The invitation data or None if not found.
        """
        response = (
            self.client.table("invitations")
            .select("*, companies(name)")
            .eq("id", str(invitation_id))
            .single()
            .execute()
        )

        return response.data if response.data else None

    async def list_company_invitations(
        self,
        company_id: UUID,
        status: InvitationStatus | None = None,
    ) -> list[dict[str, Any]]:
        """List all invitations for a company.

        Args:
            company_id: The company's UUID.
            status: Optional filter by invitation status.

        Returns:
            list[dict]: List of invitation data.
        """
        query = (
            self.client.table("invitations")
            .select("*")
            .eq("company_id", str(company_id))
        )

        if status:
            query = query.eq("status", status.value)

        response = query.order("created_at", desc=True).execute()

        return response.data or []

    async def list_user_invitations(self, email: str) -> list[dict[str, Any]]:
        """List all pending invitations for a user's email.

        Args:
            email: The user's email address.

        Returns:
            list[dict]: List of pending invitation data with company names.
        """
        response = (
            self.client.table("invitations")
            .select("*, companies(name)")
            .eq("email", email)
            .eq("status", InvitationStatus.PENDING.value)
            .order("created_at", desc=True)
            .execute()
        )

        return response.data or []

    async def accept_invitation(
        self,
        invitation_id: UUID,
        profile_id: UUID,
        user_email: str,
    ) -> dict[str, Any]:
        """Accept an invitation and join the company.

        Args:
            invitation_id: The invitation's UUID.
            profile_id: The profile ID of the accepting user.
            user_email: The email of the accepting user.

        Returns:
            dict: The updated invitation data.

        Raises:
            NotFoundError: If invitation not found.
            ValidationError: If invitation expired, already used, or email mismatch.
        """
        # Get the invitation
        invitation = await self.get_invitation(invitation_id)

        if not invitation:
            raise NotFoundError("Invitation not found")

        # Check email matches
        if invitation["email"].lower() != user_email.lower():
            raise ValidationError("This invitation is for a different email address")

        # Check if already accepted
        if invitation["status"] != InvitationStatus.PENDING.value:
            raise ValidationError(f"Invitation has already been {invitation['status']}")

        # Check expiration
        expires_at = datetime.fromisoformat(invitation["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires_at:
            # Update status to expired
            self.client.table("invitations").update(
                {"status": InvitationStatus.EXPIRED.value}
            ).eq("id", str(invitation_id)).execute()

            raise ValidationError("Invitation has expired")

        # Check if user is already a member
        company_id = invitation["company_id"]
        existing_member = (
            self.client.table("company_members")
            .select("id")
            .eq("company_id", str(company_id))
            .eq("profile_id", str(profile_id))
            .execute()
        )

        if existing_member.data:
            raise ValidationError("You are already a member of this company")

        # Add user as member
        member_data = {
            "company_id": str(company_id),
            "profile_id": str(profile_id),
            "role": "member",
        }
        self.client.table("company_members").insert(member_data).execute()

        # Update invitation status
        now = datetime.now(timezone.utc)
        response = (
            self.client.table("invitations")
            .update({
                "status": InvitationStatus.ACCEPTED.value,
                "accepted_at": now.isoformat(),
            })
            .eq("id", str(invitation_id))
            .execute()
        )

        return response.data[0]

    async def decline_invitation(self, invitation_id: UUID, user_email: str) -> dict[str, Any]:
        """Decline an invitation.

        Args:
            invitation_id: The invitation's UUID.
            user_email: The email of the declining user.

        Returns:
            dict: The updated invitation data.

        Raises:
            NotFoundError: If invitation not found.
            ValidationError: If invitation is not pending or email mismatch.
        """
        invitation = await self.get_invitation(invitation_id)

        if not invitation:
            raise NotFoundError("Invitation not found")

        if invitation["email"].lower() != user_email.lower():
            raise ValidationError("This invitation is for a different email address")

        if invitation["status"] != InvitationStatus.PENDING.value:
            raise ValidationError(f"Invitation has already been {invitation['status']}")

        response = (
            self.client.table("invitations")
            .update({"status": InvitationStatus.DECLINED.value})
            .eq("id", str(invitation_id))
            .execute()
        )

        return response.data[0]

"""Invitation API routes for accepting/declining invitations."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.api.deps import CurrentUser
from src.schemas.company import InvitationResponse, InvitationWithCompany
from src.services.invitation_service import InvitationService
from src.services.profile_service import ProfileService

router = APIRouter(prefix="/invitations", tags=["invitations"])


async def _get_user_profile_id(user: CurrentUser) -> UUID:
    """Get the profile ID for a user, creating profile if needed."""
    service = ProfileService()
    profile = await service.get_or_create_profile(user.user_id, user.email)
    return UUID(profile["id"])


@router.get(
    "",
    response_model=list[InvitationWithCompany],
    summary="List my invitations",
    description="Returns all pending invitations for the authenticated user's email.",
)
async def list_my_invitations(user: CurrentUser) -> list[InvitationWithCompany]:
    """List all pending invitations for the current user.

    Args:
        user: The authenticated user context.

    Returns:
        list[InvitationWithCompany]: List of pending invitations with company info.
    """
    if not user.email:
        return []

    service = InvitationService()
    invitations = await service.list_user_invitations(user.email)

    result = []
    for inv in invitations:
        company_data = inv.get("companies", {})
        result.append(
            InvitationWithCompany(
                id=inv["id"],
                company_id=inv["company_id"],
                email=inv["email"],
                invited_by=inv["invited_by"],
                status=inv["status"],
                expires_at=inv["expires_at"],
                created_at=inv["created_at"],
                accepted_at=inv.get("accepted_at"),
                company_name=company_data.get("name", "Unknown"),
            )
        )

    return result


@router.post(
    "/{invitation_id}/accept",
    response_model=InvitationResponse,
    summary="Accept invitation",
    description="Accepts an invitation and joins the company.",
)
async def accept_invitation(
    invitation_id: UUID,
    user: CurrentUser,
) -> InvitationResponse:
    """Accept an invitation to join a company.

    Args:
        invitation_id: The invitation's UUID.
        user: The authenticated user context.

    Returns:
        InvitationResponse: The updated invitation.

    Raises:
        HTTPException: 400 if invitation invalid/expired, 404 if not found.
    """
    if not user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address required to accept invitation",
        )

    profile_id = await _get_user_profile_id(user)
    service = InvitationService()

    invitation = await service.accept_invitation(invitation_id, profile_id, user.email)
    return InvitationResponse(**invitation)


@router.post(
    "/{invitation_id}/decline",
    response_model=InvitationResponse,
    summary="Decline invitation",
    description="Declines an invitation.",
)
async def decline_invitation(
    invitation_id: UUID,
    user: CurrentUser,
) -> InvitationResponse:
    """Decline an invitation to join a company.

    Args:
        invitation_id: The invitation's UUID.
        user: The authenticated user context.

    Returns:
        InvitationResponse: The updated invitation.

    Raises:
        HTTPException: 400 if invitation not pending, 404 if not found.
    """
    if not user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address required to decline invitation",
        )

    service = InvitationService()
    invitation = await service.decline_invitation(invitation_id, user.email)
    return InvitationResponse(**invitation)

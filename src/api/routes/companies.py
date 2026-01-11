"""Company API routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.api.deps import CurrentUser
from src.schemas.company import (
    CompanyCreate,
    CompanyMemberResponse,
    CompanyResponse,
    InvitationCreate,
    InvitationResponse,
)
from src.services.company_service import CompanyService
from src.services.invitation_service import InvitationService
from src.services.profile_service import ProfileService

router = APIRouter(prefix="/companies", tags=["companies"])


async def _get_user_profile_id(user: CurrentUser) -> UUID:
    """Get the profile ID for a user, creating profile if needed."""
    service = ProfileService()
    profile = await service.get_or_create_profile(user.user_id, user.email)
    return UUID(profile["id"])


async def _check_member_access(company_id: UUID, profile_id: UUID) -> None:
    """Check if user is a member of the company."""
    service = CompanyService()
    if not await service.is_member(company_id, profile_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this company",
        )


async def _check_owner_access(company_id: UUID, profile_id: UUID) -> None:
    """Check if user is the owner of the company."""
    service = CompanyService()
    if not await service.is_owner(company_id, profile_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the company owner can perform this action",
        )


@router.post(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a company",
    description="Creates a new company with the authenticated user as owner.",
)
async def create_company(
    data: CompanyCreate,
    user: CurrentUser,
) -> CompanyResponse:
    """Create a new company.

    The authenticated user becomes the owner and first member.

    Args:
        data: Company creation data.
        user: The authenticated user context.

    Returns:
        CompanyResponse: The created company.
    """
    profile_id = await _get_user_profile_id(user)
    service = CompanyService()
    company = await service.create_company(data, profile_id)
    return CompanyResponse(**company)


@router.get(
    "/me",
    response_model=CompanyResponse,
    summary="Get current user's company",
    description="Returns the company the authenticated user belongs to.",
)
async def get_my_company(
    user: CurrentUser,
) -> CompanyResponse:
    """Get the current user's company.

    Returns the company the user is a member of.
    If user belongs to multiple companies, returns the first one.

    Args:
        user: The authenticated user context.

    Returns:
        CompanyResponse: The user's company.

    Raises:
        HTTPException: 404 if user has no company.
    """
    profile_id = await _get_user_profile_id(user)
    service = CompanyService()
    company = await service.get_user_company(profile_id)

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No company found for this user",
        )

    return CompanyResponse(**company)


@router.get(
    "/{company_id}",
    response_model=CompanyResponse,
    summary="Get company details",
    description="Returns company details. Only accessible to company members.",
)
async def get_company(
    company_id: UUID,
    user: CurrentUser,
) -> CompanyResponse:
    """Get company details.

    Args:
        company_id: The company's UUID.
        user: The authenticated user context.

    Returns:
        CompanyResponse: The company details.

    Raises:
        HTTPException: 404 if not found, 403 if not a member.
    """
    profile_id = await _get_user_profile_id(user)
    service = CompanyService()

    company = await service.get_company(company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    await _check_member_access(company_id, profile_id)

    return CompanyResponse(**company)


@router.get(
    "/{company_id}/members",
    response_model=list[CompanyMemberResponse],
    summary="List company members",
    description="Returns all members of a company. Only accessible to company members.",
)
async def list_company_members(
    company_id: UUID,
    user: CurrentUser,
) -> list[CompanyMemberResponse]:
    """List all members of a company.

    Args:
        company_id: The company's UUID.
        user: The authenticated user context.

    Returns:
        list[CompanyMemberResponse]: List of company members with profiles.

    Raises:
        HTTPException: 403 if not a member.
    """
    profile_id = await _get_user_profile_id(user)
    await _check_member_access(company_id, profile_id)

    service = CompanyService()
    return await service.get_members(company_id)


@router.delete(
    "/{company_id}/members/{member_profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove company member",
    description="Removes a member from the company. Only the owner can remove members.",
)
async def remove_company_member(
    company_id: UUID,
    member_profile_id: UUID,
    user: CurrentUser,
) -> None:
    """Remove a member from a company.

    Args:
        company_id: The company's UUID.
        member_profile_id: The profile ID of the member to remove.
        user: The authenticated user context.

    Raises:
        HTTPException: 403 if not owner, 404 if member not found.
    """
    profile_id = await _get_user_profile_id(user)
    service = CompanyService()

    await service.remove_member(company_id, member_profile_id, profile_id)


# Invitation endpoints


@router.post(
    "/{company_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create invitation",
    description="Invites a user by email to join the company. Only the owner can create invitations.",
)
async def create_invitation(
    company_id: UUID,
    data: InvitationCreate,
    user: CurrentUser,
) -> InvitationResponse:
    """Create an invitation to join the company.

    Args:
        company_id: The company's UUID.
        data: Invitation data with email.
        user: The authenticated user context.

    Returns:
        InvitationResponse: The created invitation.

    Raises:
        HTTPException: 403 if not owner.
    """
    profile_id = await _get_user_profile_id(user)
    await _check_owner_access(company_id, profile_id)

    service = InvitationService()
    invitation = await service.create_invitation(company_id, data, profile_id)
    return InvitationResponse(**invitation)


@router.get(
    "/{company_id}/invitations",
    response_model=list[InvitationResponse],
    summary="List company invitations",
    description="Returns all invitations for a company. Only accessible to company members.",
)
async def list_invitations(
    company_id: UUID,
    user: CurrentUser,
) -> list[InvitationResponse]:
    """List all invitations for a company.

    Args:
        company_id: The company's UUID.
        user: The authenticated user context.

    Returns:
        list[InvitationResponse]: List of invitations.

    Raises:
        HTTPException: 403 if not a member.
    """
    profile_id = await _get_user_profile_id(user)
    await _check_member_access(company_id, profile_id)

    service = InvitationService()
    invitations = await service.list_company_invitations(company_id)
    return [InvitationResponse(**inv) for inv in invitations]

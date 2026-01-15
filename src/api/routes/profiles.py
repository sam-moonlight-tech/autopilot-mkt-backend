"""Profile API routes."""

from fastapi import APIRouter, HTTPException, status

from src.api.deps import CurrentUser
from src.schemas.profile import (
    CompanySummary,
    ProfileResponse,
    ProfileUpdate,
    SetTestAccountRequest,
)
from src.services.profile_service import ProfileService

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get(
    "/me",
    response_model=ProfileResponse,
    summary="Get current user's profile",
    description="Returns the authenticated user's profile information.",
)
async def get_my_profile(user: CurrentUser) -> ProfileResponse:
    """Get the authenticated user's profile.

    Args:
        user: The authenticated user context.

    Returns:
        ProfileResponse: The user's profile data.

    Raises:
        HTTPException: 404 if profile not found.
    """
    service = ProfileService()
    profile = await service.get_or_create_profile(
        user_id=user.user_id,
        email=user.email,
    )

    return ProfileResponse(**profile)


@router.put(
    "/me",
    response_model=ProfileResponse,
    summary="Update current user's profile",
    description="Updates the authenticated user's profile with provided fields.",
)
async def update_my_profile(
    data: ProfileUpdate,
    user: CurrentUser,
) -> ProfileResponse:
    """Update the authenticated user's profile.

    Args:
        data: Fields to update.
        user: The authenticated user context.

    Returns:
        ProfileResponse: The updated profile data.

    Raises:
        HTTPException: 404 if profile not found.
    """
    service = ProfileService()

    # Ensure profile exists
    await service.get_or_create_profile(user_id=user.user_id, email=user.email)

    # Update profile
    profile = await service.update_profile(user.user_id, data)

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    return ProfileResponse(**profile)


@router.get(
    "/me/companies",
    response_model=list[CompanySummary],
    summary="Get user's companies",
    description="Returns all companies the authenticated user belongs to.",
)
async def get_my_companies(user: CurrentUser) -> list[CompanySummary]:
    """Get all companies the authenticated user belongs to.

    Args:
        user: The authenticated user context.

    Returns:
        list[CompanySummary]: List of companies with user's role.
    """
    service = ProfileService()
    return await service.get_user_companies(user.user_id)


@router.post(
    "/me/test-account",
    response_model=ProfileResponse,
    summary="Set test account mode",
    description="Enable or disable Stripe test mode for this account. When enabled, checkout uses Stripe test keys.",
)
async def set_test_account(
    data: SetTestAccountRequest,
    user: CurrentUser,
) -> ProfileResponse:
    """Enable or disable test account mode.

    Test accounts use Stripe test mode for checkout, even in production.
    This allows testing the full checkout flow without real charges.

    Args:
        data: Request with is_test_account flag.
        user: The authenticated user context.

    Returns:
        ProfileResponse: The updated profile data.

    Raises:
        HTTPException: 404 if profile not found.
    """
    service = ProfileService()

    # Get the profile
    profile = await service.get_or_create_profile(user_id=user.user_id, email=user.email)

    # Update test account flag
    updated = await service.set_test_account(
        profile_id=profile["id"],
        is_test_account=data.is_test_account,
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found",
        )

    return ProfileResponse(**updated)

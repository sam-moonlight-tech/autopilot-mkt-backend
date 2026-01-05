"""Discovery profile API routes for authenticated users."""

from fastapi import APIRouter, HTTPException, status

from src.api.deps import CurrentUser
from src.schemas.discovery import DiscoveryProfileResponse, DiscoveryProfileUpdate
from src.services.discovery_profile_service import DiscoveryProfileService
from src.services.profile_service import ProfileService

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get(
    "",
    response_model=DiscoveryProfileResponse,
    summary="Get discovery profile",
    description="Returns the authenticated user's discovery profile. Creates one if it doesn't exist.",
)
async def get_discovery_profile(user: CurrentUser) -> DiscoveryProfileResponse:
    """Get the authenticated user's discovery profile.

    This endpoint returns the user's discovery progress including
    answers, ROI inputs, and product selections. If no profile exists,
    one is created automatically.

    Args:
        user: The authenticated user context.

    Returns:
        DiscoveryProfileResponse: The discovery profile data.
    """
    profile_service = ProfileService()
    discovery_service = DiscoveryProfileService()

    # Get or create the user's profile first
    profile = await profile_service.get_or_create_profile(
        user_id=user.user_id,
        email=user.email,
    )

    # Get or create discovery profile
    discovery_profile = await discovery_service.get_or_create(profile["id"])

    return DiscoveryProfileResponse(**discovery_profile)


@router.put(
    "",
    response_model=DiscoveryProfileResponse,
    summary="Update discovery profile",
    description="Updates the authenticated user's discovery profile with provided fields.",
)
async def update_discovery_profile(
    data: DiscoveryProfileUpdate,
    user: CurrentUser,
) -> DiscoveryProfileResponse:
    """Update the authenticated user's discovery profile.

    Updates fields like current question index, phase, answers,
    ROI inputs, and product selections.

    Args:
        data: Fields to update.
        user: The authenticated user context.

    Returns:
        DiscoveryProfileResponse: The updated discovery profile data.

    Raises:
        HTTPException: 404 if discovery profile not found.
    """
    profile_service = ProfileService()
    discovery_service = DiscoveryProfileService()

    # Get or create the user's profile first
    profile = await profile_service.get_or_create_profile(
        user_id=user.user_id,
        email=user.email,
    )

    # Ensure discovery profile exists
    await discovery_service.get_or_create(profile["id"])

    # Update discovery profile
    discovery_profile = await discovery_service.update(profile["id"], data)

    if not discovery_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discovery profile not found",
        )

    return DiscoveryProfileResponse(**discovery_profile)

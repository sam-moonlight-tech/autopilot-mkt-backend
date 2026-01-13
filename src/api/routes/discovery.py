"""Discovery profile API routes for authenticated users."""

from fastapi import APIRouter, HTTPException, status

from src.api.deps import CurrentUser
from src.schemas.discovery import DiscoveryProfileResponse, DiscoveryProfileUpdate
from src.services.company_service import CompanyService
from src.services.discovery_profile_service import DiscoveryProfileService
from src.services.extraction_constants import REQUIRED_QUESTION_KEYS
from src.services.profile_service import ProfileService

router = APIRouter(prefix="/discovery", tags=["discovery"])

# Minimum required questions answered to be ready for ROI (4 of 6)
MIN_QUESTIONS_FOR_ROI = 4


def compute_ready_for_roi(answers: dict, has_company: bool = False) -> bool:
    """Compute whether discovery has enough answers for ROI analysis.

    Args:
        answers: Discovery answers dict keyed by question key.
        has_company: If True, company_name is considered answered (from user's company).

    Returns:
        True if 4+ of the 6 required questions are answered.
    """
    answered_required = sum(1 for key in REQUIRED_QUESTION_KEYS if key in answers)

    # If user has a company, count company_name as answered (if not already)
    if has_company and "company_name" not in answers:
        answered_required += 1

    return answered_required >= MIN_QUESTIONS_FOR_ROI


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

    # Check if user has a company (company_name can be derived from it)
    company_service = CompanyService()
    company = await company_service.get_user_company(profile["id"])
    has_company = company is not None and company.get("name")

    # Compute ready_for_roi based on answered required questions
    ready_for_roi = compute_ready_for_roi(discovery_profile.get("answers", {}), has_company=has_company)

    return DiscoveryProfileResponse(**discovery_profile, ready_for_roi=ready_for_roi)


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

    # Check if user has a company (company_name can be derived from it)
    company_service = CompanyService()
    company = await company_service.get_user_company(profile["id"])
    has_company = company is not None and company.get("name")

    # Compute ready_for_roi based on answered required questions
    ready_for_roi = compute_ready_for_roi(discovery_profile.get("answers", {}), has_company=has_company)

    return DiscoveryProfileResponse(**discovery_profile, ready_for_roi=ready_for_roi)

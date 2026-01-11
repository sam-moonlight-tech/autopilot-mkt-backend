"""ROI and Recommendations API routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import CurrentUser, DualAuth
from src.schemas.roi import (
    GreenlightConfirmRequest,
    GreenlightConfirmResponse,
    GreenlightValidationRequest,
    GreenlightValidationResponse,
    RecommendationsRequest,
    RecommendationsResponse,
    ROICalculationRequest,
    ROICalculationResponse,
)
from src.services.robot_catalog_service import RobotCatalogService
from src.services.roi_service import get_roi_service
from src.services.session_service import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/roi", tags=["roi"])


@router.post(
    "/calculate",
    response_model=ROICalculationResponse,
    summary="Calculate ROI for a specific robot",
    description="Calculates projected ROI and savings for a specific robot based on discovery answers.",
)
async def calculate_roi(
    request: ROICalculationRequest,
    auth: DualAuth,
) -> ROICalculationResponse:
    """Calculate ROI for a specific robot.

    Uses discovery answers and optional ROI inputs to project
    savings and return on investment for the specified robot.

    Args:
        request: ROI calculation request with robot_id and answers.
        auth: Dual auth context (user or session).

    Returns:
        ROICalculationResponse with detailed ROI projections.

    Raises:
        HTTPException: 404 if robot not found.
    """
    roi_service = get_roi_service()

    try:
        result = await roi_service.calculate_roi_for_robot(request)
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/recommendations",
    response_model=RecommendationsResponse,
    summary="Get robot recommendations",
    description="Returns ranked robot recommendations based on discovery answers and business needs.",
)
async def get_recommendations(
    request: RecommendationsRequest,
    auth: DualAuth,
) -> RecommendationsResponse:
    """Get ranked robot recommendations.

    Analyzes discovery answers to score and rank robots,
    returning the top matches with ROI projections and reasoning.

    Args:
        request: Recommendations request with answers and preferences.
        auth: Dual auth context (user or session).

    Returns:
        RecommendationsResponse with ranked recommendations.
    """
    roi_service = get_roi_service()

    try:
        result = await roi_service.get_recommendations(request)
        return result

    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate recommendations",
        ) from e


@router.post(
    "/recommendations/session",
    response_model=RecommendationsResponse,
    summary="Get recommendations using session data",
    description="Returns robot recommendations using the current session's discovery answers.",
)
async def get_recommendations_from_session(
    auth: DualAuth,
    top_k: int = Query(default=3, ge=1, le=50, description="Number of recommendations to return"),
) -> RecommendationsResponse:
    """Get recommendations using current session data.

    Convenience endpoint that uses the session's stored answers
    to generate recommendations without requiring the caller
    to pass answers explicitly.

    Args:
        auth: Dual auth context (user or session).
        top_k: Number of recommendations to return.

    Returns:
        RecommendationsResponse with ranked recommendations.

    Raises:
        HTTPException: 404 if session not found or no answers available.
    """
    if auth.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /discovery endpoint for authenticated users",
        )

    if not auth.session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No session found",
        )

    # Get session data
    session_service = SessionService()
    session = await session_service.get_session_by_id(auth.session.session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    answers = session.get("answers", {})
    if not answers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No discovery answers in session. Complete discovery first.",
        )

    # Build request from session data
    try:
        request = RecommendationsRequest(
            answers=answers,
            roi_inputs=None,  # Will be derived from answers
            top_k=top_k,
        )
    except Exception as e:
        logger.error(f"Error building RecommendationsRequest: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid session data format: {str(e)}",
        ) from e

    roi_service = get_roi_service()
    try:
        result = await roi_service.get_recommendations(request)
        return result
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}",
        ) from e


@router.post(
    "/recommendations/discovery",
    response_model=RecommendationsResponse,
    summary="Get recommendations using discovery profile data",
    description="Returns robot recommendations using the authenticated user's discovery profile answers.",
)
async def get_recommendations_from_discovery(
    user: CurrentUser,
    top_k: int = Query(default=3, ge=1, le=50, description="Number of recommendations to return"),
) -> RecommendationsResponse:
    """Get recommendations using current discovery profile data.

    Authenticated-user endpoint that uses the discovery profile's stored answers
    to generate recommendations without requiring the caller
    to pass answers explicitly.

    Args:
        user: Authenticated user context.
        top_k: Number of recommendations to return.

    Returns:
        RecommendationsResponse with ranked recommendations.

    Raises:
        HTTPException: 404 if profile not found or no answers available.
    """
    from src.services.discovery_profile_service import DiscoveryProfileService
    from src.services.profile_service import ProfileService

    # Get user's profile ID
    profile_service = ProfileService()
    profile = await profile_service.get_or_create_profile(user.user_id, user.email)
    profile_id = UUID(profile["id"])

    # Get discovery profile
    discovery_service = DiscoveryProfileService()
    discovery_profile = await discovery_service.get_by_profile_id(profile_id)

    if not discovery_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Discovery profile not found",
        )

    answers = discovery_profile.get("answers", {})
    if not answers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No discovery answers in profile. Complete discovery first.",
        )

    # Build request from discovery profile data
    try:
        request = RecommendationsRequest(
            answers=answers,
            roi_inputs=None,  # Will be derived from answers
            top_k=top_k,
        )
    except Exception as e:
        logger.error(f"Error building RecommendationsRequest: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid discovery profile data format: {str(e)}",
        ) from e

    roi_service = get_roi_service()
    try:
        result = await roi_service.get_recommendations(request)
        return result
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}",
        ) from e


# Greenlight routes

greenlight_router = APIRouter(prefix="/greenlight", tags=["greenlight"])


@greenlight_router.post(
    "/validate",
    response_model=GreenlightValidationResponse,
    summary="Validate greenlight data",
    description="Validates greenlight phase selections before confirmation.",
)
async def validate_greenlight(
    request: GreenlightValidationRequest,
    auth: DualAuth,
) -> GreenlightValidationResponse:
    """Validate greenlight phase data.

    Checks that the selected robot is available, team members
    are valid, and all required data is present before proceeding
    to checkout.

    Args:
        request: Greenlight validation request.
        auth: Dual auth context.

    Returns:
        GreenlightValidationResponse with validation results.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Validate robot exists and is available
    robot_catalog = RobotCatalogService()
    robot = await robot_catalog.get_robot(request.selected_robot_id)

    robot_available = True
    if not robot:
        errors.append("Selected robot not found")
        robot_available = False
    elif not robot.get("active", True):
        errors.append("Selected robot is no longer available")
        robot_available = False

    # Validate team members if provided
    for i, member in enumerate(request.team_members):
        if not member.get("email"):
            errors.append(f"Team member {i + 1} is missing email")
        if not member.get("name"):
            warnings.append(f"Team member {i + 1} has no name specified")

    # Validate payment method
    if not request.payment_method:
        warnings.append("No payment method selected")

    # Validate start date if provided
    estimated_delivery = None
    if request.target_start_date:
        # In a real implementation, check availability and calculate delivery
        estimated_delivery = request.target_start_date
    else:
        warnings.append("No target start date specified")

    return GreenlightValidationResponse(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        robot_available=robot_available,
        estimated_delivery=estimated_delivery,
    )


@greenlight_router.post(
    "/confirm",
    response_model=GreenlightConfirmResponse,
    summary="Confirm greenlight and prepare checkout",
    description="Confirms greenlight selections and prepares for checkout.",
)
async def confirm_greenlight(
    request: GreenlightConfirmRequest,
    auth: DualAuth,
) -> GreenlightConfirmResponse:
    """Confirm greenlight and prepare for checkout.

    Validates all greenlight data, creates an order intent,
    and returns the next step (usually checkout URL).

    Args:
        request: Greenlight confirmation request.
        auth: Dual auth context.

    Returns:
        GreenlightConfirmResponse with checkout URL or next steps.

    Raises:
        HTTPException: 400 if validation fails.
    """
    # First validate
    validation_request = GreenlightValidationRequest(
        selected_robot_id=request.selected_robot_id,
        target_start_date=request.target_start_date,
        team_members=request.team_members,
        payment_method=request.payment_method,
    )

    validation = await validate_greenlight(validation_request, auth)

    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation failed: {'; '.join(validation.errors)}",
        )

    # Get robot for checkout
    robot_catalog = RobotCatalogService()
    robot = await robot_catalog.get_robot_with_stripe_ids(request.selected_robot_id)

    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Robot not found",
        )

    # Check if robot has Stripe integration
    if not robot.get("stripe_product_id") or not robot.get("stripe_lease_price_id"):
        # Robot doesn't have Stripe setup - need to contact sales
        return GreenlightConfirmResponse(
            success=True,
            order_intent_id=None,
            message="This robot requires a custom quote. Our team will contact you.",
            next_step="contact_sales",
            checkout_url=None,
        )

    # Update session with greenlight data
    if not auth.is_authenticated and auth.session:
        session_service = SessionService()
        await session_service.update_session(
            auth.session.session_id,
            {
                "phase": "greenlight",
                "selected_product_ids": [str(request.selected_robot_id)],
                "greenlight": {
                    "target_start_date": request.target_start_date,
                    "team_members": request.team_members,
                    "payment_method": request.payment_method,
                },
            },
        )

    # Return checkout as next step
    # The frontend will call /checkout/create-session with this info
    return GreenlightConfirmResponse(
        success=True,
        order_intent_id=None,  # Created during actual checkout
        message="Ready for checkout",
        next_step="checkout",
        checkout_url=None,  # Frontend will construct this
    )


# Combined router for main.py
roi_router = APIRouter()
roi_router.include_router(router)
roi_router.include_router(greenlight_router)

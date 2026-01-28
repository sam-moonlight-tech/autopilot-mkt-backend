"""Floor plan analysis API routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from src.api.deps import DualAuth, RequiredDualAuth
from src.core.token_budget import TokenBudgetError
from src.schemas.floor_plan import (
    FloorPlanAnalysisResponse,
    FloorPlanListResponse,
    FloorPlanWithRecommendationsResponse,
)
from src.services.floor_plan_service import (
    FloorPlanServiceError,
    FloorPlanUploadError,
    get_floor_plan_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/floor-plans", tags=["floor-plans"])


@router.post(
    "/analyze",
    response_model=FloorPlanWithRecommendationsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and analyze a floor plan",
    responses={
        201: {"description": "Floor plan analyzed successfully"},
        400: {"description": "Invalid file type or file too large"},
        429: {"description": "Token budget exceeded"},
        500: {"description": "Analysis failed"},
    },
)
async def analyze_floor_plan(
    file: UploadFile = File(
        ...,
        description="Floor plan image (PNG or JPG, max 10MB)",
    ),
    auth: RequiredDualAuth = None,
) -> FloorPlanWithRecommendationsResponse:
    """Upload a floor plan image and analyze it for robotic cleaning cost estimation.

    This endpoint:
    1. Validates and stores the uploaded image
    2. Analyzes the floor plan using GPT-4o Vision to extract:
       - Court count and dimensions
       - Zone classification (courts, circulation, auxiliary, excluded)
       - Surface types
       - Obstructions
    3. Calculates cleaning costs based on extracted features
    4. Updates the user's discovery profile with extracted data (if authenticated)
    5. Returns robot recommendations based on the analysis

    The analysis runs synchronously and typically takes 10-20 seconds.

    **Supported formats:** PNG, JPG/JPEG
    **Maximum file size:** 10 MB
    """
    service = get_floor_plan_service()

    # Extract user_id (used as profile_id) and session_id from auth
    # In Supabase, profile_id equals user_id since profiles are 1:1 with users
    profile_id = auth.user_id if auth else None
    session_id = auth.session_id if auth else None

    try:
        result = await service.upload_and_analyze(
            file=file,
            profile_id=profile_id,
            session_id=session_id,
        )
        return result

    except FloorPlanUploadError as e:
        logger.warning("Floor plan upload failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    except TokenBudgetError as e:
        logger.warning("Token budget exceeded for floor plan analysis: %s", e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": "86400"},  # 24 hours
        ) from e

    except FloorPlanServiceError as e:
        logger.error("Floor plan analysis failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {e}",
        ) from e


@router.get(
    "",
    response_model=FloorPlanListResponse,
    summary="List floor plan analyses",
)
async def list_floor_plans(
    auth: RequiredDualAuth = None,
) -> FloorPlanListResponse:
    """List all floor plan analyses for the current user/session.

    Returns analyses ordered by creation date (newest first).
    """
    service = get_floor_plan_service()

    profile_id = auth.user_id if auth else None
    session_id = auth.session_id if auth else None

    analyses = await service.list_analyses(
        profile_id=profile_id,
        session_id=session_id,
    )

    return FloorPlanListResponse(
        analyses=analyses,
        total=len(analyses),
    )


@router.get(
    "/{analysis_id}",
    response_model=FloorPlanAnalysisResponse,
    summary="Get floor plan analysis",
    responses={
        200: {"description": "Analysis found"},
        404: {"description": "Analysis not found"},
    },
)
async def get_floor_plan_analysis(
    analysis_id: UUID,
    auth: RequiredDualAuth = None,
) -> FloorPlanAnalysisResponse:
    """Get a specific floor plan analysis by ID.

    Only returns the analysis if it belongs to the current user/session.
    """
    service = get_floor_plan_service()

    profile_id = auth.user_id if auth else None
    session_id = auth.session_id if auth else None

    analysis = await service.get_analysis(
        analysis_id=analysis_id,
        profile_id=profile_id,
        session_id=session_id,
    )

    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Floor plan analysis not found",
        )

    return analysis


@router.delete(
    "/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete floor plan analysis",
    responses={
        204: {"description": "Analysis deleted"},
        404: {"description": "Analysis not found"},
    },
)
async def delete_floor_plan_analysis(
    analysis_id: UUID,
    auth: RequiredDualAuth = None,
) -> None:
    """Delete a floor plan analysis and its associated storage.

    Only deletes if the analysis belongs to the current user/session.
    """
    service = get_floor_plan_service()

    profile_id = auth.user_id if auth else None
    session_id = auth.session_id if auth else None

    deleted = await service.delete_analysis(
        analysis_id=analysis_id,
        profile_id=profile_id,
        session_id=session_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Floor plan analysis not found",
        )

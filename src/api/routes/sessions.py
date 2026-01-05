"""Session API routes for anonymous user session management."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response, status

from src.api.deps import (
    AuthContext,
    CurrentUser,
    DualAuth,
    clear_session_cookie,
    get_session_cookie,
    set_session_cookie,
)
from src.schemas.session import SessionClaimResponse, SessionResponse, SessionUpdate
from src.services.checkout_service import CheckoutService
from src.services.profile_service import ProfileService
from src.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new session",
    description="Creates a new anonymous session and sets the session cookie.",
)
async def create_session(response: Response) -> SessionResponse:
    """Create a new anonymous session.

    This endpoint creates a fresh session, even if one already exists.
    The session cookie is set automatically.

    Args:
        response: FastAPI response object for setting cookie.

    Returns:
        SessionResponse: The created session data.
    """
    service = SessionService()
    session_data, token = await service.create_session()

    set_session_cookie(response, token)

    return SessionResponse(**session_data)


@router.get(
    "/me",
    response_model=SessionResponse,
    summary="Get current session",
    description="Returns the current session data. Creates a new session if none exists.",
)
async def get_my_session(auth: DualAuth) -> SessionResponse:
    """Get the current session.

    If the user is authenticated (JWT), returns 400 since they don't have a session.
    If anonymous, returns the session data.

    Args:
        auth: Dual auth context (user or session).

    Returns:
        SessionResponse: The session data.

    Raises:
        HTTPException: 400 if user is authenticated (no session for authenticated users).
    """
    if auth.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated users don't have sessions. Use /discovery instead.",
        )

    if not auth.session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No session found",
        )

    service = SessionService()
    session = await service.get_session_by_id(auth.session.session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionResponse(**session)


@router.put(
    "/me",
    response_model=SessionResponse,
    summary="Update current session",
    description="Updates the current session with discovery progress data.",
)
async def update_my_session(
    data: SessionUpdate,
    auth: DualAuth,
) -> SessionResponse:
    """Update the current session.

    Updates session fields like answers, ROI inputs, and selections.

    Args:
        data: Fields to update.
        auth: Dual auth context.

    Returns:
        SessionResponse: The updated session data.

    Raises:
        HTTPException: 400 if user is authenticated.
        HTTPException: 404 if session not found.
    """
    if auth.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated users don't have sessions. Use /discovery instead.",
        )

    if not auth.session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No session found",
        )

    service = SessionService()
    session = await service.update_session(auth.session.session_id, data)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    return SessionResponse(**session)


@router.post(
    "/claim",
    response_model=SessionClaimResponse,
    summary="Claim session for authenticated user",
    description="Transfers session data to the authenticated user's profile.",
)
async def claim_session(
    request: Request,
    response: Response,
    user: CurrentUser,
) -> SessionClaimResponse:
    """Claim a session and transfer data to user profile.

    This endpoint requires both JWT authentication AND a valid session cookie.
    It transfers all session data (answers, ROI inputs, selections) to the
    user's discovery profile and transfers any conversation ownership.

    Args:
        request: FastAPI request object for reading cookie.
        response: FastAPI response object for clearing cookie.
        user: The authenticated user context (from JWT).

    Returns:
        SessionClaimResponse: Result of the claim operation.

    Raises:
        HTTPException: 400 if no session cookie or already claimed.
        HTTPException: 404 if session not found.
    """
    # Get session from cookie
    session_token = get_session_cookie(request)
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No session cookie found. Nothing to claim.",
        )

    checkout_service = CheckoutService()
    session_service = SessionService(checkout_service=checkout_service)
    profile_service = ProfileService()

    # Get the session
    session = await session_service.get_session_by_token(session_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Get user's profile
    profile = await profile_service.get_or_create_profile(
        user_id=user.user_id,
        email=user.email,
    )

    try:
        # Claim the session (transfers discovery data, conversation, and orders)
        result = await session_service.claim_session(
            session_id=UUID(session["id"]),
            profile_id=UUID(profile["id"]),
        )

        # Clear the session cookie
        clear_session_cookie(response)

        return SessionClaimResponse(
            message="Session claimed successfully",
            discovery_profile_id=UUID(result["discovery_profile"]["id"]),
            conversation_transferred=result["conversation_transferred"],
            orders_transferred=result["orders_transferred"],
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

"""FastAPI dependency injection functions."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status

from src.api.middleware.auth import AuthError, AuthErrorCode, decode_jwt
from src.schemas.auth import UserContext
from src.services.session_service import SessionService


# Session cookie configuration
SESSION_COOKIE_CONFIG = {
    "key": "autopilot_session",
    "max_age": 2592000,  # 30 days
    "httponly": True,
    "secure": True,  # Set to False in development
    "samesite": "lax",
    "path": "/",
}


@dataclass
class SessionContext:
    """Context for an anonymous session user."""

    session_id: UUID
    session_token: str


@dataclass
class AuthContext:
    """Context for authenticated user or anonymous session.

    Either user or session will be set, not both.
    """

    user: UserContext | None = None
    session: SessionContext | None = None

    @property
    def is_authenticated(self) -> bool:
        """Check if this is an authenticated user (vs anonymous session)."""
        return self.user is not None

    @property
    def profile_id(self) -> UUID | None:
        """Get the profile ID if authenticated."""
        return self.user.profile_id if self.user else None

    @property
    def session_id(self) -> UUID | None:
        """Get the session ID if anonymous."""
        return self.session.session_id if self.session else None


async def get_current_user(
    authorization: Annotated[str, Header(description="Bearer token")] = "",
) -> UserContext:
    """Extract and validate the current user from the Authorization header.

    This dependency requires a valid JWT token in the Authorization header.
    Use this for endpoints that require authentication.

    Args:
        authorization: The Authorization header value (Bearer token).

    Returns:
        UserContext: The authenticated user's context.

    Raises:
        HTTPException: 401 if token is missing, invalid, or expired.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract the token from "Bearer <token>" format
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    try:
        payload = decode_jwt(token)
        return payload.to_user_context()

    except AuthError as e:
        # Map auth errors to appropriate HTTP responses
        if e.code == AuthErrorCode.TOKEN_EXPIRED:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_optional_user(
    authorization: Annotated[str | None, Header()] = None,
) -> UserContext | None:
    """Extract the current user if an Authorization header is present.

    This dependency allows routes to work with or without authentication.
    Returns None if no token is provided, UserContext if valid token is provided.

    Args:
        authorization: Optional Authorization header value.

    Returns:
        UserContext | None: The user context if authenticated, None otherwise.
    """
    if not authorization:
        return None

    # If header is present, validate it
    try:
        return await get_current_user(authorization)
    except HTTPException:
        # If token is present but invalid, still raise the error
        raise


# Type aliases for cleaner dependency injection
CurrentUser = Annotated[UserContext, Depends(get_current_user)]
OptionalUser = Annotated[UserContext | None, Depends(get_optional_user)]


# Cookie utility functions


def get_session_cookie(request: Request) -> str | None:
    """Extract session token from cookie.

    Args:
        request: FastAPI request object.

    Returns:
        str | None: The session token or None if not present.
    """
    return request.cookies.get(SESSION_COOKIE_CONFIG["key"])


def set_session_cookie(response: Response, token: str) -> None:
    """Set session cookie on response.

    Args:
        response: FastAPI response object.
        token: The session token to set.
    """
    response.set_cookie(
        key=SESSION_COOKIE_CONFIG["key"],
        value=token,
        max_age=SESSION_COOKIE_CONFIG["max_age"],
        httponly=SESSION_COOKIE_CONFIG["httponly"],
        secure=SESSION_COOKIE_CONFIG["secure"],
        samesite=SESSION_COOKIE_CONFIG["samesite"],
        path=SESSION_COOKIE_CONFIG["path"],
    )


def clear_session_cookie(response: Response) -> None:
    """Clear session cookie from response.

    Args:
        response: FastAPI response object.
    """
    response.delete_cookie(
        key=SESSION_COOKIE_CONFIG["key"],
        path=SESSION_COOKIE_CONFIG["path"],
    )


# Dual authentication dependency


async def get_current_user_or_session(
    request: Request,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext:
    """Get authenticated user or anonymous session.

    This dependency supports both authentication methods:
    1. JWT token in Authorization header (authenticated user)
    2. Session cookie (anonymous user)

    If neither is present, a new session is created and the cookie is set.

    Args:
        request: FastAPI request object.
        response: FastAPI response object.
        authorization: Optional Authorization header.

    Returns:
        AuthContext: Context containing either user or session.
    """
    # First, try JWT authentication
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            try:
                payload = decode_jwt(token)
                return AuthContext(user=payload.to_user_context())
            except AuthError:
                # Invalid JWT - fall through to session handling
                pass

    # Try session cookie
    session_token = get_session_cookie(request)
    session_service = SessionService()

    if session_token:
        # Validate existing session
        if await session_service.is_session_valid(session_token):
            session = await session_service.get_session_by_token(session_token)
            if session:
                return AuthContext(
                    session=SessionContext(
                        session_id=UUID(session["id"]),
                        session_token=session_token,
                    )
                )

    # No valid auth - create new session
    session_data, new_token = await session_service.create_session()
    set_session_cookie(response, new_token)

    return AuthContext(
        session=SessionContext(
            session_id=UUID(session_data["id"]),
            session_token=new_token,
        )
    )


async def get_required_user_or_session(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthContext:
    """Get authenticated user or existing session (no auto-create).

    Like get_current_user_or_session but requires an existing session
    instead of creating one. Raises 401 if no valid auth is present.

    Args:
        request: FastAPI request object.
        authorization: Optional Authorization header.

    Returns:
        AuthContext: Context containing either user or session.

    Raises:
        HTTPException: 401 if no valid authentication is present.
    """
    # First, try JWT authentication
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
            try:
                payload = decode_jwt(token)
                return AuthContext(user=payload.to_user_context())
            except AuthError:
                pass

    # Try session cookie
    session_token = get_session_cookie(request)
    if session_token:
        session_service = SessionService()
        if await session_service.is_session_valid(session_token):
            session = await session_service.get_session_by_token(session_token)
            if session:
                return AuthContext(
                    session=SessionContext(
                        session_id=UUID(session["id"]),
                        session_token=session_token,
                    )
                )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


# Type aliases for dual auth
DualAuth = Annotated[AuthContext, Depends(get_current_user_or_session)]
RequiredDualAuth = Annotated[AuthContext, Depends(get_required_user_or_session)]

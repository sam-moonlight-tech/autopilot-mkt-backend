"""FastAPI dependency injection functions."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status

from src.api.middleware.auth import AuthError, AuthErrorCode, decode_jwt
from src.api.middleware.error_handler import RateLimitError
from src.core.config import get_settings
from src.core.rate_limiter import get_rate_limiter
from src.schemas.auth import UserContext
from src.services.session_service import SessionService


def get_session_cookie_config() -> dict:
    """Get session cookie configuration from settings."""
    settings = get_settings()
    # SameSite=None required for cross-origin requests (frontend on different domain)
    # But SameSite=None REQUIRES Secure=True or browsers will reject it
    # Use SameSite=Lax for local development (Secure=False)
    samesite = "none" if settings.session_cookie_secure else "lax"
    return {
        "key": settings.session_cookie_name,
        "max_age": settings.session_cookie_max_age,
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": samesite,
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
    def user_id(self) -> UUID | None:
        """Get the user ID if authenticated."""
        return self.user.user_id if self.user else None

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


def get_session_token(request: Request) -> str | None:
    """Extract session token from X-Session-Token header or cookie.

    Checks header first (works when third-party cookies are blocked),
    then falls back to cookie.

    Args:
        request: FastAPI request object.

    Returns:
        str | None: The session token or None if not present.
    """
    # Prefer header (works even when browsers block third-party cookies)
    header_token = request.headers.get("x-session-token")
    if header_token:
        return header_token

    # Fall back to cookie
    config = get_session_cookie_config()
    return request.cookies.get(config["key"])


def set_session_cookie(response: Response, token: str) -> None:
    """Set session cookie on response.

    Args:
        response: FastAPI response object.
        token: The session token to set.
    """
    config = get_session_cookie_config()
    response.set_cookie(
        key=config["key"],
        value=token,
        max_age=config["max_age"],
        httponly=config["httponly"],
        secure=config["secure"],
        samesite=config["samesite"],
        path=config["path"],
    )


def clear_session_cookie(response: Response) -> None:
    """Clear session cookie from response.

    Args:
        response: FastAPI response object.
    """
    config = get_session_cookie_config()
    response.delete_cookie(
        key=config["key"],
        path=config["path"],
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

    # Try session token from header or cookie
    session_token = get_session_token(request)
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
    # Also expose token via response header for when cookies are blocked
    response.headers["x-session-token"] = new_token

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

    # Try session token from header or cookie
    session_token = get_session_token(request)
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


# Rate limiting dependency


async def check_session_rate_limit(auth: DualAuth) -> None:
    """Check rate limit for all users (tiered limits).

    This dependency applies rate limiting to both anonymous and authenticated users.
    Authenticated users have higher limits than anonymous sessions.

    Args:
        auth: The auth context from DualAuth.

    Raises:
        RateLimitError: If the user/session has exceeded the rate limit.
    """
    settings = get_settings()
    limiter = get_rate_limiter()

    if auth.is_authenticated and auth.user:
        # Authenticated users: higher rate limit, keyed by user_id
        key = f"user:{auth.user.user_id}"
        max_requests = settings.rate_limit_authenticated_requests
    elif auth.session and auth.session.session_id:
        # Anonymous sessions: lower rate limit, keyed by session_id
        key = f"session:{auth.session.session_id}"
        max_requests = settings.rate_limit_anonymous_requests
    else:
        # No valid auth context - should not happen, but deny by default
        raise RateLimitError(
            message="Authentication required for rate limiting.",
            retry_after=60,
        )

    allowed, remaining, retry_after = await limiter.check_and_increment(
        key,
        max_requests=max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )

    if not allowed:
        raise RateLimitError(
            message="Rate limit exceeded. Please wait before sending more messages.",
            retry_after=retry_after,
        )


# Type alias for rate limit dependency
SessionRateLimit = Annotated[None, Depends(check_session_rate_limit)]

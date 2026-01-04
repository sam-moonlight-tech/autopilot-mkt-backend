"""FastAPI dependency injection functions."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from src.api.middleware.auth import AuthError, AuthErrorCode, decode_jwt
from src.schemas.auth import UserContext


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

"""JWT authentication middleware and utilities."""

import json
from enum import Enum
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWK

from src.core.config import get_settings
from src.schemas.auth import TokenPayload


class AuthErrorCode(str, Enum):
    """Authentication error codes."""

    UNAUTHORIZED = "UNAUTHORIZED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_TOKEN = "INVALID_TOKEN"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"


class AuthError(Exception):
    """Authentication error with specific error code.

    Raised when JWT validation fails for any reason.
    The error code indicates the specific failure reason.
    """

    def __init__(self, message: str, code: AuthErrorCode) -> None:
        """Initialize authentication error.

        Args:
            message: Human-readable error description.
            code: Specific error code for programmatic handling.
        """
        self.message = message
        self.code = code
        super().__init__(message)


@lru_cache
def get_signing_key() -> Any:
    """Load the public key from the signing key JWK environment variable.

    Returns:
        Public key for JWT verification.
    """
    settings = get_settings()
    jwk_json = settings.supabase_signing_key_jwk

    if not jwk_json:
        raise AuthError(
            "Signing key not configured",
            AuthErrorCode.INVALID_TOKEN,
        )

    try:
        jwk_data = json.loads(jwk_json)
    except json.JSONDecodeError as e:
        raise AuthError(
            f"Invalid signing key JWK format: {e}",
            AuthErrorCode.INVALID_TOKEN,
        )

    # Create PyJWK from the JWK data (uses only public components for verification)
    jwk = PyJWK.from_dict(jwk_data)
    return jwk.key


def decode_jwt(token: str) -> TokenPayload:
    """Decode and validate a JWT token.

    Validates the token signature, expiration, and structure.
    Uses ES256 algorithm with the configured signing key.

    Args:
        token: The JWT token string to decode.

    Returns:
        TokenPayload: Validated token payload.

    Raises:
        AuthError: If token is invalid, expired, or has wrong signature.
    """
    try:
        # Get the public key for verification
        public_key = get_signing_key()

        # Decode and verify the JWT
        payload: dict[str, Any] = jwt.decode(
            token,
            public_key,
            algorithms=["ES256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "require": ["exp", "iat", "sub"],
            },
        )

        # Parse into TokenPayload
        return TokenPayload(
            sub=payload["sub"],
            email=payload.get("email"),
            role=payload.get("role"),
            exp=payload["exp"],
            iat=payload["iat"],
            aud=payload.get("aud"),
            iss=payload.get("iss"),
        )

    except jwt.ExpiredSignatureError as e:
        raise AuthError(
            "Token has expired",
            AuthErrorCode.TOKEN_EXPIRED,
        ) from e

    except jwt.InvalidSignatureError as e:
        raise AuthError(
            "Invalid token signature",
            AuthErrorCode.INVALID_SIGNATURE,
        ) from e

    except jwt.DecodeError as e:
        raise AuthError(
            f"Invalid token format: {e}",
            AuthErrorCode.INVALID_TOKEN,
        ) from e

    except jwt.MissingRequiredClaimError as e:
        raise AuthError(
            f"Token missing required claim: {e}",
            AuthErrorCode.INVALID_TOKEN,
        ) from e

    except Exception as e:
        # Catch any other unexpected errors
        raise AuthError(
            f"Token validation failed: {e}",
            AuthErrorCode.INVALID_TOKEN,
        ) from e

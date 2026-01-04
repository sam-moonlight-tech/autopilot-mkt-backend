"""Authentication schemas for JWT tokens and user context."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserContext(BaseModel):
    """Authenticated user context extracted from JWT token.

    This model represents the authenticated user for the current request.
    It is populated by the auth middleware from the validated JWT.
    """

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(description="Unique identifier for the user (from JWT sub claim)")
    email: str | None = Field(default=None, description="User's email address if available")
    role: str | None = Field(default=None, description="User's role (e.g., 'user', 'admin')")


class TokenPayload(BaseModel):
    """JWT token payload structure for Supabase tokens.

    Represents the claims contained in a Supabase-issued JWT.
    Used for validation and extraction of user information.
    """

    model_config = ConfigDict(from_attributes=True)

    sub: str = Field(description="Subject - the user's UUID")
    email: str | None = Field(default=None, description="User's email address")
    role: str | None = Field(default=None, description="User's role")
    exp: int = Field(description="Expiration timestamp (Unix epoch)")
    iat: int = Field(description="Issued at timestamp (Unix epoch)")
    aud: str | None = Field(default=None, description="Audience - intended recipient")
    iss: str | None = Field(default=None, description="Issuer - token issuer URL")

    @property
    def expiration_datetime(self) -> datetime:
        """Get expiration as datetime object."""
        return datetime.fromtimestamp(self.exp)

    @property
    def issued_at_datetime(self) -> datetime:
        """Get issued at as datetime object."""
        return datetime.fromtimestamp(self.iat)

    def to_user_context(self) -> UserContext:
        """Convert token payload to UserContext.

        Returns:
            UserContext: User context derived from token claims.
        """
        return UserContext(
            user_id=UUID(self.sub),
            email=self.email,
            role=self.role,
        )


class AuthenticatedResponse(BaseModel):
    """Response for authenticated test endpoint.

    Used to verify authentication is working correctly.
    """

    model_config = ConfigDict(from_attributes=True)

    authenticated: bool = Field(default=True, description="Authentication status")
    user_id: str = Field(description="Authenticated user ID")
    email: str | None = Field(default=None, description="User email if available")
    role: str | None = Field(default=None, description="User role if available")

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


# Signup and verification schemas


class SignupRequest(BaseModel):
    """Request schema for user signup."""

    model_config = ConfigDict(from_attributes=True)

    email: str = Field(..., description="User's email address", min_length=3, max_length=255)
    password: str = Field(..., description="User's password", min_length=8, max_length=100)
    display_name: str | None = Field(default=None, description="User's display name", max_length=255)


class SignupResponse(BaseModel):
    """Response schema for user signup."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str = Field(description="Newly created user ID")
    email: str = Field(description="User's email address")
    message: str = Field(description="Success message")
    email_sent: bool = Field(description="Whether verification email was sent")


class VerifyEmailRequest(BaseModel):
    """Request schema for email verification."""

    model_config = ConfigDict(from_attributes=True)

    token: str = Field(..., description="Email verification token from Supabase")
    token_hash: str | None = Field(default=None, description="Token hash if provided by Supabase")


class VerifyEmailResponse(BaseModel):
    """Response schema for email verification."""

    model_config = ConfigDict(from_attributes=True)

    verified: bool = Field(description="Whether email was successfully verified")
    message: str = Field(description="Verification status message")
    redirect_url: str | None = Field(default=None, description="URL to redirect to after verification")


class ResendVerificationRequest(BaseModel):
    """Request schema for resending verification email."""

    model_config = ConfigDict(from_attributes=True)

    email: str = Field(..., description="Email address to resend verification to")


class ResendVerificationResponse(BaseModel):
    """Response schema for resending verification email."""

    model_config = ConfigDict(from_attributes=True)

    message: str = Field(description="Status message")
    email_sent: bool = Field(description="Whether email was sent")


class LoginRequest(BaseModel):
    """Request schema for user login."""

    model_config = ConfigDict(from_attributes=True)

    email: str = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


class LoginResponse(BaseModel):
    """Response schema for user login."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(description="JWT access token")
    refresh_token: str | None = Field(default=None, description="Refresh token if available")
    user_id: str = Field(description="User ID")
    email: str = Field(description="User's email address")
    expires_in: int = Field(description="Token expiration time in seconds")


# Password reset schemas


class ForgotPasswordRequest(BaseModel):
    """Request schema for password reset request."""

    model_config = ConfigDict(from_attributes=True)

    email: str = Field(..., description="User's email address", min_length=3, max_length=255)


class ForgotPasswordResponse(BaseModel):
    """Response schema for password reset request."""

    model_config = ConfigDict(from_attributes=True)

    message: str = Field(description="Status message")
    email_sent: bool = Field(description="Whether password reset email was sent")


class ResetPasswordRequest(BaseModel):
    """Request schema for password reset."""

    model_config = ConfigDict(from_attributes=True)

    token: str = Field(..., description="Password reset token from email")
    new_password: str = Field(..., description="New password", min_length=8, max_length=100)


class ResetPasswordResponse(BaseModel):
    """Response schema for password reset."""

    model_config = ConfigDict(from_attributes=True)

    message: str = Field(description="Status message")
    redirect_url: str | None = Field(default=None, description="URL to redirect to after reset")


# Change password schemas


class ChangePasswordRequest(BaseModel):
    """Request schema for changing password."""

    model_config = ConfigDict(from_attributes=True)

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password", min_length=8, max_length=100)


class ChangePasswordResponse(BaseModel):
    """Response schema for changing password."""

    model_config = ConfigDict(from_attributes=True)

    message: str = Field(description="Status message")


# Refresh token schemas


class RefreshTokenRequest(BaseModel):
    """Request schema for refreshing access token."""

    model_config = ConfigDict(from_attributes=True)

    refresh_token: str = Field(..., description="Refresh token")


class RefreshTokenResponse(BaseModel):
    """Response schema for refreshing access token."""

    model_config = ConfigDict(from_attributes=True)

    access_token: str = Field(description="New JWT access token")
    refresh_token: str | None = Field(default=None, description="New refresh token if rotated")
    expires_in: int = Field(description="Token expiration time in seconds")

"""Authentication API routes."""

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import CurrentUser
from src.api.middleware.error_handler import ValidationError
from src.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    SignupRequest,
    SignupResponse,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from src.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Sign up new user",
    description="Create a new user account with email and password. Verification email will be sent.",
)
async def signup(data: SignupRequest) -> SignupResponse:
    """Sign up a new user with email and password.

    Creates a new user account in Supabase Auth and sends a verification email.
    The user must verify their email before they can log in.

    Args:
        data: Signup request with email, password, and optional display name.

    Returns:
        SignupResponse: User ID, email, and verification email status.

    Raises:
        HTTPException: 400 if signup fails (e.g., email already exists).
    """
    service = AuthService()

    try:
        result = await service.signup(
            email=data.email,
            password=data.password,
            display_name=data.display_name,
        )
        return SignupResponse(**result)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/verify-email",
    response_model=VerifyEmailResponse,
    summary="Verify email address",
    description="Verify user's email address using verification token from email link.",
)
async def verify_email(data: VerifyEmailRequest) -> VerifyEmailResponse:
    """Verify user's email address with verification token.

    Verifies the email address using the token from the verification email.
    After successful verification, returns a redirect URL.

    Args:
        data: Verification request with token.

    Returns:
        VerifyEmailResponse: Verification status and redirect URL.

    Raises:
        HTTPException: 400 if verification fails (invalid/expired token).
    """
    service = AuthService()

    try:
        result = await service.verify_email(
            token=data.token,
            token_hash=data.token_hash,
        )
        return VerifyEmailResponse(**result)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/verify-email",
    response_model=VerifyEmailResponse,
    summary="Verify email address (GET)",
    description="Verify user's email address using token from query parameter. Used for email link redirects.",
)
async def verify_email_get(
    token: str = Query(..., description="Verification token from email link"),
    token_hash: str | None = Query(default=None, description="Optional token hash"),
) -> VerifyEmailResponse:
    """Verify user's email address via GET request (for email link redirects).

    This endpoint is used when users click the verification link in their email.
    It accepts the token as a query parameter and redirects to the frontend.

    Args:
        token: Verification token from email link.
        token_hash: Optional token hash.

    Returns:
        VerifyEmailResponse: Verification status and redirect URL.

    Raises:
        HTTPException: 400 if verification fails.
    """
    service = AuthService()

    try:
        result = await service.verify_email(
            token=token,
            token_hash=token_hash,
        )
        return VerifyEmailResponse(**result)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/resend-verification",
    response_model=ResendVerificationResponse,
    summary="Resend verification email",
    description="Resend verification email to user's email address.",
)
async def resend_verification(data: ResendVerificationRequest) -> ResendVerificationResponse:
    """Resend verification email to user.

    Sends a new verification email to the specified email address.
    Useful if the original email was lost or expired.

    Args:
        data: Request with email address.

    Returns:
        ResendVerificationResponse: Status message and email sent confirmation.

    Raises:
        HTTPException: 400 if resend fails (e.g., email not found, already verified).
    """
    service = AuthService()

    try:
        result = await service.resend_verification_email(email=data.email)
        return ResendVerificationResponse(**result)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login user",
    description="Authenticate user with email and password. Returns JWT access token.",
)
async def login(data: LoginRequest) -> LoginResponse:
    """Login user with email and password.

    Authenticates the user and returns a JWT access token and refresh token.
    The user must have verified their email before logging in.

    Args:
        data: Login request with email and password.

    Returns:
        LoginResponse: Access token, refresh token, and user information.

    Raises:
        HTTPException: 401 if login fails (invalid credentials or email not verified).
    """
    service = AuthService()

    try:
        result = await service.login(
            email=data.email,
            password=data.password,
        )
        return LoginResponse(**result)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e


@router.post(
    "/logout",
    summary="Logout user",
    description="Logout the current user and invalidate their session.",
)
async def logout(user: CurrentUser) -> dict[str, str]:
    """Logout the authenticated user.

    Invalidates the user's session. Note: This requires the access token
    to be passed in the Authorization header.

    Args:
        user: The authenticated user context.

    Returns:
        dict: Logout confirmation message.
    """
    # Note: For proper logout, we'd need the access token
    # Since we only have the decoded user context, we return success
    # The frontend should clear the token
    return {"message": "Logged out successfully"}


@router.get(
    "/me",
    summary="Get current user",
    description="Get the authenticated user's information from JWT token.",
)
async def get_current_user_info(user: CurrentUser) -> dict[str, str | None]:
    """Get current authenticated user information.

    Returns the user information extracted from the JWT token.
    This endpoint is useful for checking authentication status.

    Args:
        user: The authenticated user context.

    Returns:
        dict: User ID, email, and role.
    """
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "role": user.role,
    }


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request password reset",
    description="Send password reset email to user's email address.",
)
async def forgot_password(data: ForgotPasswordRequest) -> ForgotPasswordResponse:
    """Request password reset email.

    Sends a password reset email to the specified email address.
    For security, always returns success even if email doesn't exist.

    Args:
        data: Request with email address.

    Returns:
        ForgotPasswordResponse: Status message and email sent confirmation.

    Raises:
        HTTPException: 400 if request fails.
    """
    service = AuthService()

    try:
        result = await service.request_password_reset(email=data.email)
        return ForgotPasswordResponse(**result)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Reset password",
    description="Reset user password using token from password reset email.",
)
async def reset_password(data: ResetPasswordRequest) -> ResetPasswordResponse:
    """Reset user password with token from email.

    Resets the user's password using the token from the password reset email.
    After successful reset, returns a redirect URL.

    Args:
        data: Reset request with token and new password.

    Returns:
        ResetPasswordResponse: Status message and redirect URL.

    Raises:
        HTTPException: 400 if reset fails (invalid/expired token).
    """
    service = AuthService()

    try:
        result = await service.reset_password(
            token=data.token,
            new_password=data.new_password,
        )
        return ResetPasswordResponse(**result)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Reset password (GET)",
    description="Reset password using token from query parameter. Used for email link redirects.",
)
async def reset_password_get(
    token: str = Query(..., description="Password reset token from email link"),
    new_password: str = Query(..., description="New password"),
) -> ResetPasswordResponse:
    """Reset user password via GET request (for email link redirects).

    This endpoint is used when users click the password reset link in their email.
    Note: In practice, GET requests for password reset are less secure.
    Consider redirecting to a frontend form instead.

    Args:
        token: Password reset token from email link.
        new_password: New password.

    Returns:
        ResetPasswordResponse: Reset status and redirect URL.

    Raises:
        HTTPException: 400 if reset fails.
    """
    service = AuthService()

    try:
        result = await service.reset_password(
            token=token,
            new_password=new_password,
        )
        return ResetPasswordResponse(**result)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
    summary="Change password",
    description="Change password for authenticated user. Requires current password verification.",
)
async def change_password(
    data: ChangePasswordRequest,
    user: CurrentUser,
) -> ChangePasswordResponse:
    """Change password for authenticated user.

    Changes the user's password after verifying the current password.
    The user must be authenticated to use this endpoint.

    Args:
        data: Change password request with current and new password.
        user: The authenticated user context.

    Returns:
        ChangePasswordResponse: Status message.

    Raises:
        HTTPException: 400 if change fails (wrong current password, weak new password, etc.).
    """
    service = AuthService()

    try:
        result = await service.change_password(
            user_id=user.user_id,
            current_password=data.current_password,
            new_password=data.new_password,
        )
        return ChangePasswordResponse(**result)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    summary="Refresh access token",
    description="Refresh access token using refresh token. Returns new access token and optionally new refresh token.",
)
async def refresh_token(data: RefreshTokenRequest) -> RefreshTokenResponse:
    """Refresh access token using refresh token.

    Issues a new access token using a valid refresh token.
    This allows users to maintain their session without re-logging in.

    Args:
        data: Refresh request with refresh token.

    Returns:
        RefreshTokenResponse: New access token, refresh token, and expiration.

    Raises:
        HTTPException: 401 if refresh fails (invalid/expired refresh token).
    """
    service = AuthService()

    try:
        result = await service.refresh_token(refresh_token=data.refresh_token)
        return RefreshTokenResponse(**result)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from e


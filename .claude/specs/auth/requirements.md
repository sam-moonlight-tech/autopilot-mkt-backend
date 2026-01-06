# Requirements Document: Authentication

## Introduction

This specification defines the authentication layer for the Autopilot backend API. It establishes a complete authentication system including user signup, email verification, login, and JWT token verification. The system uses Supabase Auth as the identity provider, with the backend handling signup flows, email verification, and token validation.

## Alignment with Product Vision

Authentication enables the Autopilot platform by providing:
- **User Registration**: Email/password signup with verification
- **Secure Access**: Only authenticated users can access conversations and profile data
- **User Context**: All operations are tied to a specific user identity
- **Email Verification**: Ensures valid email addresses before account activation
- **Sales Demo Ready**: Supports the sales-led flow where reps sign in to demonstrate the platform

## Requirements

### Requirement 1: JWT Token Verification Middleware

**User Story:** As a developer, I want automatic JWT verification on protected routes, so that I don't need to manually validate tokens in each endpoint.

#### Acceptance Criteria

1. WHEN a request includes an Authorization header with "Bearer {token}" THEN the system SHALL validate the JWT against Supabase's public key
2. IF the Authorization header is missing THEN the system SHALL return HTTP 401 with error code "UNAUTHORIZED"
3. IF the JWT is expired THEN the system SHALL return HTTP 401 with error code "TOKEN_EXPIRED"
4. IF the JWT signature is invalid THEN the system SHALL return HTTP 401 with error code "INVALID_TOKEN"
5. WHEN the JWT is valid THEN the system SHALL extract the user_id from the token's "sub" claim

### Requirement 2: User Context Extraction

**User Story:** As a developer, I want to access the authenticated user's information in my route handlers, so that I can perform user-specific operations.

#### Acceptance Criteria

1. WHEN a protected route is called with valid authentication THEN the system SHALL provide a UserContext object containing the user_id
2. WHEN a protected route is called THEN the system SHALL extract the user's email from the JWT claims if present
3. WHEN a protected route is called THEN the system SHALL make the UserContext available via FastAPI dependency injection
4. IF the user context cannot be extracted THEN the system SHALL return HTTP 401 with descriptive error

### Requirement 3: Route Protection Decorator

**User Story:** As a developer, I want a simple way to mark routes as protected, so that I can consistently enforce authentication across the API.

#### Acceptance Criteria

1. WHEN a route uses the `get_current_user` dependency THEN the system SHALL require valid authentication
2. IF authentication fails for a protected route THEN the system SHALL return 401 before executing the route handler
3. WHEN defining a protected route THEN the system SHALL support optional user access for routes that work with or without auth
4. WHEN authentication is optional THEN the system SHALL return None for the user if not authenticated

### Requirement 4: Token Refresh Awareness

**User Story:** As a frontend developer, I want clear error responses for expired tokens, so that I can trigger token refresh flows appropriately.

#### Acceptance Criteria

1. WHEN a token is expired THEN the system SHALL return a specific error code "TOKEN_EXPIRED" distinct from other auth errors
2. WHEN a token is expired THEN the system SHALL include a message indicating the client should refresh their token
3. WHEN returning auth errors THEN the system SHALL use consistent ErrorResponse schema format

### Requirement 5: User Signup with Email Verification

**User Story:** As a new user, I want to sign up with my email and password, so that I can create an account and start using the platform.

#### Acceptance Criteria

1. WHEN a user submits signup with email and password THEN the system SHALL create a user account in Supabase Auth
2. WHEN a user signs up THEN the system SHALL send a verification email to the provided email address
3. WHEN a user signs up THEN the system SHALL return user_id, email, and email_sent status
4. IF the email already exists THEN the system SHALL return HTTP 400 with appropriate error message
5. IF the password is too weak THEN the system SHALL return HTTP 400 with validation error
6. WHEN a user signs up with display_name THEN the system SHALL store it in user metadata

### Requirement 6: Email Verification

**User Story:** As a new user, I want to verify my email address, so that I can activate my account and log in.

#### Acceptance Criteria

1. WHEN a user clicks the verification link in their email THEN the system SHALL verify the email address
2. WHEN email verification succeeds THEN the system SHALL return a redirect URL to the frontend
3. WHEN email verification succeeds THEN the system SHALL mark the user's email as verified in Supabase
4. IF the verification token is invalid or expired THEN the system SHALL return HTTP 400 with error message
5. WHEN verification completes THEN the system SHALL redirect to the configured AUTH_REDIRECT_URL
6. WHEN a user requests email verification via POST THEN the system SHALL accept token in request body
7. WHEN a user requests email verification via GET THEN the system SHALL accept token as query parameter (for email link redirects)

### Requirement 7: Resend Verification Email

**User Story:** As a user, I want to resend my verification email, so that I can verify my account if I lost the original email.

#### Acceptance Criteria

1. WHEN a user requests to resend verification email THEN the system SHALL send a new verification email
2. IF the email is not found THEN the system SHALL return HTTP 400 with error message
3. IF the email is already verified THEN the system SHALL return HTTP 400 indicating verification not needed
4. WHEN resend succeeds THEN the system SHALL return confirmation that email was sent

### Requirement 8: User Login

**User Story:** As a user, I want to log in with my email and password, so that I can access my account.

#### Acceptance Criteria

1. WHEN a user submits valid email and password THEN the system SHALL authenticate the user
2. WHEN login succeeds THEN the system SHALL return JWT access token and refresh token
3. WHEN login succeeds THEN the system SHALL return user_id, email, and token expiration time
4. IF credentials are invalid THEN the system SHALL return HTTP 401 with error message
5. IF email is not verified THEN the system SHALL return HTTP 401 indicating verification required
6. WHEN login succeeds THEN the system SHALL create a session in Supabase

### Requirement 9: User Logout

**User Story:** As a user, I want to log out, so that I can securely end my session.

#### Acceptance Criteria

1. WHEN an authenticated user requests logout THEN the system SHALL invalidate their session
2. WHEN logout succeeds THEN the system SHALL return confirmation message
3. WHEN logout is called THEN the system SHALL clear the user's session in Supabase

### Requirement 10: Redirect URL Configuration

**User Story:** As a developer, I want to configure redirect URLs per environment, so that email verification links work correctly in development, staging, and production.

#### Acceptance Criteria

1. WHEN the system sends verification emails THEN it SHALL use the AUTH_REDIRECT_URL environment variable
2. WHEN AUTH_REDIRECT_URL is not set THEN the system SHALL raise a configuration error
3. WHEN verification completes THEN the system SHALL redirect to AUTH_REDIRECT_URL with success status
4. WHEN redirect URL is configured THEN it SHALL be included in all verification email links

### Requirement 11: Password Reset (Forgot Password)

**User Story:** As a user, I forgot my password and need to reset it via email, so that I can regain access to my account.

#### Acceptance Criteria

1. WHEN a user requests password reset with their email THEN the system SHALL send a password reset email
2. WHEN password reset email is sent THEN the system SHALL return confirmation that email was sent
3. WHEN a user clicks the password reset link in their email THEN the system SHALL allow them to set a new password
4. WHEN a user submits a new password with valid reset token THEN the system SHALL update their password
5. IF the reset token is invalid or expired THEN the system SHALL return HTTP 400 with error message
6. IF the email is not found THEN the system SHALL return HTTP 400 with error message (for security, don't reveal if email exists)
7. WHEN password reset succeeds THEN the system SHALL return a redirect URL to the frontend
8. WHEN a user requests password reset via POST THEN the system SHALL accept email in request body
9. WHEN a user requests password reset via GET THEN the system SHALL accept token as query parameter (for email link redirects)

### Requirement 12: Change Password (Authenticated)

**User Story:** As a logged-in user, I want to change my password, so that I can update it for security reasons.

#### Acceptance Criteria

1. WHEN an authenticated user requests to change password THEN the system SHALL require current password verification
2. WHEN current password is verified THEN the system SHALL update to new password
3. IF current password is incorrect THEN the system SHALL return HTTP 401 with error message
4. IF new password is too weak THEN the system SHALL return HTTP 400 with validation error
5. IF new password is same as current password THEN the system SHALL return HTTP 400 with error message
6. WHEN password change succeeds THEN the system SHALL return confirmation message
7. WHEN password is changed THEN the system SHALL invalidate all other sessions (optional, security best practice)

### Requirement 13: Refresh Access Token

**User Story:** As a user, I want my session to stay active without re-logging in, so that I have a seamless experience.

#### Acceptance Criteria

1. WHEN a user provides a valid refresh token THEN the system SHALL issue a new access token
2. WHEN refresh succeeds THEN the system SHALL return new access token and optionally new refresh token
3. WHEN refresh succeeds THEN the system SHALL return token expiration time
4. IF refresh token is invalid or expired THEN the system SHALL return HTTP 401 with error message
5. WHEN refresh token is used THEN the system SHALL optionally rotate to a new refresh token (security best practice)
6. WHEN refresh succeeds THEN the system SHALL maintain the same user session

## Non-Functional Requirements

### Performance
- JWT verification SHALL complete in under 10ms
- Token validation SHALL not require external API calls after initial JWKS fetch
- JWKS SHALL be cached and refreshed only when keys rotate

### Security
- JWT secrets SHALL never be logged
- Failed authentication attempts SHALL be logged with IP address
- System SHALL reject tokens with "none" algorithm
- System SHALL validate token issuer matches Supabase project

### Reliability
- System SHALL handle JWKS fetch failures gracefully with cached keys
- System SHALL not crash on malformed Authorization headers
- System SHALL handle concurrent requests with same token efficiently

### Usability
- Error messages SHALL clearly indicate why authentication failed
- API documentation SHALL show which endpoints require authentication
- Protected endpoints SHALL show lock icon in Swagger UI

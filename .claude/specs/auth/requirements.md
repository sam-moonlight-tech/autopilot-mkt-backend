# Requirements Document: Authentication

## Introduction

This specification defines the authentication layer for the Autopilot backend API. It establishes JWT token verification middleware that validates Supabase-issued tokens, extracts user context for protected routes, and provides dependency injection for accessing the authenticated user throughout the application.

## Alignment with Product Vision

Authentication enables the Autopilot platform by providing:
- **Secure Access**: Only authenticated users can access conversations and profile data
- **User Context**: All operations are tied to a specific user identity
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

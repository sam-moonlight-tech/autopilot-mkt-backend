# Implementation Plan: Authentication

## Task Overview

This implementation plan establishes complete authentication for the Autopilot backend, including user signup, email verification, login, logout, and JWT token verification. Tasks build from schemas through services to routes, enabling full authentication flows and protected routes across the application.

## Implementation Status

✅ **COMPLETED** - All authentication features have been implemented:
- User signup with email/password
- Email verification with redirect URLs
- Resend verification email
- User login
- User logout
- JWT token verification for protected routes
- Configuration via environment variables

## Steering Document Compliance

- Files follow `structure.md` directory layout
- Uses snake_case for modules per naming conventions
- Integrates with existing error handling patterns from core-infra

## Atomic Task Requirements

**Each task meets these criteria:**
- **File Scope**: Touches 1-3 related files maximum
- **Time Boxing**: Completable in 15-30 minutes
- **Single Purpose**: One testable outcome per task
- **Specific Files**: Exact file paths specified
- **Agent-Friendly**: Clear input/output with minimal context switching

## Tasks

- [x] 2.1. Create auth schemas for UserContext and TokenPayload
  - File: `src/schemas/auth.py` (create)
  - Define UserContext with user_id (UUID), email (optional), role (optional)
  - Define TokenPayload with sub, email, role, exp, iat, aud, iss fields
  - Use Pydantic v2 syntax with model_config
  - Purpose: Establish type-safe auth data structures
  - _Leverage: src/schemas/common.py for patterns_
  - _Requirements: 2_

- [x] 2.2. Implement JWT decoding and validation utilities
  - File: `src/api/middleware/auth.py` (create)
  - Import python-jose JWT library
  - Create decode_jwt() function that validates signature, expiration, issuer
  - Define AuthError exception class with code field (UNAUTHORIZED, TOKEN_EXPIRED, INVALID_TOKEN)
  - Use JWT secret from settings for HS256 verification
  - Purpose: Central JWT validation logic
  - _Leverage: src/core/config.py for settings_
  - _Requirements: 1_

- [x] 2.3. Implement get_current_user dependency
  - File: `src/api/deps.py` (create)
  - Create async get_current_user() function with Authorization header parameter
  - Extract Bearer token from header
  - Call decode_jwt() and convert to UserContext
  - Raise HTTPException 401 on auth failures
  - Purpose: Enable protected routes via dependency injection
  - _Leverage: src/api/middleware/auth.py, src/schemas/auth.py_
  - _Requirements: 2, 3_

- [x] 2.4. Implement get_optional_user dependency
  - File: `src/api/deps.py` (modify)
  - Create async get_optional_user() function
  - Return None if no Authorization header present
  - Return UserContext if valid token provided
  - Purpose: Support routes that work with or without auth
  - _Leverage: get_current_user implementation_
  - _Requirements: 3_

- [x] 2.5. Add JWT secret to configuration
  - File: `src/core/config.py` (modify)
  - Add jwt_secret field to Settings class
  - Add supabase_jwt_secret as alias (Supabase uses this naming)
  - Ensure validation that secret is provided
  - Purpose: Configure JWT verification
  - _Leverage: existing Settings class_
  - _Requirements: 1_

- [x] 2.6. Create protected test endpoint
  - File: `src/api/routes/health.py` (modify)
  - Add GET /health/auth endpoint requiring authentication
  - Return user context information if authenticated
  - Use get_current_user dependency
  - Purpose: Enable testing of auth flow
  - _Leverage: src/api/deps.py_
  - _Requirements: 1, 2_

- [x] 2.7. Write unit tests for JWT decoding
  - File: `tests/unit/test_auth.py` (create)
  - Test decode_jwt() with valid token
  - Test decode_jwt() with expired token raises AuthError
  - Test decode_jwt() with invalid signature raises AuthError
  - Test decode_jwt() with malformed token raises AuthError
  - Mock JWT secret in tests
  - Purpose: Verify JWT validation logic
  - _Requirements: 1_

- [x] 2.8. Write unit tests for auth dependencies
  - File: `tests/unit/test_deps.py` (create)
  - Test get_current_user() extracts UserContext correctly
  - Test get_current_user() raises 401 for missing header
  - Test get_optional_user() returns None for missing header
  - Test get_optional_user() returns UserContext for valid token
  - Purpose: Verify dependency injection works correctly
  - _Requirements: 2, 3_

- [x] 2.9. Write integration tests for protected endpoints
  - File: `tests/integration/test_auth_routes.py` (create)
  - Test /health/auth returns 401 without auth header
  - Test /health/auth returns 401 with expired token
  - Test /health/auth returns 200 with valid token
  - Use test client with mocked auth
  - Purpose: Verify end-to-end auth flow
  - _Requirements: 1, 2, 4_

- [x] 2.10. Update requirements.txt with auth dependencies
  - File: `requirements.txt` (modify)
  - Add python-jose[cryptography] for JWT operations
  - Purpose: Ensure auth dependencies are installed
  - _Leverage: existing requirements.txt_
  - _Requirements: 1_

## Additional Implementation Tasks (Completed)

- [x] 2.11. Create auth service for Supabase integration
  - File: `src/services/auth_service.py` (create)
  - Implement signup, login, verify_email, resend_verification, logout methods
  - Integrate with Supabase Auth API
  - Handle error cases and validation
  - Purpose: Business logic for authentication operations
  - _Requirements: 5, 6, 7, 8, 9_

- [x] 2.12. Create auth routes
  - File: `src/api/routes/auth.py` (create)
  - Implement POST /auth/signup endpoint
  - Implement POST /auth/login endpoint
  - Implement POST/GET /auth/verify-email endpoints
  - Implement POST /auth/resend-verification endpoint
  - Implement POST /auth/logout endpoint
  - Implement GET /auth/me endpoint
  - Purpose: Expose authentication endpoints via API
  - _Requirements: 5, 6, 7, 8, 9_

- [x] 2.13. Add auth schemas for signup/login/verification
  - File: `src/schemas/auth.py` (modify)
  - Add SignupRequest, SignupResponse schemas
  - Add LoginRequest, LoginResponse schemas
  - Add VerifyEmailRequest, VerifyEmailResponse schemas
  - Add ResendVerificationRequest, ResendVerificationResponse schemas
  - Purpose: Type-safe request/response models
  - _Requirements: 5, 6, 7, 8_

- [x] 2.14. Add redirect URL configuration
  - File: `src/core/config.py` (modify)
  - Add AUTH_REDIRECT_URL environment variable (required)
  - Update CORS origins to include redirect URL
  - Purpose: Configure redirect URLs per environment
  - _Requirements: 10_

- [x] 2.15. Register auth router in main application
  - File: `src/main.py` (modify)
  - Import auth router
  - Register auth router in API v1 router
  - Purpose: Enable authentication endpoints
  - _Requirements: 5, 6, 7, 8, 9_

- [x] 2.16. Update documentation
  - File: `README.md` (modify)
  - Add AUTH_REDIRECT_URL to environment variables
  - Update API documentation with new auth endpoints
  - Purpose: Document authentication features
  - _Requirements: 5, 6, 7, 8, 9, 10_

## Password Management Implementation Tasks (Completed)

- [x] 2.17. Add password reset schemas
  - File: `src/schemas/auth.py` (modify)
  - Add ForgotPasswordRequest, ForgotPasswordResponse schemas
  - Add ResetPasswordRequest, ResetPasswordResponse schemas
  - Add ChangePasswordRequest, ChangePasswordResponse schemas
  - Add RefreshTokenRequest, RefreshTokenResponse schemas
  - Purpose: Type-safe request/response models for password management
  - _Requirements: 11, 12, 13_

- [x] 2.18. Implement password reset service methods
  - File: `src/services/auth_service.py` (modify)
  - Implement request_password_reset() method
  - Implement reset_password() method
  - Implement change_password() method
  - Implement refresh_token() method
  - Integrate with Supabase Auth API
  - Handle error cases and security considerations
  - Purpose: Business logic for password management
  - _Requirements: 11, 12, 13_

- [x] 2.19. Add password management routes
  - File: `src/api/routes/auth.py` (modify)
  - Implement POST /auth/forgot-password endpoint
  - Implement POST /auth/reset-password endpoint
  - Implement GET /auth/reset-password endpoint (for email links)
  - Implement POST /auth/change-password endpoint (requires auth)
  - Implement POST /auth/refresh endpoint
  - Purpose: Expose password management endpoints via API
  - _Requirements: 11, 12, 13_

- [x] 2.20. Update API documentation
  - File: `README.md` (modify)
  - Add password reset endpoints to API documentation
  - Add change password endpoint to API documentation
  - Add refresh token endpoint to API documentation
  - Purpose: Document new password management features
  - _Requirements: 11, 12, 13_

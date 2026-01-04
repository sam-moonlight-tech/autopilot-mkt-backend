# Implementation Plan: Authentication

## Task Overview

This implementation plan establishes JWT-based authentication for the Autopilot backend. Tasks build from schemas through middleware to dependencies, enabling protected routes across the application.

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

- [ ] 2.1. Create auth schemas for UserContext and TokenPayload
  - File: `src/schemas/auth.py` (create)
  - Define UserContext with user_id (UUID), email (optional), role (optional)
  - Define TokenPayload with sub, email, role, exp, iat, aud, iss fields
  - Use Pydantic v2 syntax with model_config
  - Purpose: Establish type-safe auth data structures
  - _Leverage: src/schemas/common.py for patterns_
  - _Requirements: 2_

- [ ] 2.2. Implement JWT decoding and validation utilities
  - File: `src/api/middleware/auth.py` (create)
  - Import python-jose JWT library
  - Create decode_jwt() function that validates signature, expiration, issuer
  - Define AuthError exception class with code field (UNAUTHORIZED, TOKEN_EXPIRED, INVALID_TOKEN)
  - Use JWT secret from settings for HS256 verification
  - Purpose: Central JWT validation logic
  - _Leverage: src/core/config.py for settings_
  - _Requirements: 1_

- [ ] 2.3. Implement get_current_user dependency
  - File: `src/api/deps.py` (create)
  - Create async get_current_user() function with Authorization header parameter
  - Extract Bearer token from header
  - Call decode_jwt() and convert to UserContext
  - Raise HTTPException 401 on auth failures
  - Purpose: Enable protected routes via dependency injection
  - _Leverage: src/api/middleware/auth.py, src/schemas/auth.py_
  - _Requirements: 2, 3_

- [ ] 2.4. Implement get_optional_user dependency
  - File: `src/api/deps.py` (modify)
  - Create async get_optional_user() function
  - Return None if no Authorization header present
  - Return UserContext if valid token provided
  - Purpose: Support routes that work with or without auth
  - _Leverage: get_current_user implementation_
  - _Requirements: 3_

- [ ] 2.5. Add JWT secret to configuration
  - File: `src/core/config.py` (modify)
  - Add jwt_secret field to Settings class
  - Add supabase_jwt_secret as alias (Supabase uses this naming)
  - Ensure validation that secret is provided
  - Purpose: Configure JWT verification
  - _Leverage: existing Settings class_
  - _Requirements: 1_

- [ ] 2.6. Create protected test endpoint
  - File: `src/api/routes/health.py` (modify)
  - Add GET /health/auth endpoint requiring authentication
  - Return user context information if authenticated
  - Use get_current_user dependency
  - Purpose: Enable testing of auth flow
  - _Leverage: src/api/deps.py_
  - _Requirements: 1, 2_

- [ ] 2.7. Write unit tests for JWT decoding
  - File: `tests/unit/test_auth.py` (create)
  - Test decode_jwt() with valid token
  - Test decode_jwt() with expired token raises AuthError
  - Test decode_jwt() with invalid signature raises AuthError
  - Test decode_jwt() with malformed token raises AuthError
  - Mock JWT secret in tests
  - Purpose: Verify JWT validation logic
  - _Requirements: 1_

- [ ] 2.8. Write unit tests for auth dependencies
  - File: `tests/unit/test_deps.py` (create)
  - Test get_current_user() extracts UserContext correctly
  - Test get_current_user() raises 401 for missing header
  - Test get_optional_user() returns None for missing header
  - Test get_optional_user() returns UserContext for valid token
  - Purpose: Verify dependency injection works correctly
  - _Requirements: 2, 3_

- [ ] 2.9. Write integration tests for protected endpoints
  - File: `tests/integration/test_auth_routes.py` (create)
  - Test /health/auth returns 401 without auth header
  - Test /health/auth returns 401 with expired token
  - Test /health/auth returns 200 with valid token
  - Use test client with mocked auth
  - Purpose: Verify end-to-end auth flow
  - _Requirements: 1, 2, 4_

- [ ] 2.10. Update requirements.txt with auth dependencies
  - File: `requirements.txt` (modify)
  - Add python-jose[cryptography] for JWT operations
  - Purpose: Ensure auth dependencies are installed
  - _Leverage: existing requirements.txt_
  - _Requirements: 1_

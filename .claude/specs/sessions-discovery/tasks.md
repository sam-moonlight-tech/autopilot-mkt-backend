# Implementation Plan: Sessions & Discovery Profiles

## Task Overview

This implementation plan establishes session management for anonymous users and discovery profile storage for authenticated users. Tasks are ordered to build database schema first, then models/schemas, then services, and finally routes.

## Steering Document Compliance

- Files follow `structure.md` directory layout
- Uses snake_case for modules, PascalCase for classes
- Follows layered architecture: routes -> services -> models

## Atomic Task Requirements

**Each task meets these criteria:**
- **File Scope**: Touches 1-3 related files maximum
- **Time Boxing**: Completable in 15-30 minutes
- **Single Purpose**: One testable outcome per task
- **Specific Files**: Exact file paths specified
- **Agent-Friendly**: Clear input/output with minimal context switching

## Tasks

### Database Layer

- [x] 6.1. Create session_phase enum and sessions table migration
  - File: `supabase/migrations/005_create_sessions.sql` (create)
  - Define session_phase enum: 'discovery', 'roi', 'greenlight'
  - Create sessions table with: id, session_token (unique), conversation_id FK, current_question_index, phase, answers (JSONB), roi_inputs (JSONB), selected_product_ids (UUID[]), timeframe, metadata, claimed_by_profile_id FK, expires_at, timestamps
  - Add indexes on session_token, conversation_id, expires_at
  - Purpose: Establish anonymous session storage
  - _Requirements: 1, 2_

- [x] 6.2. Create discovery_profiles table migration
  - File: `supabase/migrations/006_create_discovery_profiles.sql` (create)
  - Create discovery_profiles table with: id, profile_id (unique FK), current_question_index, phase (session_phase), answers (JSONB), roi_inputs (JSONB), selected_product_ids (UUID[]), timeframe, timestamps
  - Add RLS policies for profile owner access
  - Add index on profile_id
  - Purpose: Establish authenticated user discovery storage
  - _Requirements: 5_

- [x] 6.3. Update conversations table for session ownership
  - File: `supabase/migrations/009_update_conversations.sql` (create)
  - Make user_id nullable
  - Add session_id UUID column with FK to sessions
  - Add constraint: user_id OR session_id must be non-null
  - Add index on session_id
  - Migrate existing conversation_phase enum to new values
  - Purpose: Enable session-owned conversations and phase alignment
  - _Requirements: 3, 6_

### Model Layer

- [x] 6.4. Create session model type hints
  - File: `src/models/session.py` (create)
  - Define Session TypedDict with all table columns
  - Define SessionPhase literal type
  - Include DiscoveryAnswer and ROIInputs type structures
  - Purpose: Type-safe session data handling
  - _Requirements: 1, 2_

- [x] 6.5. Create discovery_profile model type hints
  - File: `src/models/discovery_profile.py` (create)
  - Define DiscoveryProfile TypedDict with all table columns
  - Reuse types from session model where applicable
  - Purpose: Type-safe discovery profile handling
  - _Requirements: 5_

- [x] 6.6. Update conversation model for phase alignment
  - File: `src/models/conversation.py` (modify)
  - Update ConversationPhase enum to: DISCOVERY, ROI, GREENLIGHT
  - Remove SELECTION and COMPLETED phases
  - Add session_id to Conversation TypedDict
  - Purpose: Align phases with frontend
  - _Requirements: 6_

### Schema Layer

- [x] 6.7. Create session Pydantic schemas
  - File: `src/schemas/session.py` (create)
  - Define DiscoveryAnswerSchema with questionId, key, label, value, group
  - Define ROIInputsSchema with laborRate, utilization, maintenanceFactor, manualMonthlySpend, manualMonthlyHours
  - Define SessionUpdate for PUT /sessions/me
  - Define SessionResponse for GET /sessions/me
  - Define SessionClaimResponse for POST /sessions/claim
  - Purpose: API contracts for session endpoints
  - _Requirements: 1, 2, 4_

- [x] 6.8. Create discovery profile Pydantic schemas
  - File: `src/schemas/discovery.py` (create)
  - Define DiscoveryProfileUpdate for PUT /discovery
  - Define DiscoveryProfileResponse for GET /discovery
  - Import and reuse DiscoveryAnswerSchema, ROIInputsSchema from session schemas
  - Purpose: API contracts for discovery endpoints
  - _Requirements: 5_

### Service Layer

- [x] 6.9. Implement SessionService core methods
  - File: `src/services/session_service.py` (create)
  - Implement create_session() that generates 64-char token and inserts record
  - Implement get_session_by_token() for token-based lookup
  - Implement update_session() for updating session fields
  - Implement is_session_valid() to check token and expiration
  - Purpose: Core session business logic
  - _Leverage: src/core/supabase.py, secrets module_
  - _Requirements: 1, 2_

- [x] 6.10. Add session claim method to SessionService
  - File: `src/services/session_service.py` (modify)
  - Implement claim_session() that:
    - Verifies session not already claimed
    - Creates/updates discovery_profile with session data
    - Transfers conversation ownership
    - Sets claimed_by_profile_id
  - Use transaction for atomicity
  - Purpose: Session-to-profile merge logic
  - _Leverage: src/services/discovery_profile_service.py, src/services/conversation_service.py_
  - _Requirements: 4_

- [x] 6.11. Add session cleanup method to SessionService
  - File: `src/services/session_service.py` (modify)
  - Implement cleanup_expired_sessions() that deletes sessions past expires_at
  - Return count of deleted sessions
  - Purpose: Prevent table bloat from expired sessions
  - _Requirements: Non-functional reliability_

- [x] 6.12. Implement DiscoveryProfileService
  - File: `src/services/discovery_profile_service.py` (create)
  - Implement get_or_create() for profile_id
  - Implement update() for updating discovery profile fields
  - Implement create_from_session() for creating from session data
  - Purpose: Discovery profile business logic
  - _Leverage: src/core/supabase.py_
  - _Requirements: 5_

- [x] 6.13. Update ConversationService for session ownership
  - File: `src/services/conversation_service.py` (modify)
  - Add create_conversation_for_session() method
  - Add can_access_by_session() method for session-based authorization
  - Add transfer_to_profile() method for ownership transfer
  - Update existing create_conversation to accept optional session_id
  - Purpose: Enable session-owned conversations
  - _Leverage: existing conversation_service.py_
  - _Requirements: 3_

- [x] 6.14. Update AgentService for phase alignment
  - File: `src/services/agent_service.py` (modify)
  - Update SYSTEM_PROMPTS dict keys from 'selection' to 'greenlight'
  - Update greenlight phase prompt content for checkout guidance
  - Purpose: Align agent behavior with new phases
  - _Requirements: 6_

### Dependency Layer

- [x] 6.15. Add dual auth dependency
  - File: `src/api/deps.py` (modify)
  - Define SessionContext dataclass with session_id, session_token
  - Define AuthContext dataclass with optional user, optional session
  - Implement get_current_user_or_session() that:
    - First tries JWT from Authorization header
    - Falls back to session token from cookie
    - Creates new session if neither present
  - Purpose: Reusable dual authentication dependency
  - _Leverage: existing get_current_user, src/services/session_service.py_
  - _Requirements: 7_

- [x] 6.16. Add cookie utility functions
  - File: `src/api/deps.py` (modify)
  - Add get_session_cookie() helper to extract cookie from request
  - Add set_session_cookie() helper to set cookie on response
  - Add clear_session_cookie() helper to clear cookie
  - Define SESSION_COOKIE_CONFIG constant
  - Purpose: Centralized cookie handling
  - _Requirements: 1_

### Route Layer

- [x] 6.17. Create session routes
  - File: `src/api/routes/sessions.py` (create)
  - Implement POST /sessions to create session and set cookie
  - Implement GET /sessions/me to get current session
  - Implement PUT /sessions/me to update session data
  - Use dual auth dependency (creates session if needed)
  - Purpose: Session API endpoints
  - _Leverage: src/api/deps.py, src/services/session_service.py_
  - _Requirements: 1, 2_

- [x] 6.18. Add session claim endpoint
  - File: `src/api/routes/sessions.py` (modify)
  - Implement POST /sessions/claim requiring both JWT and session cookie
  - Clear session cookie after successful claim
  - Return discovery profile data
  - Purpose: Session-to-profile merge endpoint
  - _Leverage: src/services/session_service.py_
  - _Requirements: 4_

- [x] 6.19. Create discovery profile routes
  - File: `src/api/routes/discovery.py` (create)
  - Implement GET /discovery to get user's discovery profile
  - Implement PUT /discovery to update discovery profile
  - Require JWT authentication
  - Purpose: Discovery profile API endpoints
  - _Leverage: src/api/deps.py, src/services/discovery_profile_service.py_
  - _Requirements: 5_

- [x] 6.20. Update conversation routes for dual auth
  - File: `src/api/routes/conversations.py` (modify)
  - Update POST /conversations to use dual auth dependency
  - Update access checks to verify session ownership
  - Update message endpoints to work with session-owned conversations
  - Purpose: Enable anonymous user conversations
  - _Leverage: src/api/deps.py updated dependency_
  - _Requirements: 3, 7_

### Configuration Layer

- [x] 6.21. Add session configuration settings
  - File: `src/core/config.py` (modify)
  - Add session_cookie_name: str (default: "autopilot_session")
  - Add session_cookie_max_age: int (default: 2592000)
  - Add session_cookie_secure: bool (default: True)
  - Add session_expiry_days: int (default: 30)
  - Purpose: Configurable session settings
  - _Requirements: 1, Non-functional_

### Registration Layer

- [x] 6.22. Register session and discovery routes
  - File: `src/main.py` (modify)
  - Import and include sessions router at /api/v1/sessions
  - Import and include discovery router at /api/v1/discovery
  - Purpose: Enable new endpoints
  - _Requirements: 1, 2, 4, 5_

### Testing Layer

- [x] 6.23. Write unit tests for SessionService
  - File: `tests/unit/test_session_service.py` (create)
  - Test create_session generates 64-char token
  - Test get_session_by_token returns correct session
  - Test update_session modifies fields
  - Test is_session_valid returns false for expired
  - Test claim_session transfers data correctly
  - Purpose: Verify session business logic
  - _Requirements: 1, 2, 4_

- [x] 6.24. Write unit tests for DiscoveryProfileService
  - File: `tests/unit/test_discovery_profile_service.py` (create)
  - Test get_or_create creates new profile
  - Test get_or_create returns existing profile
  - Test update modifies allowed fields
  - Test create_from_session copies all fields
  - Purpose: Verify discovery profile business logic
  - _Requirements: 5_

- [x] 6.25. Write integration tests for session endpoints
  - File: `tests/integration/test_session_routes.py` (create)
  - Test POST /sessions creates session and sets cookie
  - Test GET /sessions/me returns session with valid cookie
  - Test PUT /sessions/me updates session
  - Test POST /sessions/claim merges data
  - Purpose: Verify session API works end-to-end
  - _Requirements: 1, 2, 4_

- [x] 6.26. Write integration tests for discovery endpoints
  - File: `tests/integration/test_discovery_routes.py` (create)
  - Test GET /discovery returns profile for authenticated user
  - Test PUT /discovery updates profile
  - Test GET /discovery auto-creates if not exists
  - Purpose: Verify discovery API works end-to-end
  - _Requirements: 5_

- [x] 6.27. Write integration tests for session-owned conversations
  - File: `tests/integration/test_session_conversations.py` (create)
  - Test POST /conversations with session creates session-owned conversation
  - Test message sending works with session auth
  - Test conversation access denied for wrong session
  - Test conversation transfers on session claim
  - Purpose: Verify session conversation flow
  - _Requirements: 3, 7_

### Profile Extraction Layer (AI-Powered Auto-Population)

- [x] 6.28. Create extraction constants
  - File: `src/services/extraction_constants.py` (create)
  - Define DISCOVERY_QUESTIONS list with 25 questions (id, key, label, group)
  - Define QUESTION_BY_KEY lookup dict
  - Define VALID_QUESTION_KEYS set
  - Define EXTRACTION_SYSTEM_PROMPT for extraction instructions
  - Define EXTRACTION_USER_PROMPT template for context
  - Define EXTRACTION_SCHEMA for OpenAI structured JSON output
  - Purpose: Centralize extraction configuration aligned with frontend
  - _Requirements: 8_

- [x] 6.29. Implement ProfileExtractionService core methods
  - File: `src/services/profile_extraction_service.py` (create)
  - Implement extract_and_update() that:
    - Gets recent messages from conversation (last 10)
    - Gets current answers from session or discovery_profile
    - Calls OpenAI gpt-4o-mini with structured output schema
    - Validates extracted keys against QUESTION_BY_KEY
    - Merges new extractions with existing answers
    - Updates session or discovery_profile
  - Use low temperature (0.1) for consistent extraction
  - Return extracted_count, confidence, keys_extracted
  - Purpose: AI-powered profile data extraction
  - _Leverage: src/core/openai.py, src/services/session_service.py, src/services/discovery_profile_service.py_
  - _Requirements: 8_

- [x] 6.30. Add extraction validation and enrichment
  - File: `src/services/profile_extraction_service.py` (modify)
  - Implement _validate_and_enrich_answers() that:
    - Filters out unknown question keys
    - Skips answers without a value
    - Enriches with questionId, label, group from QUESTION_BY_KEY
  - Implement _update_target() that:
    - Updates session if session_id provided
    - Updates discovery_profile if profile_id provided
    - Handles ROI inputs (laborRate, manualMonthlySpend, manualMonthlyHours)
  - Purpose: Ensure data quality and proper targeting
  - _Requirements: 8_

- [x] 6.31. Integrate extraction in conversation message endpoint
  - File: `src/api/routes/conversations.py` (modify)
  - After generate_response(), call ProfileExtractionService.extract_and_update()
  - Pass conversation_id, session_id (from auth.session), profile_id (from auth.user)
  - Wrap in try/except - extraction failures should NOT fail message response
  - Log extracted fields on success, warn on failure
  - Purpose: Trigger extraction on every message
  - _Leverage: src/services/profile_extraction_service.py_
  - _Requirements: 8_

- [x] 6.32. Write unit tests for ProfileExtractionService
  - File: `tests/unit/test_profile_extraction_service.py` (create)
  - Test extract_and_update extracts facility size from conversation
  - Test returns zero when not enough messages
  - Test returns zero when no target provided
  - Test merges with existing answers
  - Test handles extraction failure gracefully
  - Test _validate_and_enrich_answers validates known keys
  - Test _validate_and_enrich_answers enriches with metadata
  - Test _validate_and_enrich_answers skips empty values
  - Test extracts ROI inputs when mentioned
  - Purpose: Verify extraction business logic
  - _Requirements: 8_

# Requirements Document: Sessions & Discovery Profiles

## Introduction

This specification defines the session management system for anonymous users and discovery profile storage for authenticated users. It enables users to interact with the Autopilot agent and build their procurement profile before signing up, with seamless data transfer when they authenticate.

## Alignment with Product Vision

Session and discovery management enables the Autopilot platform by providing:
- **Frictionless Onboarding**: Users can start chatting immediately without signup
- **Profile Building**: Discovery answers captured during conversation build user profiles
- **Seamless Conversion**: Session data auto-merges to profile on signup
- **Data Continuity**: Conversation history and ROI calculations preserved across authentication

## Requirements

### Requirement 1: Anonymous Session Creation

**User Story:** As an anonymous visitor, I want a session created automatically, so that my interactions are tracked without requiring signup.

#### Acceptance Criteria

1. WHEN a user without a session cookie visits THEN the system SHALL create a new session
2. WHEN a session is created THEN the system SHALL generate a unique session_token (64 chars)
3. WHEN a session is created THEN the system SHALL set an httpOnly, secure cookie
4. WHEN a session is created THEN the system SHALL set expiration to 30 days
5. WHEN a session is retrieved (GET /sessions/me) THEN the system SHALL return session data
6. IF a session cookie is invalid or expired THEN the system SHALL create a new session

### Requirement 2: Session Data Storage

**User Story:** As an anonymous user, I want my discovery answers and preferences saved to my session, so that I can continue where I left off.

#### Acceptance Criteria

1. WHEN a user updates their session (PUT /sessions/me) THEN the system SHALL store discovery answers
2. WHEN session is updated THEN the system SHALL store current_question_index and phase
3. WHEN session is updated THEN the system SHALL store roi_inputs if provided
4. WHEN session is updated THEN the system SHALL store selected_product_ids if provided
5. WHEN session is updated THEN the system SHALL store timeframe preference if provided
6. WHEN answers are stored THEN the system SHALL use the DiscoveryAnswer structure (questionId, key, label, value, group)
7. WHEN ROI inputs are stored THEN the system SHALL validate numeric fields

### Requirement 3: Session-Owned Conversations

**User Story:** As an anonymous user, I want my chat conversations linked to my session, so that I can continue chatting without an account.

#### Acceptance Criteria

1. WHEN an anonymous user creates a conversation THEN the system SHALL link it to their session
2. WHEN a session-owned conversation is accessed THEN the system SHALL verify session ownership
3. WHEN messages are sent THEN the system SHALL work for both session-owned and user-owned conversations
4. IF a session is claimed THEN the system SHALL transfer conversation ownership to the profile
5. IF an invalid session tries to access a conversation THEN the system SHALL return 403 Forbidden

### Requirement 4: Session Claim on Authentication

**User Story:** As a user who just signed up, I want my session data transferred to my profile, so that I don't lose my discovery progress.

#### Acceptance Criteria

1. WHEN a user calls POST /sessions/claim with valid JWT AND session cookie THEN the system SHALL merge session data
2. WHEN session is claimed THEN the system SHALL create or update the user's discovery_profile
3. WHEN session is claimed THEN the system SHALL transfer discovery answers, ROI inputs, and selections
4. WHEN session is claimed THEN the system SHALL transfer conversation ownership to the profile
5. WHEN session is claimed THEN the system SHALL mark session as claimed (claimed_by_profile_id set)
6. WHEN session is claimed THEN the system SHALL clear the session cookie
7. IF session is already claimed THEN the system SHALL return 400 Bad Request
8. IF session has no data to merge THEN the system SHALL still mark as claimed successfully

### Requirement 5: Discovery Profile for Authenticated Users

**User Story:** As an authenticated user, I want a discovery profile to store my procurement journey data, so that it persists across sessions.

#### Acceptance Criteria

1. WHEN an authenticated user requests discovery data (GET /discovery) THEN the system SHALL return their discovery_profile
2. IF no discovery_profile exists THEN the system SHALL create one on first access
3. WHEN a user updates discovery data (PUT /discovery) THEN the system SHALL update their discovery_profile
4. WHEN discovery_profile is updated THEN the system SHALL store all discovery session fields
5. WHEN discovery_profile is queried THEN the system SHALL return answers, roi_inputs, phase, and selections

### Requirement 6: Phase Enum Alignment

**User Story:** As a developer, I want consistent phase values between frontend and backend, so that state management is straightforward.

#### Acceptance Criteria

1. WHEN storing phase THEN the system SHALL use values: 'discovery', 'roi', 'greenlight'
2. WHEN migrating existing data THEN the system SHALL convert 'selection' to 'greenlight'
3. WHEN migrating existing data THEN the system SHALL convert 'completed' to 'greenlight'
4. WHEN validating phase input THEN the system SHALL reject invalid phase values

### Requirement 7: Dual Authentication Support

**User Story:** As a developer, I want endpoints to support both authenticated users and anonymous sessions, so that the same API works for both.

#### Acceptance Criteria

1. WHEN a request has a valid JWT THEN the system SHALL treat as authenticated user
2. WHEN a request has no JWT but valid session cookie THEN the system SHALL treat as anonymous session
3. WHEN a request has both JWT and session cookie THEN the system SHALL prefer JWT authentication
4. WHEN neither auth method is present THEN the system SHALL create a new session (for session-supporting endpoints)
5. WHEN implementing dual auth THEN the system SHALL provide a reusable dependency

### Requirement 8: AI-Powered Profile Extraction

**User Story:** As a user chatting with the agent, I want my discovery profile to be automatically populated from my conversation, so that I don't have to manually fill out forms.

#### Acceptance Criteria

1. WHEN a message is sent to a conversation THEN the system SHALL extract discovery data from recent messages
2. WHEN extracting data THEN the system SHALL use OpenAI structured output with gpt-4o-mini
3. WHEN extracting data THEN the system SHALL only extract EXPLICITLY stated information
4. WHEN extracting data THEN the system SHALL validate against the 25 known question keys
5. WHEN extracting data THEN the system SHALL merge new extractions with existing answers
6. WHEN extracting data THEN the system SHALL update sessions (anonymous) or discovery_profiles (authenticated)
7. WHEN ROI inputs are mentioned THEN the system SHALL extract laborRate, manualMonthlySpend, manualMonthlyHours
8. IF extraction fails THEN the system SHALL NOT fail the message response
9. IF conversation has fewer than 2 messages THEN the system SHALL skip extraction
10. WHEN extraction succeeds THEN the system SHALL log the extracted keys

#### Extraction Questions (25 total)

| Group | Keys |
|-------|------|
| Company | company_name, priorities, stakeholders |
| Facility | background, fnb, courts_count, surfaces, sqft, lifecycle |
| Operations | method, responsibility, frequency, timing, duration, challenges, failure_impact |
| Economics | budget_exists, monthly_spend, opportunity_cost |
| Context | feedback, confidence, past_attempts, ideal_timeline, upcoming_events, business_challenges |

## Non-Functional Requirements

### Performance
- Session lookup by token SHALL complete in under 20ms
- Session creation SHALL complete in under 50ms
- Cookie validation SHALL add under 5ms to request time

### Security
- Session tokens SHALL be cryptographically random (64 characters)
- Session cookies SHALL be httpOnly, secure, and SameSite=Lax
- Session data SHALL only be accessible with matching session_token
- Expired sessions SHALL not be accessible

### Reliability
- Session creation SHALL be idempotent if same token used
- Session claim SHALL be atomic (all-or-nothing transfer)
- Expired session cleanup SHALL run periodically without affecting active sessions

### Scalability
- Sessions table SHALL support millions of rows efficiently
- Session token index SHALL be optimized for quick lookups
- Expired sessions SHALL be cleaned up to prevent table bloat

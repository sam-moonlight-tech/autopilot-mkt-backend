# Requirements Document: Conversations

## Introduction

This specification defines the conversation management system for the Autopilot backend. It establishes CRUD operations for conversations, message storage and retrieval, OpenAI GPT-4o integration for agent responses, and context window reconstruction from conversation history. This is the core feature that enables the agent-led procurement experience.

## Alignment with Product Vision

The conversations system enables the Autopilot platform by providing:
- **Agent-Led Experience**: GPT-4o powered agent guides buyers through procurement
- **Conversation Continuity**: Full history storage enables resuming sessions
- **Structured Data**: Conversation phases and metadata capture decision progress
- **Team Collaboration**: Company-associated conversations enable team sharing

## Requirements

### Requirement 1: Conversation Creation

**User Story:** As a user, I want to start a new conversation, so that I can begin the agent-led procurement process.

#### Acceptance Criteria

1. WHEN a user creates a conversation (POST /conversations) THEN the system SHALL create a new conversation record
2. WHEN a conversation is created THEN the system SHALL store user_id, optional company_id, title, phase, and metadata
3. WHEN a conversation is created THEN the system SHALL set initial phase to "discovery"
4. WHEN a conversation is created THEN the system SHALL generate a default title if not provided
5. IF company_id is provided THEN the system SHALL verify the user is a member of that company

### Requirement 2: Conversation Listing

**User Story:** As a user, I want to see my previous conversations, so that I can resume or review them.

#### Acceptance Criteria

1. WHEN a user requests conversations (GET /conversations) THEN the system SHALL return conversations they own
2. WHEN a user is a company member THEN the system SHALL also return company conversations they have access to
3. WHEN listing conversations THEN the system SHALL include message count and last message timestamp
4. WHEN listing conversations THEN the system SHALL support pagination with cursor-based approach
5. WHEN listing conversations THEN the system SHALL order by most recently updated first

### Requirement 3: Conversation Retrieval and Deletion

**User Story:** As a user, I want to view and delete my conversations, so that I can manage my conversation history.

#### Acceptance Criteria

1. WHEN a user requests a conversation (GET /conversations/{id}) THEN the system SHALL return the conversation if they have access
2. WHEN a user deletes a conversation (DELETE /conversations/{id}) THEN the system SHALL soft-delete or hard-delete the record
3. IF a user tries to access a conversation they don't own THEN the system SHALL return 403 Forbidden
4. IF a user tries to access a non-existent conversation THEN the system SHALL return 404 Not Found

### Requirement 4: Message Creation with Agent Response

**User Story:** As a user, I want to send messages and receive agent responses, so that I can interact with the procurement assistant.

#### Acceptance Criteria

1. WHEN a user sends a message (POST /conversations/{id}/messages) THEN the system SHALL store the user message
2. WHEN a user message is stored THEN the system SHALL trigger an agent response using OpenAI
3. WHEN generating an agent response THEN the system SHALL reconstruct context from conversation history
4. WHEN generating an agent response THEN the system SHALL include relevant product information from RAG (if available)
5. WHEN an agent response is generated THEN the system SHALL store it as a new message with role "assistant"
6. WHEN responding THEN the system SHALL return both the user message and agent response

### Requirement 5: Message History Retrieval

**User Story:** As a user, I want to view all messages in a conversation, so that I can review the conversation history.

#### Acceptance Criteria

1. WHEN a user requests messages (GET /conversations/{id}/messages) THEN the system SHALL return all messages in chronological order
2. WHEN returning messages THEN the system SHALL include role, content, metadata, and created_at
3. WHEN returning messages THEN the system SHALL support pagination for long conversations
4. IF messages contain structured data THEN the system SHALL include it in the metadata field

### Requirement 6: Context Window Reconstruction

**User Story:** As the agent, I need conversation context to generate relevant responses, so that I can maintain coherent conversations.

#### Acceptance Criteria

1. WHEN generating an agent response THEN the system SHALL load recent conversation history
2. WHEN reconstructing context THEN the system SHALL include a system prompt defining the agent persona
3. WHEN reconstructing context THEN the system SHALL respect token limits (e.g., last N messages or summarization)
4. WHEN reconstructing context THEN the system SHALL include conversation phase in system prompt
5. WHEN RAG results are available THEN the system SHALL inject relevant product context

### Requirement 7: Conversation Phase Management

**User Story:** As a system, I want to track conversation phases, so that the agent can guide users through the procurement journey.

#### Acceptance Criteria

1. WHEN a conversation progresses THEN the system SHALL update the phase field
2. WHEN the phase is updated THEN the system SHALL record the transition in metadata
3. WHEN the agent determines phase change THEN the system SHALL accept phase updates via metadata
4. WHEN listing conversations THEN the system SHALL include current phase

### Requirement 8: Session-Owned Conversations (NEW)

**User Story:** As an anonymous user, I want to chat with the agent without signing up, so that I can explore the platform before committing.

#### Acceptance Criteria

1. WHEN an anonymous user creates a conversation THEN the system SHALL link it to their session_id
2. WHEN a session-owned conversation exists THEN the system SHALL make user_id nullable
3. WHEN accessing a conversation THEN the system SHALL verify either user_id or session_id ownership
4. IF a session is claimed THEN the system SHALL transfer conversation ownership to the profile
5. WHEN ownership transfers THEN the system SHALL update user_id and clear session_id
6. WHEN listing conversations THEN the system SHALL include session-owned conversations for valid sessions

### Requirement 9: Phase Enum Alignment (UPDATE)

**User Story:** As a developer, I want consistent phase values between frontend and backend, so that the user journey is seamless.

#### Acceptance Criteria

1. WHEN storing phase THEN the system SHALL use values: 'discovery', 'roi', 'greenlight'
2. WHEN phase was previously 'selection' or 'completed' THEN the system SHALL migrate to 'greenlight'
3. WHEN validating phase input THEN the system SHALL reject 'selection' and 'completed' values
4. WHEN agent prompts reference phases THEN the system SHALL use 'greenlight' for final phase

## Non-Functional Requirements

### Performance
- Message creation SHALL complete in under 10 seconds (including agent response)
- Message history retrieval SHALL complete in under 100ms for up to 100 messages
- Context reconstruction SHALL complete in under 500ms

### Security
- Users SHALL only access their own conversations or company conversations they're members of
- Message content SHALL be stored encrypted at rest (Supabase default)
- OpenAI API keys SHALL never be exposed in responses

### Reliability
- Message creation SHALL be atomic (user message + agent response)
- Failed agent responses SHALL not lose the user message
- System SHALL handle OpenAI API rate limits gracefully

### Usability
- Error messages SHALL clearly indicate conversation access issues
- Agent responses SHALL be well-formatted and contextually relevant
- Conversation phases SHALL be human-readable

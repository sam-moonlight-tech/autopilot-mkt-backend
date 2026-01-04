# Implementation Plan: Conversations

## Task Overview

This implementation plan establishes the conversation system with OpenAI integration. Tasks build from database schema through services to routes, with agent integration last to allow testing of CRUD operations first.

## Steering Document Compliance

- Files follow `structure.md` directory layout
- Uses snake_case for modules, PascalCase for classes
- Follows layered architecture: routes → services → models

## Atomic Task Requirements

**Each task meets these criteria:**
- **File Scope**: Touches 1-3 related files maximum
- **Time Boxing**: Completable in 15-30 minutes
- **Single Purpose**: One testable outcome per task
- **Specific Files**: Exact file paths specified
- **Agent-Friendly**: Clear input/output with minimal context switching

## Tasks

- [ ] 4.1. Create conversations and messages tables migration
  - File: `supabase/migrations/003_create_conversations.sql` (create)
  - Define conversations table with user_id, company_id, title, phase, metadata, timestamps
  - Define messages table with conversation_id, role, content, metadata, created_at
  - Add indexes for performance (user_id, company_id, conversation_id)
  - Enable RLS with appropriate access policies
  - Purpose: Establish conversation data storage
  - _Requirements: 1, 3, 5_

- [ ] 4.2. Create conversation model type hints
  - File: `src/models/conversation.py` (create)
  - Define Conversation TypedDict with all table columns
  - Define ConversationPhase literal type for valid phases
  - Purpose: Type-safe conversation data handling
  - _Requirements: 1, 7_

- [ ] 4.3. Create message model type hints
  - File: `src/models/message.py` (create)
  - Define Message TypedDict with all table columns
  - Define MessageRole literal type ("user", "assistant", "system")
  - Purpose: Type-safe message data handling
  - _Requirements: 4, 5_

- [ ] 4.4. Create conversation Pydantic schemas
  - File: `src/schemas/conversation.py` (create)
  - Define ConversationCreate with optional title, company_id, metadata
  - Define ConversationResponse with all fields plus message_count
  - Define ConversationListResponse with pagination
  - Define ConversationUpdate for phase changes
  - Purpose: API request/response contracts for conversations
  - _Requirements: 1, 2, 7_

- [ ] 4.5. Create message Pydantic schemas
  - File: `src/schemas/message.py` (create)
  - Define MessageCreate with content and optional metadata
  - Define MessageResponse with all fields
  - Define MessageWithAgentResponse for combined response
  - Define MessageListResponse with pagination
  - Purpose: API request/response contracts for messages
  - _Requirements: 4, 5_

- [ ] 4.6. Implement OpenAI client singleton
  - File: `src/core/openai.py` (create)
  - Create get_openai_client() function returning OpenAI client
  - Use API key from settings
  - Implement singleton pattern with module-level caching
  - Purpose: Centralized OpenAI client access
  - _Leverage: src/core/config.py for settings_
  - _Requirements: 4_

- [ ] 4.7. Add OpenAI settings to configuration
  - File: `src/core/config.py` (modify)
  - Add openai_api_key field to Settings
  - Add openai_model field with default "gpt-4o"
  - Add max_context_messages field with default 20
  - Purpose: Configure OpenAI integration
  - _Leverage: existing Settings class_
  - _Requirements: 4, 6_

- [ ] 4.8. Implement ConversationService core methods
  - File: `src/services/conversation_service.py` (create)
  - Implement create_conversation() with default title and phase
  - Implement get_conversation() for fetching by id
  - Implement can_access() checking ownership and company membership
  - Purpose: Core conversation business logic
  - _Leverage: src/core/supabase.py, src/services/company_service.py_
  - _Requirements: 1, 3_

- [ ] 4.9. Add listing and deletion to ConversationService
  - File: `src/services/conversation_service.py` (modify)
  - Implement list_conversations() with cursor pagination
  - Include message count and last message timestamp
  - Implement delete_conversation() for removing conversations
  - Purpose: Complete conversation CRUD operations
  - _Leverage: existing ConversationService_
  - _Requirements: 2, 3_

- [ ] 4.10. Add message operations to ConversationService
  - File: `src/services/conversation_service.py` (modify)
  - Implement add_message() for storing messages
  - Implement get_messages() with pagination
  - Implement get_recent_messages() for context building
  - Purpose: Message storage and retrieval
  - _Leverage: existing ConversationService_
  - _Requirements: 4, 5_

- [ ] 4.11. Implement AgentService system prompts
  - File: `src/services/agent_service.py` (create)
  - Define SYSTEM_PROMPTS dict for each phase (discovery, roi, selection)
  - Implement get_system_prompt() returning phase-appropriate prompt
  - Include agent persona and guidelines
  - Purpose: Configure agent behavior by phase
  - _Requirements: 6, 7_

- [ ] 4.12. Implement AgentService context building
  - File: `src/services/agent_service.py` (modify)
  - Implement build_context() to create OpenAI messages array
  - Load recent messages from conversation history
  - Include system prompt at the beginning
  - Respect max_context_messages limit
  - Purpose: Prepare context for OpenAI API
  - _Leverage: src/services/conversation_service.py_
  - _Requirements: 6_

- [ ] 4.13. Implement AgentService response generation
  - File: `src/services/agent_service.py` (modify)
  - Implement generate_response() orchestration method
  - Store user message first
  - Build context and call OpenAI API
  - Store and return agent response
  - Handle OpenAI errors gracefully
  - Purpose: Complete agent interaction flow
  - _Leverage: src/core/openai.py, src/services/conversation_service.py_
  - _Requirements: 4_

- [ ] 4.14. Create conversation routes (CRUD)
  - File: `src/api/routes/conversations.py` (create)
  - Implement POST /conversations for creation
  - Implement GET /conversations for listing
  - Implement GET /conversations/{id} for single conversation
  - Implement DELETE /conversations/{id} for deletion
  - Add permission checks using can_access()
  - Purpose: Conversation API endpoints
  - _Leverage: src/api/deps.py, src/services/conversation_service.py_
  - _Requirements: 1, 2, 3_

- [ ] 4.15. Create message routes
  - File: `src/api/routes/conversations.py` (modify)
  - Implement POST /conversations/{id}/messages for sending messages
  - Implement GET /conversations/{id}/messages for history
  - Return both user and agent messages from POST
  - Add conversation access verification
  - Purpose: Message API endpoints
  - _Leverage: src/services/agent_service.py_
  - _Requirements: 4, 5_

- [ ] 4.16. Register conversation routes in main
  - File: `src/main.py` (modify)
  - Import and include conversations router at /api/v1/conversations
  - Purpose: Enable conversation endpoints
  - _Leverage: existing main.py router setup_
  - _Requirements: 1, 2, 3, 4, 5_

- [ ] 4.17. Update requirements.txt with OpenAI dependency
  - File: `requirements.txt` (modify)
  - Add openai>=1.0.0
  - Purpose: Ensure OpenAI SDK is installed
  - _Leverage: existing requirements.txt_
  - _Requirements: 4_

- [ ] 4.18. Write unit tests for ConversationService
  - File: `tests/unit/test_conversation_service.py` (create)
  - Test create_conversation sets defaults
  - Test can_access with owner and company member
  - Test list_conversations pagination
  - Purpose: Verify conversation business logic
  - _Requirements: 1, 2, 3_

- [ ] 4.19. Write unit tests for AgentService
  - File: `tests/unit/test_agent_service.py` (create)
  - Test get_system_prompt returns correct prompt for phase
  - Test build_context includes system prompt and history
  - Test build_context respects message limit
  - Mock OpenAI client for generate_response tests
  - Purpose: Verify agent logic
  - _Requirements: 4, 6_

- [ ] 4.20. Write integration tests for conversation endpoints
  - File: `tests/integration/test_conversation_routes.py` (create)
  - Test POST /conversations creates conversation
  - Test GET /conversations returns user's conversations
  - Test GET /conversations/{id} returns single conversation
  - Test DELETE /conversations/{id} removes conversation
  - Purpose: Verify conversation API end-to-end
  - _Requirements: 1, 2, 3_

- [ ] 4.21. Write integration tests for message endpoints
  - File: `tests/integration/test_message_routes.py` (create)
  - Test POST /conversations/{id}/messages with mocked OpenAI
  - Test GET /conversations/{id}/messages returns history
  - Test message creation stores both user and agent messages
  - Purpose: Verify message API end-to-end
  - _Requirements: 4, 5_

"""Conversation API routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import AuthContext, CurrentUser, DualAuth, SessionRateLimit
from src.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
    CurrentConversationResponse,
)
from src.models.conversation import ConversationPhase
from src.schemas.message import (
    DiscoveryState,
    MessageCreate,
    MessageListResponse,
    MessageWithAgentResponse,
)
from src.services.extraction_constants import REQUIRED_QUESTION_KEYS
from src.services.agent_service import AgentService
from src.services.company_service import CompanyService
from src.services.conversation_service import ConversationService
from src.services.discovery_profile_service import DiscoveryProfileService
from src.services.profile_extraction_service import ProfileExtractionService
from src.services.profile_service import ProfileService
from src.services.session_service import SessionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def _get_user_profile_id(user: CurrentUser) -> UUID:
    """Get the profile ID for a user, creating profile if needed."""
    service = ProfileService()
    profile = await service.get_or_create_profile(user.user_id, user.email)
    return UUID(profile["id"])


async def _check_conversation_access(
    conversation_id: UUID,
    auth: AuthContext,
) -> None:
    """Check if user or session can access the conversation."""
    service = ConversationService()

    if auth.is_authenticated and auth.user:
        # Get profile ID for authenticated user
        profile_service = ProfileService()
        profile = await profile_service.get_or_create_profile(
            auth.user.user_id, auth.user.email
        )
        if not await service.can_access(
            conversation_id, profile_id=UUID(profile["id"])
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this conversation",
            )
    elif auth.session:
        # Check session ownership
        if not await service.can_access(
            conversation_id, session_id=auth.session.session_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this conversation",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )


# Conversation CRUD endpoints


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a conversation",
    description="Creates a new conversation for authenticated user or anonymous session.",
)
async def create_conversation(
    auth: DualAuth,
    data: ConversationCreate | None = None,
) -> ConversationResponse:
    """Create a new conversation.

    Works for both authenticated users and anonymous sessions.

    Args:
        auth: Dual auth context (user or session).
        data: Optional conversation creation data.

    Returns:
        ConversationResponse: The created conversation.
    """
    service = ConversationService()
    session_service = SessionService()

    if auth.is_authenticated and auth.user:
        # Authenticated user - create user-owned conversation
        profile_id = await _get_user_profile_id(auth.user)
        conversation = await service.create_conversation(profile_id, data)
    elif auth.session:
        # Anonymous session - create session-owned conversation
        conversation = await service.create_conversation_for_session(
            session_id=auth.session.session_id,
            title=data.title if data else None,
            metadata=data.metadata if data else None,
        )
        # Link conversation to session
        await session_service.set_conversation(
            auth.session.session_id, UUID(conversation["id"])
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return ConversationResponse(
        id=conversation["id"],
        profile_id=conversation.get("profile_id"),
        company_id=conversation.get("company_id"),
        title=conversation["title"],
        phase=conversation["phase"],
        metadata=conversation.get("metadata", {}),
        message_count=0,
        last_message_at=None,
        created_at=conversation["created_at"],
        updated_at=conversation["updated_at"],
    )


@router.post(
    "/reset",
    response_model=CurrentConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a fresh conversation",
    description="Creates a new conversation, leaving old ones accessible. Use this for 'start over' functionality.",
)
async def reset_conversation(
    auth: DualAuth,
) -> CurrentConversationResponse:
    """Start a fresh conversation (soft reset).

    Creates a new conversation while keeping old ones accessible.
    The new conversation becomes the 'current' one.

    For authenticated users:
    - Creates new conversation with discovery profile context
    - Old conversations remain in list

    For anonymous sessions:
    - Creates new conversation linked to session
    - Old conversations remain accessible

    Args:
        auth: Dual auth context (user or session).

    Returns:
        CurrentConversationResponse: The new conversation with initial greeting.
    """
    conversation_service = ConversationService()
    session_service = SessionService()

    conversation: dict
    context: dict = {}
    profile_id: UUID | None = None

    if auth.is_authenticated and auth.user:
        # Authenticated user flow
        profile_service = ProfileService()
        discovery_service = DiscoveryProfileService()
        company_service = CompanyService()

        # Get user profile
        profile = await profile_service.get_or_create_profile(
            auth.user.user_id, auth.user.email
        )
        profile_id = UUID(profile["id"])

        # Get discovery profile for context
        discovery_profile = await discovery_service.get_by_profile_id(profile_id)
        if discovery_profile:
            answers = discovery_profile.get("answers", {})
            if answers:
                context["discovery_answers"] = answers
                if "company_name" in answers:
                    context["company_name"] = answers["company_name"].get("value")

        # Get user's company for context
        company = await company_service.get_user_company(profile_id)
        company_id = UUID(company["id"]) if company else None
        if company:
            context["company_name"] = company.get("name")
            context["company_id"] = company["id"]

        # Create fresh conversation
        conversation = await conversation_service.create_fresh_for_profile(
            profile_id=profile_id,
            company_id=company_id,
            context=context,
        )
        logger.info("Created fresh conversation %s for profile %s", conversation["id"], profile_id)

    elif auth.session:
        # Anonymous session flow
        session = await session_service.get_session_by_id(auth.session.session_id)

        if session:
            answers = session.get("answers", {})
            if answers:
                context["discovery_answers"] = answers
                if "company_name" in answers:
                    context["company_name"] = answers["company_name"].get("value")

        # Create fresh conversation
        conversation = await conversation_service.create_fresh_for_session(
            session_id=auth.session.session_id,
            context=context,
        )

        # Link new conversation to session
        await session_service.set_conversation(
            auth.session.session_id, UUID(conversation["id"])
        )
        logger.info("Created fresh conversation %s for session %s", conversation["id"], auth.session.session_id)

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Generate initial greeting for the new conversation
    messages_data = []
    try:
        agent_service = AgentService()
        session_id_for_greeting = auth.session.session_id if auth.session else None

        await agent_service.generate_initial_greeting(
            conversation_id=UUID(conversation["id"]),
            session_id=session_id_for_greeting,
            profile_id=profile_id,
        )

        # Fetch the greeting message
        messages_data, _, _ = await conversation_service.get_messages(
            UUID(conversation["id"]), limit=50
        )
    except Exception as e:
        logger.warning("Failed to generate initial greeting for reset: %s", str(e))

    messages = [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "metadata": m.metadata if hasattr(m, 'metadata') and m.metadata else None,
        }
        for m in messages_data
    ]

    return CurrentConversationResponse(
        conversation=ConversationResponse(
            id=conversation["id"],
            profile_id=conversation.get("profile_id"),
            company_id=conversation.get("company_id"),
            title=conversation["title"],
            phase=conversation["phase"],
            metadata=conversation.get("metadata", {}),
            message_count=len(messages_data),
            last_message_at=messages_data[-1].created_at if messages_data else None,
            created_at=conversation["created_at"],
            updated_at=conversation["updated_at"],
        ),
        is_new=True,
        messages=messages,
    )


@router.get(
    "/current",
    response_model=CurrentConversationResponse,
    summary="Get or create current conversation",
    description="Returns the current active conversation with context. Creates one if none exists. Includes recent messages for resuming chat.",
)
async def get_current_conversation(
    auth: DualAuth,
) -> CurrentConversationResponse:
    """Get or create the current conversation with context.

    For authenticated users:
    - Returns most recent conversation or creates new one
    - Injects discovery profile context (company name, answers)

    For anonymous sessions:
    - Returns session's linked conversation or creates new one
    - Injects session answers as context

    Args:
        auth: Dual auth context (user or session).

    Returns:
        CurrentConversationResponse: Conversation, messages, and is_new flag.
    """
    conversation_service = ConversationService()
    session_service = SessionService()

    conversation: dict
    is_new: bool
    context: dict = {}
    profile_id: UUID | None = None  # Will be set for authenticated users

    if auth.is_authenticated and auth.user:
        # Authenticated user flow
        profile_service = ProfileService()
        discovery_service = DiscoveryProfileService()
        company_service = CompanyService()

        # Get user profile
        profile = await profile_service.get_or_create_profile(
            auth.user.user_id, auth.user.email
        )
        profile_id = UUID(profile["id"])

        # Get discovery profile for context
        discovery_profile = await discovery_service.get_by_profile_id(profile_id)
        logger.info(
            "Current conversation: profile_id=%s, discovery_profile_found=%s",
            profile_id,
            discovery_profile is not None,
        )
        if discovery_profile:
            answers = discovery_profile.get("answers", {})
            logger.info(
                "Discovery profile answers: count=%d, keys=%s",
                len(answers) if answers else 0,
                list(answers.keys()) if answers else [],
            )
            if answers:
                context["discovery_answers"] = answers
                # Extract company name if available
                if "company_name" in answers:
                    context["company_name"] = answers["company_name"].get("value")
        else:
            logger.warning("No discovery profile found for profile_id=%s", profile_id)

        # Get user's company for context
        company = await company_service.get_user_company(profile_id)
        company_id = UUID(company["id"]) if company else None
        if company:
            context["company_name"] = company.get("name")
            context["company_id"] = company["id"]

        # Get or create conversation (context only used if creating new)
        conversation, is_new = await conversation_service.get_or_create_current_for_profile(
            profile_id=profile_id,
            company_id=company_id,
            context=context,
        )
    elif auth.session:
        # Anonymous session flow
        session = await session_service.get_session_by_id(auth.session.session_id)

        if session:
            answers = session.get("answers", {})
            if answers:
                context["discovery_answers"] = answers
                if "company_name" in answers:
                    context["company_name"] = answers["company_name"].get("value")

        # Get or create conversation (context only used if creating new)
        conversation, is_new = await conversation_service.get_or_create_current_for_session(
            session_id=auth.session.session_id,
            context=context,
        )

        # Link conversation to session if new
        if is_new:
            await session_service.set_conversation(
                auth.session.session_id, UUID(conversation["id"])
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    # Get recent messages for chat history
    messages_data, _, _ = await conversation_service.get_messages(
        UUID(conversation["id"]), limit=50
    )

    # Generate initial greeting for new conversations OR existing conversations with no messages
    # (handles migration from old frontend-only greetings)
    if is_new or len(messages_data) == 0:
        try:
            agent_service = AgentService()
            session_id_for_greeting = auth.session.session_id if auth.session else None

            # Extract source context from request if available (for future use)
            source_context = context.get("source_context")

            await agent_service.generate_initial_greeting(
                conversation_id=UUID(conversation["id"]),
                session_id=session_id_for_greeting,
                profile_id=profile_id,  # None for anonymous, UUID for authenticated
                source_context=source_context,
            )
            logger.info(
                "Generated initial greeting for conversation %s (is_new=%s, had_messages=%s)",
                conversation["id"],
                is_new,
                len(messages_data) > 0,
            )

            # Re-fetch messages after generating greeting
            messages_data, _, _ = await conversation_service.get_messages(
                UUID(conversation["id"]), limit=50
            )
        except Exception as e:
            logger.warning("Failed to generate initial greeting: %s", str(e), exc_info=True)
            # Continue without greeting - frontend can handle empty messages
    messages = [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "metadata": m.metadata if hasattr(m, 'metadata') and m.metadata else None,
        }
        for m in messages_data
    ]

    # Get message count
    message_count = len(messages_data)

    return CurrentConversationResponse(
        conversation=ConversationResponse(
            id=conversation["id"],
            profile_id=conversation.get("profile_id"),
            company_id=conversation.get("company_id"),
            title=conversation["title"],
            phase=conversation["phase"],
            metadata=conversation.get("metadata", {}),
            message_count=message_count,
            last_message_at=messages_data[-1].created_at if messages_data else None,
            created_at=conversation["created_at"],
            updated_at=conversation["updated_at"],
        ),
        is_new=is_new,
        messages=messages,
    )


@router.get(
    "",
    response_model=ConversationListResponse,
    summary="List conversations",
    description="Returns paginated list of user's conversations.",
)
async def list_conversations(
    user: CurrentUser,
    company_id: UUID | None = Query(default=None, description="Filter by company"),
    cursor: str | None = Query(default=None, description="Pagination cursor"),
    limit: int = Query(default=20, ge=1, le=100, description="Results per page"),
) -> ConversationListResponse:
    """List conversations for the authenticated user.

    Args:
        user: The authenticated user context.
        company_id: Optional company filter.
        cursor: Pagination cursor.
        limit: Maximum results per page.

    Returns:
        ConversationListResponse: Paginated list of conversations.
    """
    profile_id = await _get_user_profile_id(user)
    service = ConversationService()

    conversations, next_cursor, has_more = await service.list_conversations(
        profile_id=profile_id,
        company_id=company_id,
        cursor=cursor,
        limit=limit,
    )

    return ConversationListResponse(
        conversations=conversations,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation",
    description="Returns a single conversation by ID.",
)
async def get_conversation(
    conversation_id: UUID,
    auth: DualAuth,
) -> ConversationResponse:
    """Get a conversation by ID.

    Args:
        conversation_id: The conversation's UUID.
        auth: Dual auth context (user or session).

    Returns:
        ConversationResponse: The conversation.

    Raises:
        HTTPException: 404 if not found, 403 if no access.
    """
    service = ConversationService()

    conversation = await service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    await _check_conversation_access(conversation_id, auth)

    # Get message count
    messages, _, _ = await service.get_messages(conversation_id, limit=1)
    message_count = len(messages)  # Simplified - could be more accurate

    return ConversationResponse(
        id=conversation["id"],
        profile_id=conversation.get("profile_id"),
        company_id=conversation.get("company_id"),
        title=conversation["title"],
        phase=conversation["phase"],
        metadata=conversation.get("metadata", {}),
        message_count=message_count,
        last_message_at=None,
        created_at=conversation["created_at"],
        updated_at=conversation["updated_at"],
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation",
    description="Deletes a conversation and all its messages.",
)
async def delete_conversation(
    conversation_id: UUID,
    user: CurrentUser,
) -> None:
    """Delete a conversation.

    Args:
        conversation_id: The conversation's UUID.
        user: The authenticated user context.

    Raises:
        HTTPException: 404 if not found, 403 if no access.
    """
    profile_id = await _get_user_profile_id(user)
    service = ConversationService()

    conversation = await service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Only owner can delete
    if conversation["profile_id"] != str(profile_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the conversation owner can delete it",
        )

    await service.delete_conversation(conversation_id)


# Message endpoints


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageWithAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send message",
    description="Sends a message and receives an agent response. Rate limited to 15 messages per minute for anonymous sessions.",
    responses={
        429: {
            "description": "Rate limit exceeded (anonymous sessions only)",
            "headers": {
                "Retry-After": {
                    "description": "Seconds until rate limit resets",
                    "schema": {"type": "integer"},
                },
                "X-RateLimit-Limit": {
                    "description": "Maximum requests per window",
                    "schema": {"type": "integer"},
                },
                "X-RateLimit-Remaining": {
                    "description": "Remaining requests in current window",
                    "schema": {"type": "integer"},
                },
            },
        }
    },
)
async def send_message(
    conversation_id: UUID,
    data: MessageCreate,
    auth: DualAuth,
    _rate_limit: SessionRateLimit,
) -> MessageWithAgentResponse:
    """Send a message to a conversation and get agent response.

    Works for both authenticated users and anonymous sessions.
    Rate limited to 15 messages per minute for anonymous sessions.

    During discovery phase, returns intelligent chips and discovery state.

    Args:
        conversation_id: The conversation's UUID.
        data: Message content.
        auth: Dual auth context (user or session).
        _rate_limit: Rate limit check (enforced for sessions only).

    Returns:
        MessageWithAgentResponse: User message, agent message, chips, and discovery state.

    Raises:
        HTTPException: 404 if not found, 403 if no access, 429 if rate limited.
    """
    await _check_conversation_access(conversation_id, auth)

    # Get conversation to check phase
    conversation_service = ConversationService()
    conversation = await conversation_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    phase = ConversationPhase(conversation["phase"])
    session_id = auth.session.session_id if auth.session else None
    profile_id = None
    if auth.is_authenticated and auth.user:
        profile_id = await _get_user_profile_id(auth.user)

    agent_service = AgentService()
    chips: list[str] = []
    discovery_state: DiscoveryState | None = None

    # Use intelligent discovery response for discovery phase
    if phase == ConversationPhase.DISCOVERY:
        result = await agent_service.generate_discovery_response(
            conversation_id=conversation_id,
            user_message=data.content,
            session_id=session_id,
            profile_id=profile_id,
            metadata=data.metadata,
        )

        user_message = result["user_message"]
        agent_message = result["agent_message"]
        chips = result["chips"]

        # Build discovery state from session or discovery profile
        current_answers: dict = {}
        if profile_id:
            # Authenticated user - get answers from discovery profile
            discovery_service = DiscoveryProfileService()
            discovery_profile = await discovery_service.get_by_profile_id(profile_id)
            if discovery_profile:
                current_answers = discovery_profile.get("answers", {})
        elif session_id:
            # Anonymous user - get answers from session
            session_service = SessionService()
            session = await session_service.get_session_by_id(session_id)
            if session:
                current_answers = session.get("answers", {})

        answered_keys = list(current_answers.keys())
        missing_keys = [k for k in REQUIRED_QUESTION_KEYS if k not in current_answers]
        progress = int((len(answered_keys) / len(REQUIRED_QUESTION_KEYS)) * 100) if REQUIRED_QUESTION_KEYS else 0

        discovery_state = DiscoveryState(
            ready_for_roi=result["ready_for_roi"],
            answered_keys=answered_keys,
            missing_keys=missing_keys,
            progress_percent=min(progress, 100),
        )
    else:
        # ROI/Greenlight phases use standard response
        user_message, agent_message = await agent_service.generate_response(
            conversation_id=conversation_id,
            user_message=data.content,
            metadata=data.metadata,
        )

    # Trigger profile extraction after agent response (non-blocking on failure)
    # This updates the stored answers for future messages and ROI calculations
    try:
        extraction_service = ProfileExtractionService()
        extraction_result = await extraction_service.extract_and_update(
            conversation_id=conversation_id,
            session_id=session_id,
            profile_id=profile_id,
        )
        if extraction_result.get("extracted_count", 0) > 0:
            logger.info(
                "Extracted %d fields from conversation %s: %s",
                extraction_result["extracted_count"],
                conversation_id,
                extraction_result.get("keys_extracted", []),
            )
    except Exception as e:
        # Log but don't fail the response - extraction is enhancement, not critical
        logger.warning("Profile extraction failed for conversation %s: %s", conversation_id, e)

    return MessageWithAgentResponse(
        user_message=user_message,
        agent_message=agent_message,
        chips=chips,
        discovery_state=discovery_state,
    )


@router.post(
    "/{conversation_id}/transition",
    summary="Generate phase transition message",
    description="Generates a dynamic AI message for phase transitions (discovery→ROI or ROI→greenlight).",
)
async def generate_transition_message(
    conversation_id: UUID,
    auth: DualAuth,
    transition_type: str = Query(
        ...,
        description="Type of transition: 'discovery_to_roi' or 'roi_to_greenlight'",
    ),
) -> dict:
    """Generate a contextual message for phase transitions.

    Uses AI to create a personalized message based on the user's discovery
    profile, company context, and selected robot.

    Args:
        conversation_id: The conversation's UUID.
        auth: Dual auth context (user or session).
        transition_type: Type of transition.

    Returns:
        dict: {
            "content": str,  # The transition message
            "chips": list[str],  # Quick reply options
        }
    """
    await _check_conversation_access(conversation_id, auth)

    session_id = auth.session.session_id if auth.session else None
    profile_id = None
    if auth.is_authenticated and auth.user:
        profile_id = await _get_user_profile_id(auth.user)

    agent_service = AgentService()

    try:
        result = await agent_service.generate_phase_transition_message(
            conversation_id=conversation_id,
            transition_type=transition_type,
            session_id=session_id,
            profile_id=profile_id,
        )
        return {
            "content": result["content"],
            "chips": result["chips"],
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Failed to generate transition message: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate transition message",
        )


@router.get(
    "/{conversation_id}/messages",
    response_model=MessageListResponse,
    summary="List messages",
    description="Returns paginated message history for a conversation.",
)
async def list_messages(
    conversation_id: UUID,
    auth: DualAuth,
    cursor: str | None = Query(default=None, description="Pagination cursor"),
    limit: int = Query(default=50, ge=1, le=100, description="Results per page"),
) -> MessageListResponse:
    """List messages in a conversation.

    Works for both authenticated users and anonymous sessions.

    Args:
        conversation_id: The conversation's UUID.
        auth: Dual auth context (user or session).
        cursor: Pagination cursor.
        limit: Maximum results per page.

    Returns:
        MessageListResponse: Paginated list of messages.

    Raises:
        HTTPException: 403 if no access.
    """
    await _check_conversation_access(conversation_id, auth)

    service = ConversationService()
    messages, next_cursor, has_more = await service.get_messages(
        conversation_id=conversation_id,
        cursor=cursor,
        limit=limit,
    )

    return MessageListResponse(
        messages=messages,
        next_cursor=next_cursor,
        has_more=has_more,
    )

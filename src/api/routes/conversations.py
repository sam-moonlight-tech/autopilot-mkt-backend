"""Conversation API routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import AuthContext, CurrentUser, DualAuth
from src.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
)
from src.schemas.message import (
    MessageCreate,
    MessageListResponse,
    MessageWithAgentResponse,
)
from src.services.agent_service import AgentService
from src.services.conversation_service import ConversationService
from src.services.profile_service import ProfileService
from src.services.session_service import SessionService

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
        user_id=conversation.get("user_id"),
        company_id=conversation.get("company_id"),
        title=conversation["title"],
        phase=conversation["phase"],
        metadata=conversation.get("metadata", {}),
        message_count=0,
        last_message_at=None,
        created_at=conversation["created_at"],
        updated_at=conversation["updated_at"],
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
        user_id=conversation.get("user_id"),
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
    if conversation["user_id"] != str(profile_id):
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
    description="Sends a message and receives an agent response.",
)
async def send_message(
    conversation_id: UUID,
    data: MessageCreate,
    auth: DualAuth,
) -> MessageWithAgentResponse:
    """Send a message to a conversation and get agent response.

    Works for both authenticated users and anonymous sessions.

    Args:
        conversation_id: The conversation's UUID.
        data: Message content.
        auth: Dual auth context (user or session).

    Returns:
        MessageWithAgentResponse: Both user and agent messages.

    Raises:
        HTTPException: 404 if not found, 403 if no access.
    """
    await _check_conversation_access(conversation_id, auth)

    agent_service = AgentService()
    user_message, agent_message = await agent_service.generate_response(
        conversation_id=conversation_id,
        user_message=data.content,
        metadata=data.metadata,
    )

    return MessageWithAgentResponse(
        user_message=user_message,
        agent_message=agent_message,
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

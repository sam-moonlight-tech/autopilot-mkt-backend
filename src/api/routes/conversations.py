"""Conversation API routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import CurrentUser
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

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def _get_user_profile_id(user: CurrentUser) -> UUID:
    """Get the profile ID for a user, creating profile if needed."""
    service = ProfileService()
    profile = await service.get_or_create_profile(user.user_id, user.email)
    return UUID(profile["id"])


async def _check_conversation_access(conversation_id: UUID, profile_id: UUID) -> None:
    """Check if user can access the conversation."""
    service = ConversationService()
    if not await service.can_access(conversation_id, profile_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this conversation",
        )


# Conversation CRUD endpoints


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a conversation",
    description="Creates a new conversation for the authenticated user.",
)
async def create_conversation(
    user: CurrentUser,
    data: ConversationCreate | None = None,
) -> ConversationResponse:
    """Create a new conversation.

    Args:
        user: The authenticated user context.
        data: Optional conversation creation data.

    Returns:
        ConversationResponse: The created conversation.
    """
    profile_id = await _get_user_profile_id(user)
    service = ConversationService()
    conversation = await service.create_conversation(profile_id, data)

    return ConversationResponse(
        id=conversation["id"],
        user_id=conversation["user_id"],
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
    user: CurrentUser,
) -> ConversationResponse:
    """Get a conversation by ID.

    Args:
        conversation_id: The conversation's UUID.
        user: The authenticated user context.

    Returns:
        ConversationResponse: The conversation.

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

    await _check_conversation_access(conversation_id, profile_id)

    # Get message count
    messages, _, _ = await service.get_messages(conversation_id, limit=1)
    message_count = len(messages)  # Simplified - could be more accurate

    return ConversationResponse(
        id=conversation["id"],
        user_id=conversation["user_id"],
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
    user: CurrentUser,
) -> MessageWithAgentResponse:
    """Send a message to a conversation and get agent response.

    Args:
        conversation_id: The conversation's UUID.
        data: Message content.
        user: The authenticated user context.

    Returns:
        MessageWithAgentResponse: Both user and agent messages.

    Raises:
        HTTPException: 404 if not found, 403 if no access.
    """
    profile_id = await _get_user_profile_id(user)
    await _check_conversation_access(conversation_id, profile_id)

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
    user: CurrentUser,
    cursor: str | None = Query(default=None, description="Pagination cursor"),
    limit: int = Query(default=50, ge=1, le=100, description="Results per page"),
) -> MessageListResponse:
    """List messages in a conversation.

    Args:
        conversation_id: The conversation's UUID.
        user: The authenticated user context.
        cursor: Pagination cursor.
        limit: Maximum results per page.

    Returns:
        MessageListResponse: Paginated list of messages.

    Raises:
        HTTPException: 403 if no access.
    """
    profile_id = await _get_user_profile_id(user)
    await _check_conversation_access(conversation_id, profile_id)

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

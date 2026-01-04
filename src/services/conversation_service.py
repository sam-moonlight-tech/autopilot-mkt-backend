"""Conversation business logic service."""

from datetime import datetime
from typing import Any
from uuid import UUID

from src.core.supabase import get_supabase_client
from src.models.conversation import ConversationPhase
from src.models.message import MessageRole
from src.schemas.conversation import ConversationCreate, ConversationResponse
from src.schemas.message import MessageResponse
from src.services.company_service import CompanyService


class ConversationService:
    """Service for managing conversations and messages."""

    DEFAULT_TITLE = "New Conversation"
    DEFAULT_PAGE_SIZE = 20

    def __init__(self) -> None:
        """Initialize conversation service with Supabase client."""
        self.client = get_supabase_client()
        self.company_service = CompanyService()

    async def create_conversation(
        self,
        user_profile_id: UUID,
        data: ConversationCreate | None = None,
    ) -> dict[str, Any]:
        """Create a new conversation.

        Args:
            user_profile_id: The profile ID of the conversation owner.
            data: Optional conversation creation data.

        Returns:
            dict: The created conversation data.
        """
        conversation_data = {
            "user_id": str(user_profile_id),
            "title": data.title if data and data.title else self.DEFAULT_TITLE,
            "phase": ConversationPhase.DISCOVERY.value,
            "metadata": data.metadata if data and data.metadata else {},
        }

        if data and data.company_id:
            conversation_data["company_id"] = str(data.company_id)

        response = self.client.table("conversations").insert(conversation_data).execute()

        return response.data[0]

    async def get_conversation(self, conversation_id: UUID) -> dict[str, Any] | None:
        """Get a conversation by ID.

        Args:
            conversation_id: The conversation's UUID.

        Returns:
            dict | None: The conversation data or None if not found.
        """
        response = (
            self.client.table("conversations")
            .select("*")
            .eq("id", str(conversation_id))
            .single()
            .execute()
        )

        return response.data if response.data else None

    async def can_access(self, conversation_id: UUID, profile_id: UUID) -> bool:
        """Check if a user can access a conversation.

        User can access if they are the owner or a member of the company.

        Args:
            conversation_id: The conversation's UUID.
            profile_id: The user's profile ID.

        Returns:
            bool: True if user can access the conversation.
        """
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return False

        # Check if user is owner
        if conversation["user_id"] == str(profile_id):
            return True

        # Check if conversation has a company and user is member
        if conversation.get("company_id"):
            return await self.company_service.is_member(
                UUID(conversation["company_id"]), profile_id
            )

        return False

    async def list_conversations(
        self,
        profile_id: UUID,
        company_id: UUID | None = None,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[ConversationResponse], str | None, bool]:
        """List conversations for a user.

        Args:
            profile_id: The user's profile ID.
            company_id: Optional company filter.
            cursor: Pagination cursor (ISO datetime string).
            limit: Maximum results to return.

        Returns:
            tuple: (conversations, next_cursor, has_more)
        """
        page_size = limit or self.DEFAULT_PAGE_SIZE

        query = (
            self.client.table("conversations")
            .select("*, messages(count)")
            .eq("user_id", str(profile_id))
            .order("created_at", desc=True)
            .limit(page_size + 1)  # Fetch one extra to check for more
        )

        if company_id:
            query = query.eq("company_id", str(company_id))

        if cursor:
            query = query.lt("created_at", cursor)

        response = query.execute()
        rows = response.data or []

        # Check if there are more results
        has_more = len(rows) > page_size
        if has_more:
            rows = rows[:page_size]

        # Determine next cursor
        next_cursor = None
        if has_more and rows:
            next_cursor = rows[-1]["created_at"]

        # Get message counts and last message times
        conversations = []
        for row in rows:
            # Extract message count from nested response
            message_count = 0
            if row.get("messages") and len(row["messages"]) > 0:
                message_count = row["messages"][0].get("count", 0)

            # Get last message timestamp
            last_message_at = await self._get_last_message_time(UUID(row["id"]))

            conversations.append(
                ConversationResponse(
                    id=row["id"],
                    user_id=row["user_id"],
                    company_id=row.get("company_id"),
                    title=row["title"],
                    phase=row["phase"],
                    metadata=row.get("metadata", {}),
                    message_count=message_count,
                    last_message_at=last_message_at,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )

        return conversations, next_cursor, has_more

    async def _get_last_message_time(self, conversation_id: UUID) -> datetime | None:
        """Get the timestamp of the last message in a conversation."""
        response = (
            self.client.table("messages")
            .select("created_at")
            .eq("conversation_id", str(conversation_id))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if response.data:
            return response.data[0]["created_at"]
        return None

    async def delete_conversation(self, conversation_id: UUID) -> bool:
        """Delete a conversation and all its messages.

        Args:
            conversation_id: The conversation's UUID.

        Returns:
            bool: True if deleted successfully.
        """
        self.client.table("conversations").delete().eq(
            "id", str(conversation_id)
        ).execute()

        return True

    async def update_phase(
        self, conversation_id: UUID, phase: ConversationPhase
    ) -> dict[str, Any] | None:
        """Update the conversation phase.

        Args:
            conversation_id: The conversation's UUID.
            phase: New conversation phase.

        Returns:
            dict | None: Updated conversation or None.
        """
        response = (
            self.client.table("conversations")
            .update({"phase": phase.value})
            .eq("id", str(conversation_id))
            .execute()
        )

        return response.data[0] if response.data else None

    # Message operations

    async def add_message(
        self,
        conversation_id: UUID,
        role: MessageRole,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Add a message to a conversation.

        Args:
            conversation_id: The conversation's UUID.
            role: Message role (user/assistant/system).
            content: Message content.
            metadata: Optional message metadata.

        Returns:
            dict: The created message data.
        """
        message_data = {
            "conversation_id": str(conversation_id),
            "role": role.value,
            "content": content,
            "metadata": metadata or {},
        }

        response = self.client.table("messages").insert(message_data).execute()

        # Update conversation updated_at
        self.client.table("conversations").update(
            {"updated_at": datetime.utcnow().isoformat()}
        ).eq("id", str(conversation_id)).execute()

        return response.data[0]

    async def get_messages(
        self,
        conversation_id: UUID,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[MessageResponse], str | None, bool]:
        """Get messages from a conversation with pagination.

        Args:
            conversation_id: The conversation's UUID.
            cursor: Pagination cursor (ISO datetime string).
            limit: Maximum results to return.

        Returns:
            tuple: (messages, next_cursor, has_more)
        """
        page_size = limit or self.DEFAULT_PAGE_SIZE

        query = (
            self.client.table("messages")
            .select("*")
            .eq("conversation_id", str(conversation_id))
            .order("created_at", desc=False)  # Oldest first for display
            .limit(page_size + 1)
        )

        if cursor:
            query = query.gt("created_at", cursor)

        response = query.execute()
        rows = response.data or []

        has_more = len(rows) > page_size
        if has_more:
            rows = rows[:page_size]

        next_cursor = None
        if has_more and rows:
            next_cursor = rows[-1]["created_at"]

        messages = [
            MessageResponse(
                id=row["id"],
                conversation_id=row["conversation_id"],
                role=row["role"],
                content=row["content"],
                metadata=row.get("metadata", {}),
                created_at=row["created_at"],
            )
            for row in rows
        ]

        return messages, next_cursor, has_more

    async def get_recent_messages(
        self, conversation_id: UUID, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Get most recent messages for context building.

        Args:
            conversation_id: The conversation's UUID.
            limit: Maximum number of messages.

        Returns:
            list[dict]: Recent messages ordered oldest first.
        """
        response = (
            self.client.table("messages")
            .select("*")
            .eq("conversation_id", str(conversation_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        # Reverse to get oldest first (chronological order)
        messages = response.data or []
        return list(reversed(messages))

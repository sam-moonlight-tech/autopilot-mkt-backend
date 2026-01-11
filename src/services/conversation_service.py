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
            "profile_id": str(user_profile_id),
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
            .maybe_single()
            .execute()
        )

        return response.data if response and response.data else None

    async def can_access(
        self,
        conversation_id: UUID,
        profile_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> bool:
        """Check if a user or session can access a conversation.

        User can access if they are the owner or a member of the company.
        Session can access if it owns the conversation.

        Args:
            conversation_id: The conversation's UUID.
            profile_id: The user's profile ID (for authenticated users).
            session_id: The session's UUID (for anonymous users).

        Returns:
            bool: True if user/session can access the conversation.
        """
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return False

        # Check session ownership first (for anonymous users)
        if session_id and conversation.get("session_id") == str(session_id):
            return True

        # Check if user is owner (for authenticated users)
        if profile_id:
            if conversation.get("profile_id") == str(profile_id):
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
            .eq("profile_id", str(profile_id))
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
                    profile_id=row["profile_id"],
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

    # Session-owned conversation operations

    async def create_conversation_for_session(
        self,
        session_id: UUID,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new conversation owned by a session (anonymous user).

        Args:
            session_id: The session ID of the anonymous user.
            title: Optional conversation title.
            metadata: Optional conversation metadata.

        Returns:
            dict: The created conversation data.
        """
        conversation_data = {
            "session_id": str(session_id),
            "profile_id": None,  # No profile for session-owned conversation
            "title": title or self.DEFAULT_TITLE,
            "phase": ConversationPhase.DISCOVERY.value,
            "metadata": metadata or {},
        }

        response = self.client.table("conversations").insert(conversation_data).execute()

        return response.data[0]

    async def can_access_by_session(
        self,
        conversation_id: UUID,
        session_id: UUID,
    ) -> bool:
        """Check if a session can access a conversation.

        Args:
            conversation_id: The conversation's UUID.
            session_id: The session's UUID.

        Returns:
            bool: True if session owns the conversation.
        """
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return False

        # Check if session is owner
        return conversation.get("session_id") == str(session_id)

    async def transfer_to_profile(
        self,
        conversation_id: UUID,
        profile_id: UUID,
    ) -> dict[str, Any] | None:
        """Transfer conversation ownership from session to user profile.

        Called during session claim to move conversation to authenticated user.

        Args:
            conversation_id: The conversation's UUID.
            profile_id: The profile UUID to transfer to.

        Returns:
            dict | None: Updated conversation or None if not found.
        """
        # Update conversation to be owned by profile instead of session
        response = (
            self.client.table("conversations")
            .update({"profile_id": str(profile_id), "session_id": None})
            .eq("id", str(conversation_id))
            .execute()
        )

        return response.data[0] if response.data else None

    async def get_session_conversations(
        self,
        session_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get all conversations owned by a session.

        Args:
            session_id: The session's UUID.

        Returns:
            list[dict]: List of conversation data.
        """
        response = (
            self.client.table("conversations")
            .select("*")
            .eq("session_id", str(session_id))
            .order("created_at", desc=True)
            .execute()
        )

        return response.data or []

    async def get_or_create_current_for_profile(
        self,
        profile_id: UUID,
        company_id: UUID | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Get the current conversation for a user or create one.

        Returns the most recent conversation for the user's profile.
        If no conversation exists, creates one with the provided context.

        Args:
            profile_id: The user's profile UUID.
            company_id: Optional company ID for the conversation.
            context: Optional context to store in metadata (discovery answers, etc.)

        Returns:
            tuple: (conversation_data, is_new) where is_new indicates if created.
        """
        # Try to get most recent conversation for this profile
        response = (
            self.client.table("conversations")
            .select("*")
            .eq("profile_id", str(profile_id))
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )

        if response.data:
            # Return existing conversation
            return response.data[0], False

        # Create new conversation with context
        metadata = context or {}
        conversation_data = {
            "profile_id": str(profile_id),
            "title": self.DEFAULT_TITLE,
            "phase": ConversationPhase.DISCOVERY.value,
            "metadata": metadata,
        }

        if company_id:
            conversation_data["company_id"] = str(company_id)

        response = self.client.table("conversations").insert(conversation_data).execute()
        return response.data[0], True

    async def get_or_create_current_for_session(
        self,
        session_id: UUID,
        context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Get or create the current conversation for a session.

        Checks if session already has a linked conversation.
        If not, creates one with the provided context.

        Args:
            session_id: The session's UUID.
            context: Optional context to store in metadata (session answers, etc.)

        Returns:
            tuple: (conversation_data, is_new) where is_new indicates if created.
        """
        # Check if session already has a conversation
        response = (
            self.client.table("conversations")
            .select("*")
            .eq("session_id", str(session_id))
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )

        if response.data:
            return response.data[0], False

        # Create new conversation for session
        metadata = context or {}
        conversation_data = {
            "session_id": str(session_id),
            "profile_id": None,
            "title": self.DEFAULT_TITLE,
            "phase": ConversationPhase.DISCOVERY.value,
            "metadata": metadata,
        }

        response = self.client.table("conversations").insert(conversation_data).execute()
        return response.data[0], True

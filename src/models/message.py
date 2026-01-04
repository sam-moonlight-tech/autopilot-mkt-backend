"""Message model type definitions for database operations."""

from datetime import datetime
from enum import Enum
from typing import Any, TypedDict
from uuid import UUID


class MessageRole(str, Enum):
    """Message role values matching database enum."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(TypedDict):
    """Message table row representation.

    Represents a message stored in the messages table.
    """

    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    metadata: dict[str, Any]
    created_at: datetime


class MessageCreate(TypedDict, total=False):
    """Data required to create a new message."""

    conversation_id: UUID
    role: MessageRole
    content: str
    metadata: dict[str, Any]

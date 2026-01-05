"""Conversation model type definitions for database operations."""

from datetime import datetime
from enum import Enum
from typing import Any, TypedDict
from uuid import UUID


class ConversationPhase(str, Enum):
    """Conversation phase values matching database enum.

    Aligned with frontend phases:
    - DISCOVERY: Initial discovery questions
    - ROI: ROI calculation and visualization
    - GREENLIGHT: Final selection and checkout
    """

    DISCOVERY = "discovery"
    ROI = "roi"
    GREENLIGHT = "greenlight"


class Conversation(TypedDict):
    """Conversation table row representation.

    Represents a conversation stored in the conversations table.
    A conversation must be owned by either a user (user_id) or a session (session_id).
    """

    id: UUID
    user_id: UUID | None
    session_id: UUID | None
    company_id: UUID | None
    title: str
    phase: ConversationPhase
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ConversationCreate(TypedDict, total=False):
    """Data required to create a new conversation.

    Either user_id or session_id must be provided.
    """

    user_id: UUID | None
    session_id: UUID | None
    company_id: UUID | None
    title: str
    phase: ConversationPhase
    metadata: dict[str, Any]


class ConversationUpdate(TypedDict, total=False):
    """Data that can be updated on a conversation.

    Includes user_id for ownership transfer from session to user.
    """

    user_id: UUID | None
    title: str
    phase: ConversationPhase
    metadata: dict[str, Any]

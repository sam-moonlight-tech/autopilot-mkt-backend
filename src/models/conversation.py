"""Conversation model type definitions for database operations."""

from datetime import datetime
from enum import Enum
from typing import Any, TypedDict
from uuid import UUID


class ConversationPhase(str, Enum):
    """Conversation phase values matching database enum."""

    DISCOVERY = "discovery"
    ROI = "roi"
    SELECTION = "selection"
    COMPLETED = "completed"


class Conversation(TypedDict):
    """Conversation table row representation.

    Represents a conversation stored in the conversations table.
    """

    id: UUID
    user_id: UUID
    company_id: UUID | None
    title: str
    phase: ConversationPhase
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ConversationCreate(TypedDict, total=False):
    """Data required to create a new conversation."""

    user_id: UUID
    company_id: UUID | None
    title: str
    phase: ConversationPhase
    metadata: dict[str, Any]


class ConversationUpdate(TypedDict, total=False):
    """Data that can be updated on a conversation."""

    title: str
    phase: ConversationPhase
    metadata: dict[str, Any]

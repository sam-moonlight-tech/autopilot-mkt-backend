"""Conversation Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.conversation import ConversationPhase


class ConversationCreate(BaseModel):
    """Schema for creating a new conversation."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(default=None, max_length=255, description="Conversation title")
    company_id: UUID | None = Field(default=None, description="Optional company context")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata")


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(default=None, max_length=255, description="New title")
    phase: ConversationPhase | None = Field(default=None, description="New phase")
    metadata: dict[str, Any] | None = Field(default=None, description="Updated metadata")


class ConversationResponse(BaseModel):
    """Schema for conversation API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Conversation unique identifier")
    profile_id: UUID | None = Field(default=None, description="Owner profile ID (None for session-owned)")
    company_id: UUID | None = Field(default=None, description="Associated company ID")
    title: str = Field(description="Conversation title")
    phase: ConversationPhase = Field(description="Current conversation phase")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    message_count: int = Field(default=0, description="Number of messages in conversation")
    last_message_at: datetime | None = Field(default=None, description="Timestamp of last message")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class ConversationListResponse(BaseModel):
    """Schema for paginated conversation list response."""

    model_config = ConfigDict(from_attributes=True)

    conversations: list[ConversationResponse] = Field(description="List of conversations")
    next_cursor: str | None = Field(default=None, description="Cursor for next page")
    has_more: bool = Field(default=False, description="Whether more results exist")


class CurrentConversationResponse(BaseModel):
    """Schema for GET /conversations/current response.

    Returns conversation with messages for resuming chat state.
    """

    model_config = ConfigDict(from_attributes=True)

    conversation: ConversationResponse = Field(description="The current conversation")
    is_new: bool = Field(description="True if conversation was just created")
    messages: list[dict[str, Any]] = Field(
        default_factory=list, description="Recent messages for chat history"
    )

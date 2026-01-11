"""Message Pydantic schemas for API request/response models."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from src.models.message import MessageRole


class MessageCreate(BaseModel):
    """Schema for creating a new message (user sends)."""

    model_config = ConfigDict(from_attributes=True)

    content: str = Field(..., min_length=1, max_length=10000, description="Message content")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional metadata")


class MessageResponse(BaseModel):
    """Schema for message API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Message unique identifier")
    conversation_id: UUID = Field(description="Parent conversation ID")
    role: MessageRole = Field(description="Message role (user/assistant/system)")
    content: str = Field(description="Message content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(description="Creation timestamp")


class DiscoveryState(BaseModel):
    """Schema for discovery progress state."""

    model_config = ConfigDict(from_attributes=True)

    ready_for_roi: bool = Field(
        default=False,
        description="Whether enough info has been gathered for ROI analysis"
    )
    answered_keys: list[str] = Field(
        default_factory=list,
        description="List of question keys that have been answered"
    )
    missing_keys: list[str] = Field(
        default_factory=list,
        description="List of required question keys still needed"
    )
    progress_percent: int = Field(
        default=0,
        description="Percentage of required questions answered (0-100)"
    )


class MessageWithAgentResponse(BaseModel):
    """Schema for message creation response including agent reply, chips, and discovery state."""

    model_config = ConfigDict(from_attributes=True)

    user_message: MessageResponse = Field(description="The user's sent message")
    agent_message: MessageResponse = Field(description="The agent's response")
    chips: list[str] = Field(
        default_factory=list,
        description="Quick reply chip options for the user"
    )
    discovery_state: DiscoveryState | None = Field(
        default=None,
        description="Discovery progress state (only present in discovery phase)"
    )


class MessageListResponse(BaseModel):
    """Schema for paginated message list response."""

    model_config = ConfigDict(from_attributes=True)

    messages: list[MessageResponse] = Field(description="List of messages")
    next_cursor: str | None = Field(default=None, description="Cursor for next page")
    has_more: bool = Field(default=False, description="Whether more results exist")

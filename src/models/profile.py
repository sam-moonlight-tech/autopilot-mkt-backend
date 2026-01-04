"""Profile model type definitions for database operations."""

from datetime import datetime
from typing import TypedDict
from uuid import UUID


class Profile(TypedDict):
    """Profile table row representation.

    Represents a user profile stored in the profiles table.
    Maps directly to the database schema.
    """

    id: UUID
    user_id: UUID
    display_name: str | None
    email: str | None
    avatar_url: str | None
    created_at: datetime
    updated_at: datetime


class ProfileCreate(TypedDict, total=False):
    """Data required to create a new profile.

    Only user_id is required; other fields are optional.
    """

    user_id: UUID
    display_name: str | None
    email: str | None
    avatar_url: str | None


class ProfileUpdate(TypedDict, total=False):
    """Data that can be updated on a profile.

    All fields are optional for partial updates.
    """

    display_name: str | None
    email: str | None
    avatar_url: str | None

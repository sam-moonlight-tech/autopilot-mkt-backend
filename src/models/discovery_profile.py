"""Discovery profile model type definitions for database operations."""

from datetime import datetime
from typing import TypedDict
from uuid import UUID

from src.models.session import DiscoveryAnswer, Greenlight, ROIInputs, SessionPhase


class DiscoveryProfile(TypedDict):
    """Discovery profile table row representation.

    Represents an authenticated user's discovery progress stored in
    the discovery_profiles table. Maps directly to the database schema.
    """

    id: UUID
    profile_id: UUID
    current_question_index: int
    phase: SessionPhase
    answers: dict[str, DiscoveryAnswer]
    roi_inputs: ROIInputs | None
    selected_product_ids: list[UUID]
    timeframe: str | None
    greenlight: Greenlight | None
    created_at: datetime
    updated_at: datetime


class DiscoveryProfileCreate(TypedDict, total=False):
    """Data required to create a new discovery profile.

    Only profile_id is required; other fields have defaults.
    """

    profile_id: UUID
    current_question_index: int
    phase: SessionPhase
    answers: dict[str, DiscoveryAnswer]
    roi_inputs: ROIInputs | None
    selected_product_ids: list[UUID]
    timeframe: str | None
    greenlight: Greenlight | None


class DiscoveryProfileUpdate(TypedDict, total=False):
    """Data that can be updated on a discovery profile.

    All fields are optional for partial updates.
    """

    current_question_index: int
    phase: SessionPhase
    answers: dict[str, DiscoveryAnswer]
    roi_inputs: ROIInputs | None
    selected_product_ids: list[UUID]
    timeframe: str | None
    greenlight: Greenlight | None

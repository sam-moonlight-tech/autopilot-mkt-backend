"""Session model type definitions for database operations."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from typing_extensions import TypedDict


# Session phase enum values matching database enum
SessionPhase = Literal["discovery", "roi", "greenlight"]

# Discovery answer group values
DiscoveryAnswerGroup = Literal["Company", "Facility", "Operations", "Economics", "Context"]


class DiscoveryAnswer(TypedDict):
    """Structure for a single discovery answer.

    Matches the frontend DiscoveryAnswer interface.
    """

    questionId: int
    key: str
    label: str
    value: str
    group: DiscoveryAnswerGroup


class ROIInputs(TypedDict):
    """Structure for ROI calculation inputs.

    Matches the frontend ROIInputs interface.
    """

    laborRate: float
    utilization: float
    maintenanceFactor: float
    manualMonthlySpend: float
    manualMonthlyHours: float


class TeamMember(TypedDict):
    """Structure for a team member in greenlight phase."""

    email: str
    name: str
    role: str


class Greenlight(TypedDict, total=False):
    """Structure for greenlight phase data.

    Matches the frontend greenlight interface.
    """

    target_start_date: str | None
    team_members: list[TeamMember]
    payment_method: Literal["card", "paypal", "bank"] | None


class Session(TypedDict):
    """Session table row representation.

    Represents an anonymous user session stored in the sessions table.
    Maps directly to the database schema.
    """

    id: UUID
    session_token: str
    conversation_id: UUID | None
    current_question_index: int
    phase: SessionPhase
    answers: dict[str, DiscoveryAnswer]
    roi_inputs: ROIInputs | None
    selected_product_ids: list[UUID]
    timeframe: str | None
    greenlight: Greenlight | None
    metadata: dict
    claimed_by_profile_id: UUID | None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class SessionCreate(TypedDict, total=False):
    """Data required to create a new session.

    Only session_token is required; other fields have defaults.
    """

    session_token: str
    conversation_id: UUID | None
    current_question_index: int
    phase: SessionPhase
    answers: dict[str, DiscoveryAnswer]
    roi_inputs: ROIInputs | None
    selected_product_ids: list[UUID]
    timeframe: str | None
    greenlight: Greenlight | None
    metadata: dict
    expires_at: datetime


class SessionUpdate(TypedDict, total=False):
    """Data that can be updated on a session.

    All fields are optional for partial updates.
    """

    conversation_id: UUID | None
    current_question_index: int
    phase: SessionPhase
    answers: dict[str, DiscoveryAnswer]
    roi_inputs: ROIInputs | None
    selected_product_ids: list[UUID]
    timeframe: str | None
    greenlight: Greenlight | None
    metadata: dict
    claimed_by_profile_id: UUID | None

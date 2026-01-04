"""Company model type definitions for database operations."""

from datetime import datetime
from enum import Enum
from typing import TypedDict
from uuid import UUID


class InvitationStatus(str, Enum):
    """Invitation status values matching database enum."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


class Company(TypedDict):
    """Company table row representation.

    Represents a company stored in the companies table.
    """

    id: UUID
    name: str
    owner_id: UUID
    created_at: datetime
    updated_at: datetime


class CompanyCreate(TypedDict):
    """Data required to create a new company."""

    name: str
    owner_id: UUID


class CompanyMember(TypedDict):
    """Company member table row representation.

    Represents a membership relationship between a profile and a company.
    """

    id: UUID
    company_id: UUID
    profile_id: UUID
    role: str
    joined_at: datetime


class CompanyMemberCreate(TypedDict):
    """Data required to create a company membership."""

    company_id: UUID
    profile_id: UUID
    role: str


class Invitation(TypedDict):
    """Invitation table row representation.

    Represents an invitation to join a company.
    """

    id: UUID
    company_id: UUID
    email: str
    invited_by: UUID
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None


class InvitationCreate(TypedDict):
    """Data required to create an invitation."""

    company_id: UUID
    email: str
    invited_by: UUID
    expires_at: datetime

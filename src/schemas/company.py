"""Company Pydantic schemas for API request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.models.company import InvitationStatus


class CompanyCreate(BaseModel):
    """Schema for creating a new company."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=255, description="Company name")


class CompanyResponse(BaseModel):
    """Schema for company API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Company unique identifier")
    name: str = Field(description="Company name")
    owner_id: UUID = Field(description="Profile ID of company owner")
    created_at: datetime = Field(description="Company creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class MemberProfile(BaseModel):
    """Embedded profile info for company member response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Profile unique identifier")
    display_name: str | None = Field(default=None, description="Member display name")
    email: str | None = Field(default=None, description="Member email")
    avatar_url: str | None = Field(default=None, description="Member avatar URL")


class CompanyMemberResponse(BaseModel):
    """Schema for company member API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Membership record ID")
    company_id: UUID = Field(description="Company ID")
    profile_id: UUID = Field(description="Member's profile ID")
    role: str = Field(description="Member's role in the company")
    joined_at: datetime = Field(description="When member joined")
    profile: MemberProfile = Field(description="Member's profile information")


class InvitationCreate(BaseModel):
    """Schema for creating an invitation."""

    model_config = ConfigDict(from_attributes=True)

    email: EmailStr = Field(..., description="Email address to invite")


class InvitationResponse(BaseModel):
    """Schema for invitation API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Invitation unique identifier")
    company_id: UUID = Field(description="Company being invited to")
    email: str = Field(description="Invited email address")
    invited_by: UUID = Field(description="Profile ID of inviter")
    status: InvitationStatus = Field(description="Current invitation status")
    expires_at: datetime = Field(description="Invitation expiration timestamp")
    created_at: datetime = Field(description="Invitation creation timestamp")
    accepted_at: datetime | None = Field(default=None, description="When invitation was accepted")


class InvitationWithCompany(InvitationResponse):
    """Invitation response with company details."""

    company_name: str = Field(description="Name of the company")

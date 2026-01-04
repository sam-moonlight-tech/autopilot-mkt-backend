"""Profile Pydantic schemas for API request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProfileBase(BaseModel):
    """Base profile fields shared across schemas."""

    display_name: str | None = Field(default=None, max_length=255, description="User display name")
    email: str | None = Field(default=None, max_length=255, description="User email address")
    avatar_url: str | None = Field(default=None, description="URL to user's avatar image")


class ProfileUpdate(BaseModel):
    """Schema for updating a profile.

    All fields are optional for partial updates.
    """

    model_config = ConfigDict(from_attributes=True)

    display_name: str | None = Field(default=None, max_length=255, description="New display name")
    avatar_url: str | None = Field(default=None, description="New avatar URL")


class ProfileResponse(ProfileBase):
    """Schema for profile API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Profile unique identifier")
    user_id: UUID = Field(description="Associated auth user ID")
    created_at: datetime = Field(description="Profile creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class CompanySummary(BaseModel):
    """Summary of a company for embedding in profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Company unique identifier")
    name: str = Field(description="Company name")
    role: str = Field(description="User's role in the company")
    joined_at: datetime = Field(description="When user joined the company")


class ProfileWithCompanies(ProfileResponse):
    """Profile response with list of companies the user belongs to."""

    companies: list[CompanySummary] = Field(
        default_factory=list, description="Companies the user belongs to"
    )

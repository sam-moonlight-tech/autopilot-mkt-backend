"""Common schemas used across the application."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthStatus(str, Enum):
    """Health check status values."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"


class HealthResponse(BaseModel):
    """Response schema for basic health check endpoint.

    Used for liveness probes to verify the service is running.
    """

    model_config = ConfigDict(from_attributes=True)

    status: HealthStatus = Field(description="Current health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    version: str = Field(default="0.1.0", description="API version")


class CheckResult(BaseModel):
    """Result of an individual dependency check.

    Used in readiness checks to report status of each dependency.
    """

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="Name of the dependency being checked")
    healthy: bool = Field(description="Whether the dependency is healthy")
    latency_ms: float | None = Field(default=None, description="Response time in milliseconds")
    error: str | None = Field(default=None, description="Error message if unhealthy")


class ReadinessResponse(BaseModel):
    """Response schema for readiness check endpoint.

    Used for readiness probes to verify all dependencies are available.
    """

    model_config = ConfigDict(from_attributes=True)

    status: HealthStatus = Field(description="Overall readiness status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    checks: list[CheckResult] = Field(default_factory=list, description="Individual check results")


class ErrorDetail(BaseModel):
    """Detailed error information for a single error.

    Can be used for field-level validation errors or general error details.
    """

    model_config = ConfigDict(from_attributes=True)

    loc: list[str] | None = Field(default=None, description="Location of error (e.g., field path)")
    msg: str = Field(description="Human-readable error message")
    type: str = Field(description="Error type identifier")


class ErrorResponse(BaseModel):
    """Standard error response schema.

    All API errors should be returned in this format for consistency.
    """

    model_config = ConfigDict(from_attributes=True)

    error: str = Field(description="Error type or category")
    message: str = Field(description="Human-readable error description")
    details: list[ErrorDetail] | None = Field(default=None, description="Additional error details")
    request_id: str | None = Field(default=None, description="Request ID for tracing")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    @classmethod
    def from_exception(
        cls,
        error_type: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
        request_id: str | None = None,
    ) -> "ErrorResponse":
        """Create an ErrorResponse from exception details.

        Args:
            error_type: Category or type of error.
            message: Human-readable error description.
            details: Optional list of error detail dictionaries.
            request_id: Optional request ID for tracing.

        Returns:
            ErrorResponse: Formatted error response.
        """
        error_details = None
        if details:
            error_details = [
                ErrorDetail(
                    loc=d.get("loc"),
                    msg=d.get("msg", str(d)),
                    type=d.get("type", "error"),
                )
                for d in details
            ]

        return cls(
            error=error_type,
            message=message,
            details=error_details,
            request_id=request_id,
        )

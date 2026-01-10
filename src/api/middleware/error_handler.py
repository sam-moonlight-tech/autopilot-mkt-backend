"""Global error handling middleware for consistent error responses."""

import logging
import time
import traceback
from typing import Any, Callable

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from src.schemas.common import ErrorResponse

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors.

    Use this class to raise application-specific errors that should
    be returned to the client with a specific status code and message.
    """

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type: str = "api_error",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        """Initialize API error.

        Args:
            message: Human-readable error message.
            status_code: HTTP status code to return.
            error_type: Error category/type for client handling.
            details: Optional additional error details.
        """
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.details = details
        super().__init__(message)


class NotFoundError(APIError):
    """Resource not found error."""

    def __init__(self, message: str = "Resource not found", details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_type="not_found",
            details=details,
        )


class ValidationError(APIError):
    """Request validation error."""

    def __init__(self, message: str = "Validation error", details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_type="validation_error",
            details=details,
        )


class AuthenticationError(APIError):
    """Authentication failure error."""

    def __init__(self, message: str = "Authentication required", details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_type="authentication_error",
            details=details,
        )


class AuthorizationError(APIError):
    """Authorization failure error."""

    def __init__(self, message: str = "Access denied", details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_type="authorization_error",
            details=details,
        )


class RateLimitError(APIError):
    """Rate limit exceeded error."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_type="rate_limit_exceeded",
            details=details,
        )
        self.retry_after = retry_after


def create_error_response(
    error_type: str,
    message: str,
    status_code: int,
    details: list[dict[str, Any]] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    """Create a standardized JSON error response.

    Args:
        error_type: Error category for client handling.
        message: Human-readable error description.
        status_code: HTTP status code.
        details: Optional error details.
        request_id: Optional request ID for tracing.

    Returns:
        JSONResponse: Formatted error response.
    """
    error_response = ErrorResponse.from_exception(
        error_type=error_type,
        message=message,
        details=details,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump(mode="json", exclude_none=True),
    )


async def error_handler_middleware(request: Request, call_next: Callable[[Request], Any]) -> Response:
    """Middleware to catch and format all exceptions.

    Ensures consistent error response format across the application.
    Logs full stack traces for debugging while returning safe messages to clients.

    Args:
        request: The incoming request.
        call_next: Next middleware or route handler.

    Returns:
        Response: Either the successful response or formatted error response.
    """
    # Extract request ID if present (can be set by upstream middleware/load balancer)
    request_id = request.headers.get("X-Request-ID")

    try:
        response = await call_next(request)
        return response

    except RateLimitError as e:
        # Rate limit errors - add Retry-After header
        logger.warning(
            "Rate limit exceeded: %s",
            e.message,
            extra={"request_id": request_id, "retry_after": e.retry_after},
        )
        response = create_error_response(
            error_type=e.error_type,
            message=e.message,
            status_code=e.status_code,
            details=e.details,
            request_id=request_id,
        )
        response.headers["Retry-After"] = str(e.retry_after)
        response.headers["X-RateLimit-Limit"] = "15"
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + e.retry_after)
        return response

    except APIError as e:
        # Application-specific errors - log at warning level
        logger.warning(
            "API error: %s - %s",
            e.error_type,
            e.message,
            extra={"request_id": request_id, "status_code": e.status_code},
        )
        return create_error_response(
            error_type=e.error_type,
            message=e.message,
            status_code=e.status_code,
            details=e.details,
            request_id=request_id,
        )

    except HTTPException as e:
        # FastAPI HTTP exceptions
        logger.warning(
            "HTTP exception: %s - %s",
            e.status_code,
            e.detail,
            extra={"request_id": request_id},
        )
        return create_error_response(
            error_type="http_error",
            message=str(e.detail),
            status_code=e.status_code,
            request_id=request_id,
        )

    except Exception as e:
        # Unexpected exceptions - log full stack trace
        logger.error(
            "Unhandled exception: %s\n%s",
            str(e),
            traceback.format_exc(),
            extra={"request_id": request_id},
        )
        return create_error_response(
            error_type="internal_error",
            message="An unexpected error occurred",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            request_id=request_id,
        )

"""Request body size limiting middleware."""

import logging
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from src.core.config import get_settings

logger = logging.getLogger(__name__)


async def request_size_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Response],
) -> Response:
    """Middleware to enforce request body size limits.

    Rejects requests with bodies larger than the configured maximum.
    This protects against memory exhaustion and abuse.

    Args:
        request: The incoming request.
        call_next: Next middleware or route handler.

    Returns:
        Response: Either the successful response or 413 error.
    """
    settings = get_settings()
    max_size = settings.max_request_body_size

    # Check Content-Length header if present
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            length = int(content_length)
            if length > max_size:
                logger.warning(
                    "Request body too large: %d bytes (max: %d)",
                    length,
                    max_size,
                )
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={
                        "error": {
                            "type": "request_too_large",
                            "message": f"Request body exceeds maximum size of {max_size} bytes",
                        }
                    },
                )
        except ValueError:
            pass  # Invalid content-length, let it proceed

    return await call_next(request)

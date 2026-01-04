"""Health check endpoints for monitoring and deployment verification."""

import time

from fastapi import APIRouter, Response, status

from src.api.deps import CurrentUser
from src.core.pinecone import check_pinecone_connection
from src.core.supabase import check_database_connection
from src.schemas.auth import AuthenticatedResponse
from src.schemas.common import CheckResult, HealthResponse, HealthStatus, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
    description="Basic health check to verify the service is running. Used for liveness probes.",
)
async def health_check() -> HealthResponse:
    """Return basic health status.

    This endpoint should always return 200 if the service is running.
    It does not check external dependencies.

    Returns:
        HealthResponse: Current health status with timestamp.
    """
    return HealthResponse(status=HealthStatus.HEALTHY)


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={
        200: {"description": "All dependencies healthy"},
        503: {"description": "One or more dependencies unhealthy"},
    },
    summary="Readiness check",
    description="Check if all dependencies are available. Used for readiness probes.",
)
async def readiness_check(response: Response) -> ReadinessResponse:
    """Check readiness of all dependencies.

    Verifies that the service can handle requests by checking:
    - Database connectivity (Supabase)
    - Vector database connectivity (Pinecone)

    Returns 503 if any dependency is unhealthy.

    Args:
        response: FastAPI response object for setting status code.

    Returns:
        ReadinessResponse: Status of all dependency checks.
    """
    checks: list[CheckResult] = []

    # Check database connection
    start_time = time.perf_counter()
    db_result = await check_database_connection()
    latency_ms = (time.perf_counter() - start_time) * 1000

    checks.append(
        CheckResult(
            name="database",
            healthy=db_result["healthy"],
            latency_ms=round(latency_ms, 2),
            error=db_result.get("error"),
        )
    )

    # Check Pinecone connection
    start_time = time.perf_counter()
    pinecone_result = await check_pinecone_connection()
    latency_ms = (time.perf_counter() - start_time) * 1000

    checks.append(
        CheckResult(
            name="pinecone",
            healthy=pinecone_result["healthy"],
            latency_ms=round(latency_ms, 2),
            error=pinecone_result.get("error"),
        )
    )

    # Determine overall status
    all_healthy = all(check.healthy for check in checks)
    overall_status = HealthStatus.HEALTHY if all_healthy else HealthStatus.UNHEALTHY

    # Set appropriate HTTP status code
    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(status=overall_status, checks=checks)


@router.get(
    "/health/auth",
    response_model=AuthenticatedResponse,
    summary="Authenticated health check",
    description="Protected endpoint to verify authentication is working correctly.",
    responses={
        200: {"description": "Successfully authenticated"},
        401: {"description": "Authentication required or invalid token"},
    },
)
async def authenticated_check(user: CurrentUser) -> AuthenticatedResponse:
    """Return authenticated user information.

    This endpoint requires a valid JWT token and returns the
    authenticated user's context. Used for testing auth flow.

    Args:
        user: The authenticated user context from JWT.

    Returns:
        AuthenticatedResponse: User information from the token.
    """
    return AuthenticatedResponse(
        authenticated=True,
        user_id=str(user.user_id),
        email=user.email,
        role=user.role,
    )

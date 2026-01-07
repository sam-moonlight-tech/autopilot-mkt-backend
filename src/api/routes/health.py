"""Health check endpoints for monitoring and deployment verification."""

import time

from fastapi import APIRouter, Response, status

from src.api.deps import CurrentUser
from src.core.pinecone import check_pinecone_connection
from src.core.supabase import check_database_connection
from src.schemas.auth import AuthenticatedResponse
from src.schemas.common import CheckResult, HealthResponse, HealthStatus, ReadinessResponse
from src.services.sales_knowledge_service import get_sales_knowledge_service, KNOWLEDGE_DIR

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


@router.get(
    "/health/knowledge",
    summary="Knowledge files check",
    description="Check if sales knowledge files are loaded correctly.",
)
async def knowledge_check() -> dict:
    """Check knowledge files status.

    Returns information about the knowledge directory and loaded files.
    Useful for debugging deployment issues.

    Returns:
        dict: Knowledge loading status and file information.
    """
    knowledge_files = [
        "personas.json",
        "pain_points.json",
        "questions_asked.json",
        "objections_discovery.json",
        "objection_responses.json",
        "roi_examples.json",
        "closing_triggers.json",
        "pricing_insights.json",
        "buying_signals.json",
    ]

    # Check directory
    dir_exists = KNOWLEDGE_DIR.exists()
    dir_path = str(KNOWLEDGE_DIR)

    # Check each file
    files_status = {}
    for filename in knowledge_files:
        filepath = KNOWLEDGE_DIR / filename
        if filepath.exists():
            try:
                import json
                with open(filepath) as f:
                    data = json.load(f)
                files_status[filename] = {
                    "exists": True,
                    "item_count": len(data) if isinstance(data, list) else 1,
                }
            except Exception as e:
                files_status[filename] = {"exists": True, "error": str(e)}
        else:
            files_status[filename] = {"exists": False}

    # Try loading via service
    service_status = {}
    try:
        service = get_sales_knowledge_service()
        discovery_ctx = service.get_discovery_context()
        service_status = {
            "loaded": True,
            "discovery_context_length": len(discovery_ctx),
            "discovery_context_preview": discovery_ctx[:500] if discovery_ctx else None,
        }
    except Exception as e:
        service_status = {"loaded": False, "error": str(e)}

    return {
        "knowledge_dir": dir_path,
        "dir_exists": dir_exists,
        "files": files_status,
        "service": service_status,
    }

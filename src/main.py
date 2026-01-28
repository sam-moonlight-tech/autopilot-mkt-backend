"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.middleware.error_handler import error_handler_middleware
from src.api.middleware.latency_logging import latency_logging_with_stats_middleware
from src.api.middleware.request_size import request_size_limit_middleware
from src.api.routes import (
    auth,
    companies,
    conversations,
    discovery,
    floor_plans,
    health,
    invitations,
    profiles,
    robots,
    sessions,
    webhooks,
)
from src.api.routes.checkout import orders_router, router as checkout_router
from src.api.routes.roi import roi_router
from src.core.config import get_settings
from src.core.rate_limiter import init_rate_limiter, shutdown_rate_limiter
from src.core.stripe import configure_stripe
from src.core.token_budget import init_token_budget, shutdown_token_budget
from src.services.recommendation_cache import (
    init_recommendation_cache,
    shutdown_recommendation_cache,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events.

    Args:
        app: FastAPI application instance.

    Yields:
        None: Control back to the application.
    """
    # Startup
    settings = get_settings()
    logger.info("Starting %s in %s mode", settings.app_name, settings.app_env)

    # Configure Stripe SDK
    configure_stripe()
    logger.info("Stripe SDK configured")

    # Initialize rate limiter with cleanup task
    await init_rate_limiter()
    logger.info("Rate limiter initialized")

    # Initialize token budget tracker with cleanup task
    await init_token_budget()
    logger.info("Token budget tracker initialized")

    # Initialize recommendation cache with cleanup task
    await init_recommendation_cache()
    logger.info("Recommendation cache initialized")

    yield
    # Shutdown
    await shutdown_recommendation_cache()
    logger.info("Recommendation cache shutdown")
    await shutdown_token_budget()
    logger.info("Token budget tracker shutdown")
    await shutdown_rate_limiter()
    logger.info("Rate limiter shutdown")
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="Autopilot API",
        description="Agent-led robotics procurement platform backend",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add error handler middleware (outermost - catches all errors)
    app.add_middleware(BaseHTTPMiddleware, dispatch=error_handler_middleware)

    # Add latency logging middleware (tracks request timing)
    app.add_middleware(BaseHTTPMiddleware, dispatch=latency_logging_with_stats_middleware)

    # Add request size limit middleware (rejects oversized requests early)
    app.add_middleware(BaseHTTPMiddleware, dispatch=request_size_limit_middleware)

    # Mount health routes at root level (no prefix)                                                                                          
    app.include_router(health.router)

    # Create API v1 router for versioned endpoints
    api_v1_router = APIRouter(prefix="/api/v1")

    # Authentication routes
    api_v1_router.include_router(auth.router)

    # Profile and company routes
    api_v1_router.include_router(profiles.router)
    api_v1_router.include_router(companies.router)
    api_v1_router.include_router(invitations.router)

    # Session and discovery routes
    api_v1_router.include_router(sessions.router)
    api_v1_router.include_router(discovery.router)

    # Conversation routes
    api_v1_router.include_router(conversations.router)

    # Robot catalog routes
    api_v1_router.include_router(robots.router)

    # Floor plan analysis routes
    api_v1_router.include_router(floor_plans.router)

    # ROI and Greenlight routes
    api_v1_router.include_router(roi_router)

    # Checkout and orders routes
    api_v1_router.include_router(checkout_router)
    api_v1_router.include_router(orders_router)

    # Webhook routes
    api_v1_router.include_router(webhooks.router)

    app.include_router(api_v1_router)

    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )

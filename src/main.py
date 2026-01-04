"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.middleware.error_handler import error_handler_middleware
from src.api.routes import companies, conversations, health, invitations, products, profiles
from src.core.config import get_settings

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
    yield
    # Shutdown
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

    # Add error handler middleware
    app.add_middleware(BaseHTTPMiddleware, dispatch=error_handler_middleware)

    # Mount health routes at root level (no prefix)
    app.include_router(health.router)

    # Create API v1 router for versioned endpoints
    api_v1_router = APIRouter(prefix="/api/v1")

    # Profile and company routes
    api_v1_router.include_router(profiles.router)
    api_v1_router.include_router(companies.router)
    api_v1_router.include_router(invitations.router)

    # Conversation routes
    api_v1_router.include_router(conversations.router)

    # Product routes
    api_v1_router.include_router(products.router)

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

"""Pytest configuration and fixtures."""

import os
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set test environment variables before importing application modules
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("SUPABASE_SIGNING_KEY_JWK", "test-signing-key-jwk")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-openai-key")
os.environ.setdefault("PINECONE_API_KEY", "test-pinecone-key")
os.environ.setdefault("PINECONE_ENVIRONMENT", "test-environment")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_stripe_secret_key")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_webhook_secret")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "pk_test_stripe_publishable_key")


@pytest.fixture(scope="session")
def test_settings() -> Generator[Any, None, None]:
    """Provide test settings with cleared cache.

    Yields:
        Settings: Test configuration settings.
    """
    from src.core.config import Settings, get_settings

    # Clear the cache to ensure fresh settings
    get_settings.cache_clear()

    settings = get_settings()
    yield settings

    # Clean up cache after tests
    get_settings.cache_clear()


@pytest.fixture
def mock_supabase_client() -> Generator[MagicMock, None, None]:
    """Provide a mocked Supabase client.

    Yields:
        MagicMock: Mocked Supabase client for testing.
    """
    mock_client = MagicMock()

    # Configure default mock responses
    mock_response = MagicMock()
    mock_response.data = []
    mock_client.table.return_value.select.return_value.limit.return_value.execute.return_value = (
        mock_response
    )

    with patch("src.core.supabase.get_supabase_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def client(mock_supabase_client: MagicMock) -> Generator[TestClient, None, None]:
    """Provide a test client for the FastAPI application.

    Args:
        mock_supabase_client: Mocked Supabase client fixture.

    Yields:
        TestClient: FastAPI test client.
    """
    from src.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client_without_mocks() -> Generator[TestClient, None, None]:
    """Provide a test client without any mocked dependencies.

    Use this fixture when you want to test actual integration
    with external services.

    Yields:
        TestClient: FastAPI test client without mocks.
    """
    from src.main import app

    with TestClient(app) as test_client:
        yield test_client

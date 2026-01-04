"""Unit tests for configuration module."""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.core.config import Settings, get_settings


class TestSettings:
    """Tests for Settings class."""

    def test_settings_loads_from_environment(self) -> None:
        """Test that Settings loads values from environment variables."""
        env_vars = {
            "APP_NAME": "test-app",
            "APP_ENV": "testing",
            "DEBUG": "true",
            "HOST": "127.0.0.1",
            "PORT": "9000",
            "CORS_ORIGINS": "http://localhost:3000,http://example.com",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_ANON_KEY": "test-anon",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service",
            "SUPABASE_JWT_SECRET": "test-secret",
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_MODEL": "gpt-4",
            "PINECONE_API_KEY": "pc-test",
            "PINECONE_ENVIRONMENT": "test-env",
            "PINECONE_INDEX_NAME": "test-index",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()

            assert settings.app_name == "test-app"
            assert settings.app_env == "testing"
            assert settings.debug is True
            assert settings.host == "127.0.0.1"
            assert settings.port == 9000
            assert settings.supabase_url == "https://test.supabase.co"
            assert settings.openai_model == "gpt-4"
            assert settings.pinecone_index_name == "test-index"

    def test_settings_cors_origins_list(self) -> None:
        """Test that CORS origins are correctly parsed into a list."""
        env_vars = {
            "CORS_ORIGINS": "http://localhost:3000, http://example.com , http://test.com",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_ANON_KEY": "test-anon",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service",
            "SUPABASE_JWT_SECRET": "test-secret",
            "OPENAI_API_KEY": "sk-test",
            "PINECONE_API_KEY": "pc-test",
            "PINECONE_ENVIRONMENT": "test-env",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()
            origins = settings.cors_origins_list

            assert len(origins) == 3
            assert "http://localhost:3000" in origins
            assert "http://example.com" in origins
            assert "http://test.com" in origins

    def test_settings_is_production_property(self) -> None:
        """Test the is_production property."""
        env_vars = {
            "APP_ENV": "production",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_ANON_KEY": "test-anon",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service",
            "SUPABASE_JWT_SECRET": "test-secret",
            "OPENAI_API_KEY": "sk-test",
            "PINECONE_API_KEY": "pc-test",
            "PINECONE_ENVIRONMENT": "test-env",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()
            assert settings.is_production is True

        env_vars["APP_ENV"] = "development"
        with patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()
            assert settings.is_production is False

    def test_settings_default_values(self) -> None:
        """Test that default values are applied correctly."""
        env_vars = {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_ANON_KEY": "test-anon",
            "SUPABASE_SERVICE_ROLE_KEY": "test-service",
            "SUPABASE_JWT_SECRET": "test-secret",
            "OPENAI_API_KEY": "sk-test",
            "PINECONE_API_KEY": "pc-test",
            "PINECONE_ENVIRONMENT": "test-env",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()

            assert settings.app_name == "autopilot-backend"
            assert settings.app_env == "development"
            assert settings.debug is False
            assert settings.host == "0.0.0.0"
            assert settings.port == 8080
            assert settings.openai_model == "gpt-4o"
            assert settings.pinecone_index_name == "autopilot-products"

    def test_settings_validation_error_missing_required(self) -> None:
        """Test that validation errors are raised for missing required fields."""
        # Clear required environment variables
        env_vars = {
            "SUPABASE_URL": "",
            "SUPABASE_ANON_KEY": "",
            "SUPABASE_SERVICE_ROLE_KEY": "",
            "SUPABASE_JWT_SECRET": "",
            "OPENAI_API_KEY": "",
            "PINECONE_API_KEY": "",
            "PINECONE_ENVIRONMENT": "",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings()

            # Check that validation error includes missing fields
            errors = exc_info.value.errors()
            error_fields = [e["loc"][0] for e in errors]
            assert "supabase_url" in error_fields


class TestGetSettings:
    """Tests for get_settings function."""

    def test_get_settings_returns_settings(self) -> None:
        """Test that get_settings returns a Settings instance."""
        # Clear cache before test
        get_settings.cache_clear()

        settings = get_settings()
        assert isinstance(settings, Settings)

        # Clean up
        get_settings.cache_clear()

    def test_get_settings_returns_cached_singleton(self) -> None:
        """Test that get_settings returns the same cached instance."""
        # Clear cache before test
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

        # Clean up
        get_settings.cache_clear()

    def test_get_settings_cache_can_be_cleared(self) -> None:
        """Test that cache can be cleared to reload settings."""
        get_settings.cache_clear()

        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()

        # After clearing cache, a new instance should be created
        # Note: They may have same values but be different objects
        assert settings1 is not settings2

        # Clean up
        get_settings.cache_clear()

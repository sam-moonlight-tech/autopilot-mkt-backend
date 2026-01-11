"""Application configuration management using Pydantic Settings."""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    All settings can be overridden via environment variables.
    Required settings will raise validation errors if not provided.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_file_priority="env_file",  # .env file takes precedence over shell env vars
    )

    # Application
    app_name: str = Field(default="autopilot-backend", description="Application name")
    app_env: str = Field(default="development", description="Environment (development/staging/production)")
    debug: bool = Field(default=False, description="Enable debug mode")

    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8080, description="Server port")

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173,https://autopilot-marketplace-discovery-to.vercel.app",
        description="Comma-separated list of allowed CORS origins",
    )

    # Auth redirects
    auth_redirect_url: str = Field(
        ...,
        description="Redirect URL after email verification (set via AUTH_REDIRECT_URL env var)",
    )

    # Supabase
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_secret_key: str = Field(..., description="Supabase secret key for backend operations")
    supabase_signing_key_jwk: str = Field(..., description="Supabase signing key JWK (JSON string) for JWT token verification")

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o", description="OpenAI model to use")
    max_context_messages: int = Field(default=20, description="Max messages to include in context")
    mock_openai: bool | None = Field(default=None, description="Mock OpenAI responses for local testing (saves tokens). Auto-enabled in development, disabled in production.")

    # Pinecone
    pinecone_api_key: str = Field(..., description="Pinecone API key")
    pinecone_environment: str = Field(..., description="Pinecone environment")
    pinecone_index_name: str = Field(default="autopilot-products", description="Pinecone index name")
    embedding_model: str = Field(default="text-embedding-3-small", description="OpenAI embedding model")

    # Session
    session_cookie_name: str = Field(default="autopilot_session", description="Session cookie name")
    session_cookie_max_age: int = Field(default=2592000, description="Session cookie max age in seconds (30 days)")
    session_cookie_secure: bool = Field(default=True, description="Use secure cookies (HTTPS only)")
    session_expiry_days: int = Field(default=30, description="Days until session expires")

    # Stripe
    stripe_secret_key: str = Field(default="", description="Stripe secret API key")
    stripe_webhook_secret: str = Field(default="", description="Stripe webhook signing secret")
    stripe_publishable_key: str = Field(default="", description="Stripe publishable key (for frontend)")

    # Email (Resend)
    resend_api_key: str = Field(default="", description="Resend API key for sending emails")
    email_from_address: str = Field(
        default="Autopilot <noreply@operationautopilot.com>",
        description="From address for transactional emails",
    )

    # Frontend
    frontend_url: str = Field(
        default="http://localhost:3000",
        description="Frontend application URL for email links",
    )

    @model_validator(mode="after")
    def set_mock_openai_default(self) -> "Settings":
        """Set mock_openai based on environment if not explicitly set via MOCK_OPENAI env var.
        
        - Production (APP_ENV=production): Always False (unless MOCK_OPENAI env var is explicitly set)
        - Development/Staging: True (unless MOCK_OPENAI env var is explicitly set)
        
        If MOCK_OPENAI env var is set, pydantic-settings already parsed it to a bool,
        so we only set the default if it's None.
        """
        # If MOCK_OPENAI was explicitly set via env var, it's already a bool (not None)
        # Only set default if it's None (meaning env var wasn't set)
        if self.mock_openai is None:
            # Production: always False
            # Development/Staging: True  
            self.mock_openai = self.app_env != "production"
        
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins string into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"

    @property
    def is_stripe_test_mode(self) -> bool:
        """Check if using Stripe test keys."""
        return self.stripe_secret_key.startswith("sk_test_")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings singleton.

    Returns:
        Settings: Application settings instance.

    Note:
        Settings are cached using lru_cache for performance.
        Call get_settings.cache_clear() to reload settings.
    """
    return Settings()

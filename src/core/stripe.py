"""Stripe client configuration and singleton."""

import logging

import stripe

from src.core.config import get_settings

logger = logging.getLogger(__name__)


def configure_stripe() -> None:
    """Configure Stripe SDK with API key from settings.

    This should be called once at application startup.
    If Stripe keys are not configured, Stripe operations will fail with clear errors.
    """
    settings = get_settings()
    if settings.stripe_secret_key:
        stripe.api_key = settings.stripe_secret_key
    else:
        logger.warning("Stripe secret key not configured. Stripe features will not work.")


def get_stripe() -> stripe:
    """Get the configured Stripe module.

    Returns:
        stripe: The Stripe module with API key configured.

    Note:
        Stripe SDK uses module-level configuration, so this returns
        the stripe module itself. Ensure configure_stripe() has been
        called before using Stripe API calls.
    """
    return stripe


def get_stripe_api_key(use_test_mode: bool | None = None) -> str:
    """Get the appropriate Stripe API key.

    Args:
        use_test_mode: If True, return test API key. If None, auto-detect from environment.

    Returns:
        str: The Stripe API key to use.

    Note:
        In production with test accounts enabled, test accounts use
        stripe_secret_key_test for Stripe operations.
    """
    settings = get_settings()
    # Auto-detect from environment if not specified
    if use_test_mode is None:
        use_test_mode = settings.is_stripe_test_mode
    if use_test_mode and settings.stripe_secret_key_test:
        return settings.stripe_secret_key_test
    return settings.stripe_secret_key

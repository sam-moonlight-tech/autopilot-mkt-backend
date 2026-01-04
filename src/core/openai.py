"""OpenAI client singleton for LLM operations."""

from functools import lru_cache

from openai import OpenAI

from src.core.config import get_settings


@lru_cache
def get_openai_client() -> OpenAI:
    """Get cached OpenAI client singleton.

    Returns:
        OpenAI: OpenAI client instance configured with API key.
    """
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key)

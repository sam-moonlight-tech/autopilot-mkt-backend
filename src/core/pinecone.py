"""Pinecone client singleton for vector database operations."""

from functools import lru_cache
from typing import Any

from pinecone import Pinecone

from src.core.config import get_settings


@lru_cache
def get_pinecone_client() -> Pinecone:
    """Get cached Pinecone client singleton.

    Returns:
        Pinecone: Pinecone client instance.
    """
    settings = get_settings()
    return Pinecone(api_key=settings.pinecone_api_key)


def get_pinecone_index():
    """Get the configured Pinecone index.

    Returns:
        Pinecone index for product embeddings.
    """
    settings = get_settings()
    client = get_pinecone_client()
    return client.Index(settings.pinecone_index_name)


async def check_pinecone_connection() -> dict[str, Any]:
    """Check if Pinecone connection is healthy.

    Performs a simple operation to verify connectivity.

    Returns:
        dict: Connection status with 'healthy' boolean and optional 'error' message.
    """
    try:
        settings = get_settings()
        client = get_pinecone_client()

        # Try to describe the index to verify connection
        index = client.Index(settings.pinecone_index_name)
        stats = index.describe_index_stats()

        return {
            "healthy": True,
            "vector_count": stats.total_vector_count if stats else 0,
        }
    except Exception as e:
        return {"healthy": False, "error": str(e)}

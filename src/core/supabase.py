"""Supabase client singleton for database operations."""

from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from src.core.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """Get cached Supabase client singleton.

    Uses service role key for backend operations, which bypasses RLS.
    This should only be used for server-side operations where
    proper authorization has already been verified.

    Returns:
        Client: Supabase client instance.
    """
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key,
    )


async def check_database_connection() -> dict[str, Any]:
    """Check if database connection is healthy.

    Performs a simple query to verify database connectivity.

    Returns:
        dict: Connection status with 'healthy' boolean and optional 'error' message.
    """
    try:
        client = get_supabase_client()
        # Execute a simple query to verify connection
        # Using a simple RPC call or table query
        result = client.table("profiles").select("id").limit(1).execute()
        # If we get here without exception, connection is healthy
        return {"healthy": True}
    except Exception as e:
        return {"healthy": False, "error": str(e)}

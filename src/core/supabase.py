"""Supabase client singleton for database operations."""

from functools import lru_cache
from typing import Any

from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions
from supabase_auth import SyncMemoryStorage

from src.core.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """Get cached Supabase client singleton for database operations.

    Uses secret key (sb_secret_) for backend operations, which bypasses RLS
    at the PostgREST level. This should only be used for server-side
    database operations where proper authorization has already been verified.

    IMPORTANT: Do NOT use this client for auth operations that call
    set_session() - use create_auth_client() instead to avoid polluting
    the singleton's Authorization header.

    Returns:
        Client: Supabase client instance.
    """
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key,
    )


def create_auth_client() -> Client:
    """Create a fresh Supabase client for auth operations.

    Use this for operations that call auth.set_session(), auth.sign_in_*(),
    or any method that modifies the client's Authorization header.

    This prevents session pollution of the singleton client used for
    database operations. Each call creates a new isolated client instance.

    Returns:
        Client: Fresh Supabase client instance with isolated session storage.
    """
    settings = get_settings()
    options = SyncClientOptions(
        storage=SyncMemoryStorage(),
        auto_refresh_token=False,
        persist_session=False,
    )
    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key,
        options=options,
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

# Supabase Secret Key Architecture

This document explains Supabase's transition from JWT-based service role keys to the new `sb_secret_` format, and how our backend is configured to work with it.

## The Old Architecture (JWT Service Role Keys)

Previously, Supabase used JWT tokens for both client and server authentication:

```
anon key:         eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... (role: "anon")
service_role key: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... (role: "service_role")
```

### How it worked

1. The key was a JWT containing `role: "service_role"` in its payload
2. PostgREST extracted the role from the JWT
3. PostgreSQL RLS policies checked `auth.role() = 'service_role'`
4. If matched, the policy granted access

### Problems with this approach

- **No revocation**: JWTs are self-contained - once issued, they're valid until expiration. If a key leaked, you couldn't invalidate it without rotating your JWT secret (which breaks ALL keys)
- **No audit trail**: No way to track when/where keys were used
- **Single key per role**: One service_role key for everything - no granular access control
- **Exposed by default**: Keys were always visible in the dashboard

## The New Architecture (`sb_secret_` Keys)

```bash
publishable key: sb_publishable_... (replaces anon)
secret key:      sb_secret_...      (replaces service_role)
```

Reference: <https://github.com/orgs/supabase/discussions/29260>

### How it works now

```bash
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌────────────┐
│   Backend   │────▶│  Kong/Edge   │────▶│  PostgREST   │────▶│ PostgreSQL │
│   (Python)  │     │   Gateway    │     │              │     │            │
└─────────────┘     └──────────────┘     └──────────────┘     └────────────┘
       │                   │                    │
       │                   │                    │
   apikey:            Validates key         RLS bypassed
   sb_secret_...      at gateway level      (no JWT to check)
```

1. **Gateway-level authentication**: The `sb_secret_` key is validated at Supabase's edge/Kong gateway, NOT in PostgreSQL
2. **RLS bypass happens upstream**: If the key is valid and has elevated privileges, RLS is bypassed before the query even reaches PostgreSQL
3. **No JWT in the request**: Since it's not a JWT, `auth.role()`, `auth.jwt()`, etc. return NULL - but it doesn't matter because RLS was already bypassed

### Benefits of the new architecture

| Benefit | Old (JWT) | New (`sb_secret_`) |
|---------|-----------|-------------------|
| **Instant revocation** | Impossible without rotating JWT secret | Delete the key, immediately invalid |
| **Multiple keys** | One per role | Create unlimited keys with different permissions |
| **Audit logging** | None | Every key reveal/use logged to org audit log |
| **Hidden by default** | Always visible | Must explicitly reveal each key |
| **Key rotation** | Painful (affects all clients) | Create new key, migrate, delete old |
| **Granular permissions** | All-or-nothing | Future: per-key scopes planned |

## How Our Backend Works With This

### The Session Pollution Problem

The old JWT service_role key worked like this:

```python
# Old behavior
client = create_client(url, "eyJ...service_role_jwt...")
# Authorization header: Bearer eyJ...
# PostgreSQL sees: auth.role() = 'service_role'
# RLS policy: USING (auth.role() = 'service_role') ✓ PASSES
```

The new secret key works like this:

```python
# New behavior
client = create_client(url, "sb_secret_...")
# Authorization header: Bearer sb_secret_...
# Gateway validates key, grants elevated access
# RLS bypassed at gateway level
# PostgreSQL sees: auth.role() = NULL (no JWT)
# RLS policy: USING (auth.role() = 'service_role') ✗ FAILS (but doesn't matter - already bypassed)
```

**The problem**: When `auth.set_session(user_jwt)` is called on the Supabase client, it replaces `Authorization: Bearer sb_secret_...` with `Authorization: Bearer eyJ...user_token...`. Now the gateway sees a regular user JWT, doesn't bypass RLS, and PostgreSQL enforces policies against the user's permissions.

If this happens on a singleton client, ALL subsequent database operations fail with RLS violations.

### Our Two-Client Pattern

To solve this, we use two client factories in `src/core/supabase.py`:

#### 1. `get_supabase_client()` - Singleton for database operations

```python
@lru_cache
def get_supabase_client() -> Client:
    """Cached singleton - use for database operations only."""
    settings = get_settings()
    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key,
    )
```

- Use for: SELECT, INSERT, UPDATE, DELETE on tables
- Cached via `@lru_cache` for performance
- RLS is bypassed via the `sb_secret_` key
- **NEVER call auth methods on this client**

#### 2. `create_auth_client()` - Fresh instance for auth operations

```python
def create_auth_client() -> Client:
    """Fresh instance - use for auth operations."""
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
```

- Use for: signup, login, logout, password reset, set_session()
- Creates a new isolated client each time
- Prevents session pollution of the singleton

### Usage in Services

```python
# Database operations - use singleton
from src.core.supabase import get_supabase_client

class ProfileService:
    def __init__(self):
        self.client = get_supabase_client()  # Singleton - safe for DB ops

# Auth operations - use fresh client
from src.core.supabase import create_auth_client

class AuthService:
    def __init__(self):
        self.client = create_auth_client()  # Fresh - safe for auth ops
```

## RLS Policy Considerations

With the new `sb_secret_` key architecture:

- **You don't need `auth.role() = 'service_role'` policies** - RLS is bypassed at the gateway level
- Existing service_role policies won't break anything, they just won't match (RLS is already bypassed)
- Focus RLS policies on user-level access control using `auth.uid()`

## Summary

Supabase moved authentication **upstream** from PostgreSQL to the API gateway. This enables:

- Instant key revocation (security)
- Multiple keys per project (flexibility)
- Audit trails (compliance)
- Future granular permissions (roadmap)

The tradeoff is that you can't mix auth operations (which modify the Authorization header) with database operations on the same client instance - hence our two-client pattern.

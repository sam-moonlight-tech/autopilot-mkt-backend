# Claude Code Project Guidelines

## Supabase Authentication

**Important:** Supabase has deprecated JWT-based service role keys. Always use the `SUPABASE_SECRET_KEY` format (`sb_secret_...`) now.

Reference: https://github.com/orgs/supabase/discussions/29260

### Configuration
```bash
# .env
SUPABASE_SECRET_KEY=sb_secret_...  # New format - use this
```

The secret key format `sb_secret_...` replaces the old JWT-based service role key (`eyJ...`). This key bypasses RLS at the PostgREST API level.

### Supabase Client Patterns

**Two client factories exist in `src/core/supabase.py`:**

1. **`get_supabase_client()`** - Singleton for database operations
   - Use for: SELECT, INSERT, UPDATE, DELETE on tables
   - Cached via `@lru_cache` for performance
   - RLS is bypassed via the `sb_secret_` key

2. **`create_auth_client()`** - Fresh instance for auth operations
   - Use for: signup, login, logout, password reset, set_session()
   - Creates a new isolated client each time
   - Prevents session pollution of the singleton

**Why two clients?** When `auth.set_session()` is called, it overwrites the client's `Authorization` header. If this happens on the singleton, ALL subsequent database operations would use the user's JWT instead of the service key, causing RLS violations.

## Database Migrations

Migrations are located in `supabase/migrations/` and follow sequential numbering:
- `001_create_profiles.sql` - User profiles linked to auth.users
- `002_create_companies.sql` - Companies, members, invitations (with non-recursive RLS)
- `003_create_conversations.sql` - Conversations and messages
- `004_create_sessions.sql` - Anonymous session management
- `005_create_discovery_profiles.sql` - Authenticated user discovery progress
- `006_create_robot_catalog.sql` - Robot products with Stripe integration
- `007_create_orders.sql` - Checkout orders

### RLS Policy Guidelines
- Avoid self-referencing policies on `company_members` to prevent infinite recursion
- Use `profiles` table for user identity checks (via `auth.uid()`)
- The `sb_secret_` key bypasses RLS at PostgREST level - no special RLS policies needed for backend access

## Stripe Integration

The robot catalog supports both test and production Stripe environments:
- `stripe_product_id` / `stripe_lease_price_id` - Production
- `stripe_product_id_test` / `stripe_lease_price_id_test` - Test

Run `python scripts/sync_stripe_products.py` to sync products to Stripe. The script auto-detects test vs production mode based on the `STRIPE_SECRET_KEY` prefix (`sk_test_` vs `sk_live_`).

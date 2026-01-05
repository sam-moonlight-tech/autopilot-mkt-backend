-- Update conversations table for session ownership and phase alignment
-- Enables anonymous users to own conversations via session_id

-- Step 1: Make user_id nullable for session-owned conversations
ALTER TABLE conversations
    ALTER COLUMN user_id DROP NOT NULL;

-- Step 2: Add session_id foreign key column
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS session_id UUID REFERENCES sessions(id) ON DELETE SET NULL;

-- Step 3: Add constraint ensuring conversation has an owner (user or session)
-- First drop if exists (for idempotency)
ALTER TABLE conversations
    DROP CONSTRAINT IF EXISTS chk_conversation_owner;
ALTER TABLE conversations
    ADD CONSTRAINT chk_conversation_owner
    CHECK (user_id IS NOT NULL OR session_id IS NOT NULL);

-- Step 4: Create index for session_id lookups
CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);

-- Step 5: Migrate conversation_phase enum to align with frontend
-- PostgreSQL doesn't support removing enum values directly, so we need to:
-- 1. Drop the default constraint
-- 2. Create a new enum type with the aligned values
-- 3. Update the column to use the new type, mapping old values to new
-- 4. Drop the old type
-- 5. Re-add the default

-- Drop the default constraint first
ALTER TABLE conversations
    ALTER COLUMN phase DROP DEFAULT;

-- Create new enum type with aligned values (discovery, roi, greenlight)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'conversation_phase_new') THEN
        CREATE TYPE conversation_phase_new AS ENUM ('discovery', 'roi', 'greenlight');
    END IF;
END $$;

-- Alter column to use new type, mapping selection/completed to greenlight
ALTER TABLE conversations
    ALTER COLUMN phase TYPE conversation_phase_new
    USING (
        CASE phase::text
            WHEN 'selection' THEN 'greenlight'
            WHEN 'completed' THEN 'greenlight'
            ELSE phase::text
        END
    )::conversation_phase_new;

-- Drop old enum type and rename new one
DROP TYPE IF EXISTS conversation_phase;
ALTER TYPE conversation_phase_new RENAME TO conversation_phase;

-- Re-add the default
ALTER TABLE conversations
    ALTER COLUMN phase SET DEFAULT 'discovery'::conversation_phase;

-- Note: Session-based access control is handled at the application layer
-- via token validation. The existing service_role policy provides
-- full access for backend operations.

-- Rename conversations.user_id to profile_id for clarity
-- The column references profiles.id, not auth.users.id, so the name was misleading

-- Rename the column
ALTER TABLE conversations RENAME COLUMN user_id TO profile_id;

-- Rename the index
ALTER INDEX idx_conversations_user_id RENAME TO idx_conversations_profile_id;

-- Drop and recreate RLS policies with updated column name

-- Drop existing policies
DROP POLICY IF EXISTS "Users can view own conversations" ON conversations;
DROP POLICY IF EXISTS "Users can create own conversations" ON conversations;
DROP POLICY IF EXISTS "Users can update own conversations" ON conversations;
DROP POLICY IF EXISTS "Users can delete own conversations" ON conversations;

-- Recreate policies with profile_id
CREATE POLICY "Users can view own conversations"
    ON conversations FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = conversations.profile_id
            AND p.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can create own conversations"
    ON conversations FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = profile_id
            AND p.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update own conversations"
    ON conversations FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = conversations.profile_id
            AND p.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete own conversations"
    ON conversations FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = conversations.profile_id
            AND p.user_id = auth.uid()
        )
    );

-- Update the CHECK constraint (need to drop and recreate)
ALTER TABLE conversations DROP CONSTRAINT chk_conversation_owner;
ALTER TABLE conversations ADD CONSTRAINT chk_conversation_owner
    CHECK (profile_id IS NOT NULL OR session_id IS NOT NULL);

-- Update messages RLS policies that reference conversations.user_id
DROP POLICY IF EXISTS "Users can view messages in own conversations" ON messages;
DROP POLICY IF EXISTS "Users can insert messages to own conversations" ON messages;

CREATE POLICY "Users can view messages in own conversations"
    ON messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM conversations c
            JOIN profiles p ON c.profile_id = p.id
            WHERE c.id = messages.conversation_id
            AND p.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert messages to own conversations"
    ON messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM conversations c
            JOIN profiles p ON c.profile_id = p.id
            WHERE c.id = conversation_id
            AND p.user_id = auth.uid()
        )
    );

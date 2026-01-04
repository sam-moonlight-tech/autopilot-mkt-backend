-- Create conversations table
-- Stores user conversations for agent interactions

CREATE TYPE conversation_phase AS ENUM ('discovery', 'roi', 'selection', 'completed');

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL DEFAULT 'New Conversation',
    phase conversation_phase NOT NULL DEFAULT 'discovery',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for conversations
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_company_id ON conversations(company_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);

-- Enable Row Level Security
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- Create messages table
-- Stores individual messages within conversations

CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system');

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role message_role NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for messages
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);

-- Enable Row Level Security
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Trigger for auto-updating updated_at on conversations
CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS Policies for conversations

-- Policy: Users can view their own conversations
CREATE POLICY "Users can view own conversations"
    ON conversations FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = conversations.user_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Company members can view company conversations
CREATE POLICY "Company members can view company conversations"
    ON conversations FOR SELECT
    USING (
        company_id IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM company_members cm
            JOIN profiles p ON cm.profile_id = p.id
            WHERE cm.company_id = conversations.company_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Users can create their own conversations
CREATE POLICY "Users can create own conversations"
    ON conversations FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = user_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Users can update their own conversations
CREATE POLICY "Users can update own conversations"
    ON conversations FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = conversations.user_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Users can delete their own conversations
CREATE POLICY "Users can delete own conversations"
    ON conversations FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = conversations.user_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Service role has full access to conversations
CREATE POLICY "Service role full access to conversations"
    ON conversations FOR ALL
    USING (auth.role() = 'service_role');

-- RLS Policies for messages

-- Policy: Users can view messages in their conversations
CREATE POLICY "Users can view messages in own conversations"
    ON messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM conversations c
            JOIN profiles p ON c.user_id = p.id
            WHERE c.id = messages.conversation_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Company members can view messages in company conversations
CREATE POLICY "Company members can view messages"
    ON messages FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM conversations c
            JOIN company_members cm ON cm.company_id = c.company_id
            JOIN profiles p ON cm.profile_id = p.id
            WHERE c.id = messages.conversation_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Users can insert messages to their conversations
CREATE POLICY "Users can insert messages to own conversations"
    ON messages FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM conversations c
            JOIN profiles p ON c.user_id = p.id
            WHERE c.id = conversation_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Service role has full access to messages
CREATE POLICY "Service role full access to messages"
    ON messages FOR ALL
    USING (auth.role() = 'service_role');

-- Create sessions table
-- Stores anonymous user sessions with discovery progress before signup

-- Create session_phase enum for session and discovery profile states
CREATE TYPE session_phase AS ENUM ('discovery', 'roi', 'greenlight');

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_token VARCHAR(64) NOT NULL UNIQUE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    current_question_index INTEGER NOT NULL DEFAULT 0,
    phase session_phase NOT NULL DEFAULT 'discovery',
    answers JSONB NOT NULL DEFAULT '{}',
    roi_inputs JSONB DEFAULT NULL,
    selected_product_ids UUID[] DEFAULT '{}',
    timeframe VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    claimed_by_profile_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 days',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for sessions
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_sessions_conversation_id ON sessions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_sessions_claimed ON sessions(claimed_by_profile_id) WHERE claimed_by_profile_id IS NOT NULL;

-- No RLS on sessions table - access controlled via service role and token-based lookup
-- Sessions are accessed by the backend using service_role key, not user JWTs

-- Trigger for auto-updating updated_at on sessions
CREATE TRIGGER update_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

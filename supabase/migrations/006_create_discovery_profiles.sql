-- Create discovery_profiles table
-- Stores authenticated user discovery progress (answers, ROI inputs, selections)

CREATE TABLE IF NOT EXISTS discovery_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
    current_question_index INTEGER NOT NULL DEFAULT 0,
    phase session_phase NOT NULL DEFAULT 'discovery',
    answers JSONB NOT NULL DEFAULT '{}',
    roi_inputs JSONB DEFAULT NULL,
    selected_product_ids UUID[] DEFAULT '{}',
    timeframe VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index for profile_id lookups
CREATE INDEX IF NOT EXISTS idx_discovery_profiles_profile_id ON discovery_profiles(profile_id);

-- Enable Row Level Security
ALTER TABLE discovery_profiles ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own discovery profile
CREATE POLICY "Users can view own discovery profile"
    ON discovery_profiles FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = discovery_profiles.profile_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Users can insert their own discovery profile
CREATE POLICY "Users can insert own discovery profile"
    ON discovery_profiles FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = profile_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Users can update their own discovery profile
CREATE POLICY "Users can update own discovery profile"
    ON discovery_profiles FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = discovery_profiles.profile_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Service role has full access to discovery profiles
CREATE POLICY "Service role full access to discovery profiles"
    ON discovery_profiles FOR ALL
    USING (auth.role() = 'service_role');

-- Trigger for auto-updating updated_at on discovery_profiles
CREATE TRIGGER update_discovery_profiles_updated_at
    BEFORE UPDATE ON discovery_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

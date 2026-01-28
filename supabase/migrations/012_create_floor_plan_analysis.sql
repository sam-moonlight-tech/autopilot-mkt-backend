-- Create floor_plan_analyses table
-- Stores uploaded floor plans with GPT-4o extracted features and cost estimates

-- Status enum for tracking analysis progress
CREATE TYPE floor_plan_status AS ENUM ('pending', 'processing', 'completed', 'failed');

CREATE TABLE floor_plan_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Ownership (supports both auth systems)
    profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,

    -- File storage
    file_name VARCHAR(255) NOT NULL,
    file_size_bytes INTEGER,
    file_mime_type VARCHAR(50),
    storage_path TEXT NOT NULL,  -- Supabase storage path

    -- Analysis status
    status floor_plan_status NOT NULL DEFAULT 'pending',
    error_message TEXT,

    -- Extracted features from GPT-4o Vision (JSONB for flexibility)
    extracted_features JSONB,
    extraction_confidence VARCHAR(20),  -- 'high', 'medium', 'low'

    -- Cost estimate calculated from extracted features
    cost_estimate JSONB,

    -- Analysis metadata
    gpt_model_used VARCHAR(50),
    tokens_used INTEGER,
    analysis_duration_ms INTEGER,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Ensure at least one owner
    CONSTRAINT floor_plan_has_owner CHECK (
        (profile_id IS NOT NULL AND session_id IS NULL) OR
        (profile_id IS NULL AND session_id IS NOT NULL)
    )
);

-- Add comments documenting JSONB structures
COMMENT ON COLUMN floor_plan_analyses.extracted_features IS
'GPT-4o extracted data: {
  facility_dimensions: {length_ft, width_ft, total_sqft, confidence},
  courts: [{label, dimensions, sqft, surface_type, max_occupancy, has_net, confidence}],
  buffer_zones: [{between_courts, width_ft, length_ft, sqft, confidence}],
  circulation_areas: [{label, sqft, surface_type, is_hex_textured, confidence}],
  auxiliary_areas: [{label, sqft, surface_type, cleanable_by_robot, confidence}],
  excluded_areas: [{label, sqft, reason, confidence}],
  obstructions: [{type, location, handling}],
  summary: {total_court_sqft, total_circulation_sqft, total_auxiliary_sqft, total_excluded_sqft, total_cleanable_sqft, court_count}
}';

COMMENT ON COLUMN floor_plan_analyses.cost_estimate IS
'Calculated cleaning costs: {
  total_monthly_cost, total_daily_cost,
  breakdown_by_zone: [{zone_type, zone_label, sqft, cleaning_mode, frequency_per_month, cost_per_cleaning, monthly_cost}],
  breakdown_by_mode: [{mode, total_sqft, rate_per_sqft, cleanings_per_month, monthly_cost}],
  estimated_daily_cleaning_hours, estimated_robot_count,
  rate_card_version
}';

-- Indexes for common queries
CREATE INDEX idx_floor_plan_analyses_profile_id ON floor_plan_analyses(profile_id);
CREATE INDEX idx_floor_plan_analyses_session_id ON floor_plan_analyses(session_id);
CREATE INDEX idx_floor_plan_analyses_status ON floor_plan_analyses(status);
CREATE INDEX idx_floor_plan_analyses_created_at ON floor_plan_analyses(created_at DESC);

-- Enable Row Level Security
ALTER TABLE floor_plan_analyses ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own floor plan analyses
CREATE POLICY "Users can view own floor plan analyses"
    ON floor_plan_analyses FOR SELECT
    USING (
        profile_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = floor_plan_analyses.profile_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Users can insert their own floor plan analyses
CREATE POLICY "Users can insert own floor plan analyses"
    ON floor_plan_analyses FOR INSERT
    WITH CHECK (
        profile_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = profile_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Users can update their own floor plan analyses
CREATE POLICY "Users can update own floor plan analyses"
    ON floor_plan_analyses FOR UPDATE
    USING (
        profile_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = floor_plan_analyses.profile_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Users can delete their own floor plan analyses
CREATE POLICY "Users can delete own floor plan analyses"
    ON floor_plan_analyses FOR DELETE
    USING (
        profile_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = floor_plan_analyses.profile_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Service role has full access
CREATE POLICY "Service role full access to floor_plan_analyses"
    ON floor_plan_analyses FOR ALL
    USING (auth.role() = 'service_role');

-- Trigger for auto-updating updated_at
CREATE TRIGGER update_floor_plan_analyses_updated_at
    BEFORE UPDATE ON floor_plan_analyses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

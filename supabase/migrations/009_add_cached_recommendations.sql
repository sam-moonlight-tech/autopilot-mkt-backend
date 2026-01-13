-- Add cached recommendations columns to discovery_profiles
-- This enables persistent caching of ROI calculations so they don't change on page reload

-- Add column to store the hash of answers used for cached recommendations
ALTER TABLE discovery_profiles
ADD COLUMN IF NOT EXISTS answers_hash VARCHAR(64);

-- Add column to store the cached recommendations response
ALTER TABLE discovery_profiles
ADD COLUMN IF NOT EXISTS cached_recommendations JSONB DEFAULT NULL;

-- Add comment to document the columns
COMMENT ON COLUMN discovery_profiles.answers_hash IS 'SHA256 hash of answers dict when cached_recommendations was generated';
COMMENT ON COLUMN discovery_profiles.cached_recommendations IS 'Cached RecommendationsResponse JSON, valid when answers_hash matches current answers';

-- Add index for answers_hash lookups (for cache validation)
CREATE INDEX IF NOT EXISTS idx_discovery_profiles_answers_hash ON discovery_profiles(answers_hash);

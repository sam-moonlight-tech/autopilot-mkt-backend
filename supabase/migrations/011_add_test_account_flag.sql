-- Add is_test_account flag to profiles table
-- Test accounts in production use Stripe test mode for checkout

ALTER TABLE profiles
ADD COLUMN is_test_account BOOLEAN NOT NULL DEFAULT FALSE;

-- Create index for filtering test accounts
CREATE INDEX IF NOT EXISTS idx_profiles_is_test_account ON profiles(is_test_account);

-- Add comment for documentation
COMMENT ON COLUMN profiles.is_test_account IS 'When true, this account uses Stripe test mode for checkout in production';

-- Create companies table
-- Companies that users can belong to

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    owner_id UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index for owner_id lookups
CREATE INDEX IF NOT EXISTS idx_companies_owner_id ON companies(owner_id);

-- Enable Row Level Security
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;

-- Create company_members table
-- Tracks which profiles belong to which companies and their roles
CREATE TABLE IF NOT EXISTS company_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(company_id, profile_id)
);

-- Create indexes for company_members
CREATE INDEX IF NOT EXISTS idx_company_members_company_id ON company_members(company_id);
CREATE INDEX IF NOT EXISTS idx_company_members_profile_id ON company_members(profile_id);

-- Enable Row Level Security
ALTER TABLE company_members ENABLE ROW LEVEL SECURITY;

-- Create invitations table
-- Tracks pending invitations to companies
CREATE TYPE invitation_status AS ENUM ('pending', 'accepted', 'declined', 'expired');

CREATE TABLE IF NOT EXISTS invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    invited_by UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    status invitation_status NOT NULL DEFAULT 'pending',
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    UNIQUE(company_id, email, status)
);

-- Create indexes for invitations
CREATE INDEX IF NOT EXISTS idx_invitations_company_id ON invitations(company_id);
CREATE INDEX IF NOT EXISTS idx_invitations_email ON invitations(email);
CREATE INDEX IF NOT EXISTS idx_invitations_status ON invitations(status);

-- Enable Row Level Security
ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;

-- Trigger for auto-updating updated_at on companies
CREATE TRIGGER update_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- RLS Policies for companies (non-recursive)
-- ============================================================================

-- Policy: Owners can view their own company (checks profiles, not company_members)
CREATE POLICY "Owners can view own company"
    ON companies FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = companies.owner_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Members can view company they belong to
CREATE POLICY "Members can view their company"
    ON companies FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM company_members cm
            JOIN profiles p ON cm.profile_id = p.id
            WHERE cm.company_id = companies.id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Authenticated users can create companies
CREATE POLICY "Users can create companies"
    ON companies FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = owner_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Company owner can update company
CREATE POLICY "Owner can update company"
    ON companies FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = owner_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Service role has full access to companies
CREATE POLICY "Service role full access to companies"
    ON companies FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================================================
-- RLS Policies for company_members (non-recursive - avoid self-reference)
-- ============================================================================

-- Policy: Users can view their OWN membership record (no recursion)
CREATE POLICY "Users can view own membership"
    ON company_members FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.id = company_members.profile_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Company owners can view/manage all members (checks companies.owner_id)
CREATE POLICY "Owners can manage company members"
    ON company_members FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM companies c
            JOIN profiles p ON c.owner_id = p.id
            WHERE c.id = company_members.company_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Service role has full access to company_members
CREATE POLICY "Service role full access to company_members"
    ON company_members FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================================================
-- RLS Policies for invitations
-- ============================================================================

-- Policy: Company owners can view invitations
CREATE POLICY "Owners can view invitations"
    ON invitations FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM companies c
            JOIN profiles p ON c.owner_id = p.id
            WHERE c.id = invitations.company_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Invited user can view their invitations
CREATE POLICY "Invited users can view own invitations"
    ON invitations FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM profiles p
            WHERE p.user_id = auth.uid()
            AND p.email = invitations.email
        )
    );

-- Policy: Company owner can create invitations
CREATE POLICY "Owner can create invitations"
    ON invitations FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM companies c
            JOIN profiles p ON c.owner_id = p.id
            WHERE c.id = company_id
            AND p.user_id = auth.uid()
        )
    );

-- Policy: Service role has full access to invitations
CREATE POLICY "Service role full access to invitations"
    ON invitations FOR ALL
    USING (auth.role() = 'service_role');

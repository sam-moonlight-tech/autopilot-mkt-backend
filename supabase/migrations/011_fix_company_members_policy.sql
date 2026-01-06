-- Fix infinite recursion in company_members RLS policy
-- The problem: "Members can view company members" policy queries company_members itself

-- Step 1: Create a security definer function that bypasses RLS
CREATE OR REPLACE FUNCTION is_company_member(check_company_id UUID, check_user_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM company_members cm
        JOIN profiles p ON cm.profile_id = p.id
        WHERE cm.company_id = check_company_id
        AND p.user_id = check_user_id
    );
END;
$$;

-- Step 2: Drop the problematic policy
DROP POLICY IF EXISTS "Members can view company members" ON company_members;

-- Step 3: Create a new policy that uses the security definer function
CREATE POLICY "Members can view company members"
    ON company_members FOR SELECT
    USING (
        is_company_member(company_id, auth.uid())
    );

-- Step 4: Also fix the "Owner can manage members" policy for consistency
DROP POLICY IF EXISTS "Owner can manage members" ON company_members;

CREATE POLICY "Owner can manage members"
    ON company_members FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM companies c
            JOIN profiles p ON c.owner_id = p.id
            WHERE c.id = company_members.company_id
            AND p.user_id = auth.uid()
        )
    );

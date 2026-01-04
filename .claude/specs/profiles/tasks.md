# Implementation Plan: Profiles & Companies

## Task Overview

This implementation plan establishes user profile and company management for the Autopilot backend. Tasks are ordered to build database schema first, then models/schemas, then services, and finally routes.

## Steering Document Compliance

- Files follow `structure.md` directory layout
- Uses snake_case for modules, PascalCase for classes
- Follows layered architecture: routes → services → models

## Atomic Task Requirements

**Each task meets these criteria:**
- **File Scope**: Touches 1-3 related files maximum
- **Time Boxing**: Completable in 15-30 minutes
- **Single Purpose**: One testable outcome per task
- **Specific Files**: Exact file paths specified
- **Agent-Friendly**: Clear input/output with minimal context switching

## Tasks

- [ ] 3.1. Create profiles table migration
  - File: `supabase/migrations/001_create_profiles.sql` (create)
  - Define profiles table with id, user_id, display_name, email, avatar_url, timestamps
  - Add unique constraint on user_id
  - Add foreign key reference to auth.users
  - Enable RLS with policies for self-access
  - Purpose: Establish profile data storage
  - _Requirements: 1_

- [ ] 3.2. Create companies and related tables migration
  - File: `supabase/migrations/002_create_companies.sql` (create)
  - Define companies table with id, name, owner_id, timestamps
  - Define company_members table with company_id, profile_id, role, joined_at
  - Define invitations table with company_id, email, invited_by, status, expires_at
  - Add foreign key references and unique constraints
  - Enable RLS with appropriate policies
  - Purpose: Establish company and membership data storage
  - _Requirements: 2, 3, 4_

- [ ] 3.3. Create profile model type hints
  - File: `src/models/__init__.py` (create)
  - File: `src/models/profile.py` (create)
  - Define Profile TypedDict with all table columns
  - Include type hints for database operations
  - Purpose: Type-safe profile data handling
  - _Requirements: 1_

- [ ] 3.4. Create company model type hints
  - File: `src/models/company.py` (create)
  - Define Company, CompanyMember, Invitation TypedDicts
  - Include type hints for all table columns
  - Purpose: Type-safe company data handling
  - _Requirements: 2, 3, 4_

- [ ] 3.5. Create profile Pydantic schemas
  - File: `src/schemas/profile.py` (create)
  - Define ProfileBase, ProfileUpdate, ProfileResponse schemas
  - Define ProfileWithCompanies for listing user's companies
  - Use Pydantic v2 syntax with model_config
  - Purpose: API request/response contracts for profiles
  - _Requirements: 1, 5_

- [ ] 3.6. Create company Pydantic schemas
  - File: `src/schemas/company.py` (create)
  - Define CompanyCreate, CompanyResponse schemas
  - Define CompanyMemberResponse with embedded profile
  - Define InvitationCreate, InvitationResponse schemas
  - Purpose: API request/response contracts for companies
  - _Requirements: 2, 3, 4_

- [ ] 3.7. Implement ProfileService core methods
  - File: `src/services/__init__.py` (create)
  - File: `src/services/profile_service.py` (create)
  - Implement get_or_create_profile() with upsert logic
  - Implement get_profile() for fetching by user_id
  - Implement update_profile() for updating allowed fields
  - Purpose: Core profile business logic
  - _Leverage: src/core/supabase.py_
  - _Requirements: 1_

- [ ] 3.8. Add get_user_companies to ProfileService
  - File: `src/services/profile_service.py` (modify)
  - Implement get_user_companies() to list companies user belongs to
  - Join with company_members table
  - Include role in response
  - Purpose: Support user's company listing
  - _Leverage: existing ProfileService_
  - _Requirements: 5_

- [ ] 3.9. Implement CompanyService core methods
  - File: `src/services/company_service.py` (create)
  - Implement create_company() that creates company and adds owner as member
  - Implement get_company() for fetching by id
  - Implement is_member() and is_owner() permission checks
  - Purpose: Core company business logic
  - _Leverage: src/core/supabase.py_
  - _Requirements: 2, 6_

- [ ] 3.10. Add member management to CompanyService
  - File: `src/services/company_service.py` (modify)
  - Implement get_members() to list all company members with profiles
  - Implement remove_member() with owner protection
  - Purpose: Company member management logic
  - _Leverage: existing CompanyService_
  - _Requirements: 3_

- [ ] 3.11. Implement InvitationService
  - File: `src/services/invitation_service.py` (create)
  - Implement create_invitation() with 7-day expiration
  - Implement get_invitation() for fetching by id
  - Implement list_company_invitations() for listing by company
  - Purpose: Invitation creation and retrieval logic
  - _Leverage: src/core/supabase.py_
  - _Requirements: 4_

- [ ] 3.12. Add invitation acceptance to InvitationService
  - File: `src/services/invitation_service.py` (modify)
  - Implement accept_invitation() with expiration and duplicate checks
  - Update invitation status and create company_member atomically
  - Return error for expired or already-member cases
  - Purpose: Invitation acceptance logic
  - _Leverage: src/services/company_service.py for member creation_
  - _Requirements: 4_

- [ ] 3.13. Create profile routes
  - File: `src/api/routes/profiles.py` (create)
  - Implement GET /profiles/me returning authenticated user's profile
  - Implement PUT /profiles/me for profile updates
  - Implement GET /profiles/me/companies for user's companies
  - Use get_current_user dependency
  - Purpose: Profile API endpoints
  - _Leverage: src/api/deps.py, src/services/profile_service.py_
  - _Requirements: 1, 5_

- [ ] 3.14. Create company routes
  - File: `src/api/routes/companies.py` (create)
  - Implement POST /companies for company creation
  - Implement GET /companies/{id} for company details
  - Implement GET /companies/{id}/members for member listing
  - Implement DELETE /companies/{id}/members/{profile_id} for member removal
  - Add permission checks for each endpoint
  - Purpose: Company API endpoints
  - _Leverage: src/api/deps.py, src/services/company_service.py_
  - _Requirements: 2, 3, 6_

- [ ] 3.15. Create invitation routes
  - File: `src/api/routes/companies.py` (modify)
  - Implement POST /companies/{id}/invitations for creating invitations
  - Implement GET /companies/{id}/invitations for listing invitations
  - Implement POST /invitations/{id}/accept for accepting invitations
  - Add owner permission check for creating invitations
  - Purpose: Invitation API endpoints
  - _Leverage: src/services/invitation_service.py_
  - _Requirements: 4_

- [ ] 3.16. Register profile and company routes in main
  - File: `src/main.py` (modify)
  - Import and include profiles router at /api/v1/profiles
  - Import and include companies router at /api/v1/companies
  - Import and include invitations router at /api/v1/invitations
  - Purpose: Enable profile and company endpoints
  - _Leverage: existing main.py router setup_
  - _Requirements: 1, 2, 3, 4_

- [ ] 3.17. Write unit tests for ProfileService
  - File: `tests/unit/test_profile_service.py` (create)
  - Test get_or_create_profile creates new profile
  - Test get_or_create_profile returns existing profile
  - Test update_profile modifies allowed fields
  - Purpose: Verify profile business logic
  - _Requirements: 1_

- [ ] 3.18. Write unit tests for CompanyService
  - File: `tests/unit/test_company_service.py` (create)
  - Test create_company adds owner as member
  - Test is_member returns correct boolean
  - Test is_owner returns correct boolean
  - Test remove_member prevents owner removal
  - Purpose: Verify company business logic
  - _Requirements: 2, 3, 6_

- [ ] 3.19. Write integration tests for profile endpoints
  - File: `tests/integration/test_profile_routes.py` (create)
  - Test GET /profiles/me returns profile
  - Test PUT /profiles/me updates profile
  - Test GET /profiles/me/companies returns user's companies
  - Purpose: Verify profile API works end-to-end
  - _Requirements: 1, 5_

- [ ] 3.20. Write integration tests for company endpoints
  - File: `tests/integration/test_company_routes.py` (create)
  - Test POST /companies creates company
  - Test GET /companies/{id} returns company for members
  - Test invitation create/accept flow
  - Test permission enforcement
  - Purpose: Verify company API works end-to-end
  - _Requirements: 2, 3, 4, 6_

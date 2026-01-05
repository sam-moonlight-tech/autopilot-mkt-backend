# Requirements Document: Profiles & Companies

## Introduction

This specification defines the user profile and company account management system for the Autopilot backend. It establishes individual user profiles, company accounts with owner/member relationships, and an invitation system for adding team members. This enables both individual users and enterprise teams to use the platform collaboratively.

## Alignment with Product Vision

Profile and company management enables the Autopilot platform by providing:
- **Individual Access**: Personal profiles for buyers exploring procurement options
- **Team Collaboration**: Company accounts allow procurement teams to share conversations
- **Sales Enablement**: Company structure supports enterprise sales workflows
- **Data Ownership**: All user data is tied to identifiable profiles

## Requirements

### Requirement 1: Individual User Profile

**User Story:** As a user, I want a profile associated with my account, so that my information and preferences are stored.

#### Acceptance Criteria

1. WHEN a user first authenticates THEN the system SHALL auto-create a profile if one doesn't exist
2. WHEN a profile is created THEN the system SHALL store user_id, display_name, email, and avatar_url
3. WHEN a user requests their profile (GET /profiles/me) THEN the system SHALL return their profile data
4. WHEN a user updates their profile (PUT /profiles/me) THEN the system SHALL update allowed fields
5. IF a user tries to access another user's profile directly THEN the system SHALL return 403 Forbidden

### Requirement 2: Company Account Creation

**User Story:** As a user, I want to create a company account, so that I can invite team members to collaborate.

#### Acceptance Criteria

1. WHEN a user creates a company (POST /companies) THEN the system SHALL create the company with the user as owner
2. WHEN a company is created THEN the system SHALL store name, owner_id, and created_at
3. WHEN a company is created THEN the system SHALL automatically add the owner as a company member
4. WHEN a user requests company details (GET /companies/{id}) THEN the system SHALL return company data if user is a member
5. IF a non-member tries to access company details THEN the system SHALL return 403 Forbidden

### Requirement 3: Company Member Management

**User Story:** As a company owner, I want to see all members of my company, so that I can manage team access.

#### Acceptance Criteria

1. WHEN a user requests company members (GET /companies/{id}/members) THEN the system SHALL return all members
2. WHEN member data is returned THEN the system SHALL include profile information, role, and joined_at
3. WHEN listing members THEN the system SHALL indicate which member is the owner
4. WHEN a member is removed THEN the system SHALL delete their company_member record
5. IF the owner is removed THEN the system SHALL return 400 Bad Request (owner cannot be removed)

### Requirement 4: Invitation System

**User Story:** As a company owner, I want to invite users by email, so that they can join my company.

#### Acceptance Criteria

1. WHEN an owner creates an invitation (POST /companies/{id}/invitations) THEN the system SHALL create a pending invitation record
2. WHEN an invitation is created THEN the system SHALL store company_id, email, invited_by, status, and expires_at
3. WHEN an invitation is created THEN the system SHALL set status to "pending" and expiration to 7 days
4. WHEN a user accepts an invitation (POST /invitations/{id}/accept) THEN the system SHALL add them as a company member
5. WHEN an invitation is accepted THEN the system SHALL update status to "accepted"
6. IF an invitation is expired THEN the system SHALL return 400 Bad Request on accept attempt
7. IF a user is already a member THEN the system SHALL return 400 Bad Request on accept attempt
8. WHEN listing invitations (GET /companies/{id}/invitations) THEN the system SHALL return all invitations for the company

### Requirement 5: User's Company Listing

**User Story:** As a user, I want to see all companies I belong to, so that I can switch between team contexts.

#### Acceptance Criteria

1. WHEN a user requests their companies (GET /profiles/me/companies) THEN the system SHALL return all companies they are a member of
2. WHEN companies are listed THEN the system SHALL include the user's role in each company
3. WHEN companies are listed THEN the system SHALL indicate which companies the user owns

### Requirement 6: Simple Owner + Members Permission Model

**User Story:** As a system, I want to enforce simple permissions, so that owners have full control and members have equal access.

#### Acceptance Criteria

1. WHEN checking permissions THEN the system SHALL treat all members (except owner) equally
2. WHEN an owner action is required (invite, remove member) THEN the system SHALL verify the user is the owner
3. WHEN a member action is required (view data) THEN the system SHALL verify the user is any member
4. IF a non-owner attempts owner-only action THEN the system SHALL return 403 Forbidden

### Requirement 7: Discovery Profile Association (NEW)

**User Story:** As a user, I want my discovery journey data stored with my profile, so that I can review and continue my procurement exploration.

#### Acceptance Criteria

1. WHEN a user has a profile THEN the system SHALL support an associated discovery_profile
2. WHEN discovery_profile is queried THEN the system SHALL return answers, ROI inputs, and selections
3. WHEN discovery_profile is updated THEN the system SHALL store discovery session data
4. WHEN a profile is deleted THEN the system SHALL cascade delete the discovery_profile

### Requirement 8: Session Claim Integration (NEW)

**User Story:** As a user who started anonymously, I want my session data transferred to my profile on signup, so that I don't lose my progress.

#### Acceptance Criteria

1. WHEN a user claims a session THEN the system SHALL create a discovery_profile with session data
2. WHEN session is claimed THEN the system SHALL transfer conversation ownership to the profile
3. WHEN session is claimed THEN the system SHALL transfer order ownership to the profile
4. WHEN profile already has discovery_profile THEN the system SHALL merge session data appropriately
5. WHEN session is claimed THEN the system SHALL mark the session as claimed

## Non-Functional Requirements

### Performance
- Profile lookup SHALL complete in under 50ms
- Company member listing SHALL complete in under 100ms for up to 50 members
- All profile/company endpoints SHALL be paginated if returning lists

### Security
- Users SHALL only access their own profile data
- Company data SHALL only be accessible to company members
- Invitation tokens SHALL be unique and unguessable (UUID)
- Expired invitations SHALL not be accepted

### Reliability
- Profile creation SHALL be idempotent (same user_id always returns same profile)
- Company member operations SHALL use database transactions
- Invitation acceptance SHALL be atomic (member creation + status update)

### Usability
- Error messages SHALL clearly indicate permission issues
- API responses SHALL include relevant relationship data (owner info, member count)
- Pagination SHALL use cursor-based approach for consistency

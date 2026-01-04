"""Integration tests for company API endpoints."""

import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt


TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests"


def create_test_token(
    sub: str = "550e8400-e29b-41d4-a716-446655440000",
    email: str = "test@example.com",
) -> str:
    """Create a test JWT token."""
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "role": "user",
        "exp": now + 3600,
        "iat": now,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


class TestCreateCompany:
    """Tests for POST /api/v1/companies endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    @patch("src.services.company_service.get_supabase_client")
    def test_creates_company(
        self,
        mock_company_supabase: MagicMock,
        mock_profile_supabase: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that company is created."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "test@example.com",
        }

        company_data = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "name": "New Company",
            "owner_id": "660e8400-e29b-41d4-a716-446655440000",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        profile_response = MagicMock()
        profile_response.data = [profile_data]
        mock_profile_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            profile_response
        )

        company_response = MagicMock()
        company_response.data = [company_data]
        mock_company_supabase.return_value.table.return_value.insert.return_value.execute.return_value = (
            company_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/companies",
                headers={"Authorization": f"Bearer {token}"},
                json={"name": "New Company"},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "New Company"

    def test_returns_401_without_auth(self, mock_supabase_client: MagicMock) -> None:
        """Test that 401 is returned without auth header."""
        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/companies",
                json={"name": "New Company"},
            )
            assert response.status_code == 401


class TestGetCompany:
    """Tests for GET /api/v1/companies/{id} endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    @patch("src.services.company_service.get_supabase_client")
    def test_returns_company_for_member(
        self,
        mock_company_supabase: MagicMock,
        mock_profile_supabase: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that company is returned for members."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
        }

        company_data = {
            "id": "770e8400-e29b-41d4-a716-446655440000",
            "name": "Test Company",
            "owner_id": "660e8400-e29b-41d4-a716-446655440000",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        profile_response = MagicMock()
        profile_response.data = [profile_data]
        mock_profile_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            profile_response
        )

        company_response = MagicMock()
        company_response.data = company_data
        mock_company_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            company_response
        )

        # Mock is_member to return True
        member_response = MagicMock()
        member_response.data = [{"id": "some-id"}]
        mock_company_supabase.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            member_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/companies/770e8400-e29b-41d4-a716-446655440000",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Test Company"


class TestListCompanyMembers:
    """Tests for GET /api/v1/companies/{id}/members endpoint."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    @patch("src.services.company_service.get_supabase_client")
    def test_returns_members_for_company_member(
        self,
        mock_company_supabase: MagicMock,
        mock_profile_supabase: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that members are returned for company members."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
        }

        profile_response = MagicMock()
        profile_response.data = [profile_data]
        mock_profile_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            profile_response
        )

        # Mock is_member
        member_check_response = MagicMock()
        member_check_response.data = [{"id": "some-id"}]
        mock_company_supabase.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            member_check_response
        )

        # Mock get_members
        members_data = [
            {
                "id": "880e8400-e29b-41d4-a716-446655440000",
                "company_id": "770e8400-e29b-41d4-a716-446655440000",
                "profile_id": "660e8400-e29b-41d4-a716-446655440000",
                "role": "owner",
                "joined_at": "2024-01-01T00:00:00Z",
                "profiles": {
                    "id": "660e8400-e29b-41d4-a716-446655440000",
                    "display_name": "Test User",
                    "email": "test@example.com",
                    "avatar_url": None,
                },
            }
        ]
        members_response = MagicMock()
        members_response.data = members_data
        mock_company_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            members_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/companies/770e8400-e29b-41d4-a716-446655440000/members",
                headers={"Authorization": f"Bearer {token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["role"] == "owner"
            assert data[0]["profile"]["display_name"] == "Test User"


class TestInvitationFlow:
    """Tests for invitation create/accept flow."""

    @patch("src.api.middleware.auth.get_settings")
    @patch("src.services.profile_service.get_supabase_client")
    @patch("src.services.company_service.get_supabase_client")
    @patch("src.services.invitation_service.get_supabase_client")
    def test_owner_can_create_invitation(
        self,
        mock_invitation_supabase: MagicMock,
        mock_company_supabase: MagicMock,
        mock_profile_supabase: MagicMock,
        mock_settings: MagicMock,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test that owner can create invitation."""
        mock_settings.return_value.supabase_signing_key_jwk = TEST_JWT_SECRET

        profile_data = {
            "id": "660e8400-e29b-41d4-a716-446655440000",
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
        }

        profile_response = MagicMock()
        profile_response.data = [profile_data]
        mock_profile_supabase.return_value.table.return_value.select.return_value.eq.return_value.execute.return_value = (
            profile_response
        )

        # Mock is_owner
        owner_response = MagicMock()
        owner_response.data = [{"id": "770e8400-e29b-41d4-a716-446655440000"}]
        mock_company_supabase.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
            owner_response
        )

        # Mock invitation creation
        invitation_data = {
            "id": "990e8400-e29b-41d4-a716-446655440000",
            "company_id": "770e8400-e29b-41d4-a716-446655440000",
            "email": "invite@example.com",
            "invited_by": "660e8400-e29b-41d4-a716-446655440000",
            "status": "pending",
            "expires_at": "2024-01-08T00:00:00Z",
            "created_at": "2024-01-01T00:00:00Z",
            "accepted_at": None,
        }
        invitation_response = MagicMock()
        invitation_response.data = [invitation_data]
        mock_invitation_supabase.return_value.table.return_value.insert.return_value.execute.return_value = (
            invitation_response
        )

        token = create_test_token()

        from src.main import app

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/companies/770e8400-e29b-41d4-a716-446655440000/invitations",
                headers={"Authorization": f"Bearer {token}"},
                json={"email": "invite@example.com"},
            )

            assert response.status_code == 201
            data = response.json()
            assert data["email"] == "invite@example.com"
            assert data["status"] == "pending"

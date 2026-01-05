"""Integration tests for session API endpoints."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestCreateSession:
    """Tests for POST /api/v1/sessions endpoint."""

    @patch("src.services.session_service.get_supabase_client")
    def test_creates_session_and_sets_cookie(
        self, mock_supabase: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that session is created and cookie is set."""
        new_session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": "a" * 64,
            "current_question_index": 0,
            "phase": "discovery",
            "answers": {},
            "selected_product_ids": [],
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        mock_response = MagicMock()
        mock_response.data = [new_session]
        mock_supabase.return_value.table.return_value.insert.return_value.execute.return_value = (
            mock_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.post("/api/v1/sessions")

            assert response.status_code == 201
            data = response.json()
            assert data["phase"] == "discovery"
            assert data["current_question_index"] == 0

            # Check that cookie is set
            assert "autopilot_session" in response.cookies


class TestGetMySession:
    """Tests for GET /api/v1/sessions/me endpoint."""

    @patch("src.services.session_service.get_supabase_client")
    def test_returns_session_for_valid_cookie(
        self, mock_supabase: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that session is returned when cookie is valid."""
        session_token = "a" * 64
        session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": session_token,
            "current_question_index": 5,
            "phase": "roi",
            "answers": {},
            "roi_inputs": None,
            "selected_product_ids": [],
            "timeframe": None,
            "conversation_id": None,
            "claimed_by_profile_id": None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        mock_response = MagicMock()
        mock_response.data = session
        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/sessions/me",
                cookies={"autopilot_session": session_token},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["phase"] == "roi"
            assert data["current_question_index"] == 5

    @patch("src.services.session_service.get_supabase_client")
    def test_creates_session_when_no_cookie(
        self, mock_supabase: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that new session is created when no cookie exists."""
        new_session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": "a" * 64,
            "current_question_index": 0,
            "phase": "discovery",
            "answers": {},
            "selected_product_ids": [],
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # First call for validation returns None (no existing session)
        mock_response_none = MagicMock()
        mock_response_none.data = None

        # Second call for create returns new session
        mock_response_new = MagicMock()
        mock_response_new.data = [new_session]

        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_response_none
        )
        mock_supabase.return_value.table.return_value.insert.return_value.execute.return_value = (
            mock_response_new
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/sessions/me")

            # Check that new session is created and cookie is set
            assert response.status_code == 200
            assert "autopilot_session" in response.cookies


class TestUpdateMySession:
    """Tests for PUT /api/v1/sessions/me endpoint."""

    @patch("src.services.session_service.get_supabase_client")
    def test_updates_session_phase(
        self, mock_supabase: MagicMock, mock_supabase_client: MagicMock
    ) -> None:
        """Test that session phase is updated."""
        session_token = "a" * 64
        session = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "session_token": session_token,
            "current_question_index": 0,
            "phase": "discovery",
            "answers": {},
            "claimed_by_profile_id": None,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        }

        updated_session = {
            **session,
            "phase": "roi",
            "current_question_index": 10,
        }

        # Mock for is_session_valid
        mock_response = MagicMock()
        mock_response.data = session
        mock_supabase.return_value.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = (
            mock_response
        )

        # Mock for update
        mock_update_response = MagicMock()
        mock_update_response.data = [updated_session]
        mock_supabase.return_value.table.return_value.update.return_value.eq.return_value.execute.return_value = (
            mock_update_response
        )

        from src.main import app

        with TestClient(app) as client:
            response = client.put(
                "/api/v1/sessions/me",
                cookies={"autopilot_session": session_token},
                json={"phase": "roi", "current_question_index": 10},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["phase"] == "roi"
            assert data["current_question_index"] == 10

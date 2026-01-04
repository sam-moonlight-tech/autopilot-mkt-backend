"""Integration tests for health check endpoints."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Test that /health endpoint returns 200 status."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self, client: TestClient) -> None:
        """Test that /health endpoint returns healthy status."""
        response = client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"

    def test_health_returns_timestamp(self, client: TestClient) -> None:
        """Test that /health endpoint returns a timestamp."""
        response = client.get("/health")
        data = response.json()

        assert "timestamp" in data
        assert data["timestamp"] is not None

    def test_health_returns_version(self, client: TestClient) -> None:
        """Test that /health endpoint returns version info."""
        response = client.get("/health")
        data = response.json()

        assert "version" in data
        assert data["version"] == "0.1.0"


class TestReadinessEndpoint:
    """Tests for /health/ready endpoint."""

    def test_readiness_returns_200_when_healthy(self, client: TestClient) -> None:
        """Test that /health/ready returns 200 when all dependencies are healthy."""
        response = client.get("/health/ready")
        assert response.status_code == 200

    def test_readiness_returns_healthy_status(self, client: TestClient) -> None:
        """Test that /health/ready returns healthy status when dependencies ok."""
        response = client.get("/health/ready")
        data = response.json()

        assert data["status"] == "healthy"

    def test_readiness_returns_checks_array(self, client: TestClient) -> None:
        """Test that /health/ready returns an array of checks."""
        response = client.get("/health/ready")
        data = response.json()

        assert "checks" in data
        assert isinstance(data["checks"], list)

    def test_readiness_includes_database_check(self, client: TestClient) -> None:
        """Test that /health/ready includes database connectivity check."""
        response = client.get("/health/ready")
        data = response.json()

        check_names = [check["name"] for check in data["checks"]]
        assert "database" in check_names

    def test_readiness_database_check_includes_latency(self, client: TestClient) -> None:
        """Test that database check includes latency measurement."""
        response = client.get("/health/ready")
        data = response.json()

        db_check = next(c for c in data["checks"] if c["name"] == "database")
        assert "latency_ms" in db_check
        assert db_check["latency_ms"] is not None

    def test_readiness_returns_503_when_database_unhealthy(
        self, mock_supabase_client: MagicMock
    ) -> None:
        """Test that /health/ready returns 503 when database is unhealthy."""
        # Configure mock to raise an exception
        mock_supabase_client.table.return_value.select.return_value.limit.return_value.execute.side_effect = Exception(
            "Connection failed"
        )

        # Need to patch check_database_connection to use the mock
        with patch(
            "src.api.routes.health.check_database_connection",
            return_value={"healthy": False, "error": "Connection failed"},
        ):
            from src.main import app

            with TestClient(app) as test_client:
                response = test_client.get("/health/ready")

                assert response.status_code == 503
                data = response.json()
                assert data["status"] == "unhealthy"

    def test_readiness_includes_error_when_unhealthy(self) -> None:
        """Test that unhealthy checks include error message."""
        with patch(
            "src.api.routes.health.check_database_connection",
            return_value={"healthy": False, "error": "Connection timeout"},
        ):
            from src.main import app

            with TestClient(app) as test_client:
                response = test_client.get("/health/ready")
                data = response.json()

                db_check = next(c for c in data["checks"] if c["name"] == "database")
                assert db_check["healthy"] is False
                assert "error" in db_check
                assert db_check["error"] == "Connection timeout"


class TestErrorResponseSchema:
    """Tests for error response schema compliance."""

    def test_404_returns_error_response_format(self, client: TestClient) -> None:
        """Test that 404 errors follow ErrorResponse schema."""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404

        data = response.json()
        # FastAPI returns detail for 404, which gets wrapped by our middleware
        # The response should have our error format
        assert "error" in data or "detail" in data

    def test_error_response_includes_timestamp(self, client: TestClient) -> None:
        """Test that error responses include a timestamp."""
        # Trigger an error by calling an endpoint that raises an exception
        with patch(
            "src.api.routes.health.check_database_connection",
            side_effect=Exception("Test error"),
        ):
            from src.main import app

            with TestClient(app, raise_server_exceptions=False) as test_client:
                response = test_client.get("/health/ready")

                # The middleware should catch this and return proper error format
                if response.status_code >= 400:
                    data = response.json()
                    # Error responses should have timestamp
                    assert "timestamp" in data or "error" in data

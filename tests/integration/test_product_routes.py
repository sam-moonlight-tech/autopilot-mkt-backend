"""Integration tests for product API routes."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_product_service() -> MagicMock:
    """Create mock product service."""
    return MagicMock()


@pytest.fixture
def sample_product() -> dict:
    """Create sample product data."""
    return {
        "id": str(uuid4()),
        "name": "UR10e Collaborative Robot",
        "description": "Versatile cobot for heavy-duty applications.",
        "category": "collaborative_robot",
        "specs": {"payload_kg": 10, "reach_mm": 1300},
        "pricing": {"base_price_usd": 45000},
        "image_url": None,
        "manufacturer": "Universal Robots",
        "model_number": "UR10e",
        "embedding_id": "product_123",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


@pytest.fixture
def valid_jwt_token() -> str:
    """Create a valid JWT token for testing."""
    # This would be a valid test token in a real test environment
    return "valid.test.token"


class TestListProducts:
    """Tests for GET /api/v1/products endpoint."""

    def test_list_products_success(
        self, client: TestClient, sample_product: dict
    ) -> None:
        """Test listing products successfully."""
        with patch("src.api.routes.products.get_product_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.list_products = AsyncMock(
                return_value={
                    "products": [sample_product],
                    "next_cursor": None,
                    "has_more": False,
                }
            )
            mock_get_service.return_value = mock_service

            response = client.get("/api/v1/products")

            assert response.status_code == 200
            data = response.json()
            assert len(data["products"]) == 1
            assert data["products"][0]["name"] == "UR10e Collaborative Robot"
            assert data["has_more"] is False

    def test_list_products_with_pagination(
        self, client: TestClient, sample_product: dict
    ) -> None:
        """Test listing products with pagination parameters."""
        with patch("src.api.routes.products.get_product_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.list_products = AsyncMock(
                return_value={
                    "products": [sample_product],
                    "next_cursor": "next-cursor-id",
                    "has_more": True,
                }
            )
            mock_get_service.return_value = mock_service

            response = client.get("/api/v1/products?limit=10&cursor=some-cursor")

            assert response.status_code == 200
            data = response.json()
            assert data["has_more"] is True
            assert data["next_cursor"] == "next-cursor-id"

    def test_list_products_with_category_filter(
        self, client: TestClient, sample_product: dict
    ) -> None:
        """Test listing products filtered by category."""
        with patch("src.api.routes.products.get_product_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.list_products = AsyncMock(
                return_value={
                    "products": [sample_product],
                    "next_cursor": None,
                    "has_more": False,
                }
            )
            mock_get_service.return_value = mock_service

            response = client.get("/api/v1/products?category=collaborative_robot")

            assert response.status_code == 200
            mock_service.list_products.assert_called_with(
                category="collaborative_robot",
                manufacturer=None,
                cursor=None,
                limit=20,
            )


class TestGetProduct:
    """Tests for GET /api/v1/products/{product_id} endpoint."""

    def test_get_product_success(
        self, client: TestClient, sample_product: dict
    ) -> None:
        """Test getting a product by ID."""
        product_id = sample_product["id"]

        with patch("src.api.routes.products.get_product_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_product = AsyncMock(return_value=sample_product)
            mock_get_service.return_value = mock_service

            response = client.get(f"/api/v1/products/{product_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "UR10e Collaborative Robot"

    def test_get_product_not_found(self, client: TestClient) -> None:
        """Test getting a non-existent product."""
        product_id = uuid4()

        with patch("src.api.routes.products.get_product_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_product = AsyncMock(return_value=None)
            mock_get_service.return_value = mock_service

            response = client.get(f"/api/v1/products/{product_id}")

            assert response.status_code == 404
            assert response.json()["detail"] == "Product not found"


class TestCreateProduct:
    """Tests for POST /api/v1/products endpoint."""

    def test_create_product_requires_auth(self, client: TestClient) -> None:
        """Test that creating a product requires authentication."""
        response = client.post(
            "/api/v1/products",
            json={
                "name": "Test Robot",
                "category": "collaborative_robot",
            },
        )

        assert response.status_code == 401

    def test_create_product_success(
        self, client: TestClient, sample_product: dict
    ) -> None:
        """Test creating a product with valid auth."""
        with patch("src.api.routes.products.get_product_service") as mock_get_service:
            with patch("src.api.deps.decode_jwt") as mock_decode:
                mock_decode.return_value = {
                    "sub": str(uuid4()),
                    "email": "test@example.com",
                    "role": "authenticated",
                }

                mock_service = MagicMock()
                mock_service.create_product = AsyncMock(return_value=sample_product)
                mock_get_service.return_value = mock_service

                response = client.post(
                    "/api/v1/products",
                    json={
                        "name": "Test Robot",
                        "category": "collaborative_robot",
                    },
                    headers={"Authorization": "Bearer valid-token"},
                )

                assert response.status_code == 201
                data = response.json()
                assert data["name"] == "UR10e Collaborative Robot"


class TestDeleteProduct:
    """Tests for DELETE /api/v1/products/{product_id} endpoint."""

    def test_delete_product_requires_auth(self, client: TestClient) -> None:
        """Test that deleting a product requires authentication."""
        response = client.delete(f"/api/v1/products/{uuid4()}")

        assert response.status_code == 401

    def test_delete_product_success(self, client: TestClient) -> None:
        """Test deleting a product with valid auth."""
        product_id = uuid4()

        with patch("src.api.routes.products.get_product_service") as mock_get_service:
            with patch("src.api.deps.decode_jwt") as mock_decode:
                mock_decode.return_value = {
                    "sub": str(uuid4()),
                    "email": "test@example.com",
                    "role": "authenticated",
                }

                mock_service = MagicMock()
                mock_service.delete_product = AsyncMock(return_value=True)
                mock_get_service.return_value = mock_service

                response = client.delete(
                    f"/api/v1/products/{product_id}",
                    headers={"Authorization": "Bearer valid-token"},
                )

                assert response.status_code == 204

    def test_delete_product_not_found(self, client: TestClient) -> None:
        """Test deleting a non-existent product."""
        product_id = uuid4()

        with patch("src.api.routes.products.get_product_service") as mock_get_service:
            with patch("src.api.deps.decode_jwt") as mock_decode:
                mock_decode.return_value = {
                    "sub": str(uuid4()),
                    "email": "test@example.com",
                    "role": "authenticated",
                }

                mock_service = MagicMock()
                mock_service.delete_product = AsyncMock(return_value=False)
                mock_get_service.return_value = mock_service

                response = client.delete(
                    f"/api/v1/products/{product_id}",
                    headers={"Authorization": "Bearer valid-token"},
                )

                assert response.status_code == 404


class TestSearchProducts:
    """Tests for POST /api/v1/products/search endpoint."""

    def test_search_products_success(
        self, client: TestClient, sample_product: dict
    ) -> None:
        """Test searching products."""
        with patch("src.api.routes.products.get_product_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.search_products = AsyncMock(
                return_value=[
                    {"product": sample_product, "score": 0.95}
                ]
            )
            mock_get_service.return_value = mock_service

            response = client.post(
                "/api/v1/products/search",
                json={
                    "query": "collaborative robot for palletizing",
                    "top_k": 5,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 1
            assert data["results"][0]["score"] == 0.95
            assert data["query"] == "collaborative robot for palletizing"
            assert data["total"] == 1

    def test_search_products_with_category(
        self, client: TestClient, sample_product: dict
    ) -> None:
        """Test searching products with category filter."""
        with patch("src.api.routes.products.get_product_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.search_products = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            response = client.post(
                "/api/v1/products/search",
                json={
                    "query": "robot",
                    "category": "collaborative_robot",
                    "top_k": 10,
                },
            )

            assert response.status_code == 200
            mock_service.search_products.assert_called_with(
                query="robot",
                category="collaborative_robot",
                top_k=10,
            )

    def test_search_products_empty_results(self, client: TestClient) -> None:
        """Test searching with no results."""
        with patch("src.api.routes.products.get_product_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.search_products = AsyncMock(return_value=[])
            mock_get_service.return_value = mock_service

            response = client.post(
                "/api/v1/products/search",
                json={"query": "nonexistent product"},
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 0
            assert data["total"] == 0


class TestIndexAllProducts:
    """Tests for POST /api/v1/products/index-all endpoint."""

    def test_index_all_requires_auth(self, client: TestClient) -> None:
        """Test that indexing all products requires authentication."""
        response = client.post("/api/v1/products/index-all")

        assert response.status_code == 401

    def test_index_all_success(self, client: TestClient) -> None:
        """Test indexing all products with valid auth."""
        with patch("src.api.routes.products.get_product_service") as mock_get_service:
            with patch("src.api.deps.decode_jwt") as mock_decode:
                mock_decode.return_value = {
                    "sub": str(uuid4()),
                    "email": "admin@example.com",
                    "role": "authenticated",
                }

                mock_service = MagicMock()
                mock_service.index_all_products = AsyncMock(
                    return_value={
                        "total": 10,
                        "indexed": 10,
                        "failed": 0,
                    }
                )
                mock_get_service.return_value = mock_service

                response = client.post(
                    "/api/v1/products/index-all",
                    headers={"Authorization": "Bearer valid-token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 10
                assert data["indexed"] == 10
                assert data["failed"] == 0

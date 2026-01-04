"""Unit tests for ProductService."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.services.product_service import ProductService


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Create a mock Supabase client."""
    return MagicMock()


@pytest.fixture
def mock_rag_service() -> MagicMock:
    """Create a mock RAG service."""
    rag_service = MagicMock()
    rag_service.index_product = AsyncMock(return_value="product_test-id")
    rag_service.delete_product_embedding = AsyncMock()
    rag_service.search_products = AsyncMock(return_value=[])
    return rag_service


@pytest.fixture
def sample_product() -> dict:
    """Create a sample product."""
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
        "embedding_id": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


class TestCreateProduct:
    """Tests for create_product method."""

    @pytest.mark.asyncio
    async def test_create_product_success(
        self, mock_supabase: MagicMock, mock_rag_service: MagicMock, sample_product: dict
    ) -> None:
        """Test successful product creation."""
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_product]
        )
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{**sample_product, "embedding_id": "product_test-id"}]
        )

        service = ProductService(
            supabase_client=mock_supabase, rag_service=mock_rag_service
        )
        result = await service.create_product(
            data={"name": "Test Robot", "category": "collaborative_robot"},
            index_embedding=True,
        )

        assert result is not None
        mock_supabase.table.assert_called()
        mock_rag_service.index_product.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_product_without_indexing(
        self, mock_supabase: MagicMock, mock_rag_service: MagicMock, sample_product: dict
    ) -> None:
        """Test product creation without embedding indexing."""
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[sample_product]
        )

        service = ProductService(
            supabase_client=mock_supabase, rag_service=mock_rag_service
        )
        result = await service.create_product(
            data={"name": "Test Robot", "category": "collaborative_robot"},
            index_embedding=False,
        )

        assert result is not None
        mock_rag_service.index_product.assert_not_called()


class TestGetProduct:
    """Tests for get_product method."""

    @pytest.mark.asyncio
    async def test_get_product_found(
        self, mock_supabase: MagicMock, sample_product: dict
    ) -> None:
        """Test getting an existing product."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_product]
        )

        service = ProductService(supabase_client=mock_supabase)
        result = await service.get_product(uuid4())

        assert result is not None
        assert result["name"] == "UR10e Collaborative Robot"

    @pytest.mark.asyncio
    async def test_get_product_not_found(self, mock_supabase: MagicMock) -> None:
        """Test getting a non-existent product."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        service = ProductService(supabase_client=mock_supabase)
        result = await service.get_product(uuid4())

        assert result is None


class TestUpdateProduct:
    """Tests for update_product method."""

    @pytest.mark.asyncio
    async def test_update_product_success(
        self, mock_supabase: MagicMock, mock_rag_service: MagicMock, sample_product: dict
    ) -> None:
        """Test successful product update."""
        updated_product = {**sample_product, "name": "Updated Robot"}
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[updated_product]
        )

        service = ProductService(
            supabase_client=mock_supabase, rag_service=mock_rag_service
        )
        result = await service.update_product(
            product_id=uuid4(),
            data={"name": "Updated Robot"},
            reindex_embedding=True,
        )

        assert result is not None
        assert result["name"] == "Updated Robot"

    @pytest.mark.asyncio
    async def test_update_product_not_found(
        self, mock_supabase: MagicMock, mock_rag_service: MagicMock
    ) -> None:
        """Test updating a non-existent product."""
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        service = ProductService(
            supabase_client=mock_supabase, rag_service=mock_rag_service
        )
        result = await service.update_product(
            product_id=uuid4(),
            data={"name": "Updated Robot"},
        )

        assert result is None


class TestDeleteProduct:
    """Tests for delete_product method."""

    @pytest.mark.asyncio
    async def test_delete_product_success(
        self, mock_supabase: MagicMock, mock_rag_service: MagicMock, sample_product: dict
    ) -> None:
        """Test successful product deletion."""
        product_with_embedding = {**sample_product, "embedding_id": "product_123"}

        # Mock get_product
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[product_with_embedding]
        )
        # Mock delete
        mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[product_with_embedding]
        )

        service = ProductService(
            supabase_client=mock_supabase, rag_service=mock_rag_service
        )
        result = await service.delete_product(uuid4())

        assert result is True
        mock_rag_service.delete_product_embedding.assert_called_once_with("product_123")

    @pytest.mark.asyncio
    async def test_delete_product_not_found(self, mock_supabase: MagicMock) -> None:
        """Test deleting a non-existent product."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[]
        )

        service = ProductService(supabase_client=mock_supabase)
        result = await service.delete_product(uuid4())

        assert result is False


class TestListProducts:
    """Tests for list_products method."""

    @pytest.mark.asyncio
    async def test_list_products_success(
        self, mock_supabase: MagicMock, sample_product: dict
    ) -> None:
        """Test listing products."""
        mock_query = MagicMock()
        mock_query.order.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[sample_product])
        mock_supabase.table.return_value.select.return_value = mock_query

        service = ProductService(supabase_client=mock_supabase)
        result = await service.list_products(limit=20)

        assert "products" in result
        assert len(result["products"]) == 1
        assert result["has_more"] is False

    @pytest.mark.asyncio
    async def test_list_products_with_pagination(
        self, mock_supabase: MagicMock, sample_product: dict
    ) -> None:
        """Test listing products with pagination."""
        # Return more products than limit to indicate has_more
        products = [sample_product for _ in range(21)]

        mock_query = MagicMock()
        mock_query.order.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=products)
        mock_supabase.table.return_value.select.return_value = mock_query

        service = ProductService(supabase_client=mock_supabase)
        result = await service.list_products(limit=20)

        assert result["has_more"] is True
        assert len(result["products"]) == 20

    @pytest.mark.asyncio
    async def test_list_products_with_category_filter(
        self, mock_supabase: MagicMock, sample_product: dict
    ) -> None:
        """Test listing products with category filter."""
        mock_query = MagicMock()
        mock_query.order.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[sample_product])
        mock_supabase.table.return_value.select.return_value = mock_query

        service = ProductService(supabase_client=mock_supabase)
        result = await service.list_products(category="collaborative_robot")

        assert "products" in result
        mock_query.eq.assert_called()


class TestSearchProducts:
    """Tests for search_products method."""

    @pytest.mark.asyncio
    async def test_search_products_success(
        self, mock_supabase: MagicMock, mock_rag_service: MagicMock, sample_product: dict
    ) -> None:
        """Test searching products."""
        mock_rag_service.search_products = AsyncMock(
            return_value=[
                {"product_id": sample_product["id"], "score": 0.95}
            ]
        )

        # Mock get_product
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_product]
        )

        service = ProductService(
            supabase_client=mock_supabase, rag_service=mock_rag_service
        )
        results = await service.search_products("collaborative robot", top_k=5)

        assert len(results) == 1
        assert results[0]["score"] == 0.95
        assert results[0]["product"]["name"] == "UR10e Collaborative Robot"

    @pytest.mark.asyncio
    async def test_search_products_empty_results(
        self, mock_supabase: MagicMock, mock_rag_service: MagicMock
    ) -> None:
        """Test searching with no results."""
        mock_rag_service.search_products = AsyncMock(return_value=[])

        service = ProductService(
            supabase_client=mock_supabase, rag_service=mock_rag_service
        )
        results = await service.search_products("nonexistent product")

        assert len(results) == 0


class TestIndexAllProducts:
    """Tests for index_all_products method."""

    @pytest.mark.asyncio
    async def test_index_all_products_success(
        self, mock_supabase: MagicMock, mock_rag_service: MagicMock, sample_product: dict
    ) -> None:
        """Test indexing all products."""
        mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[sample_product]
        )
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_product]
        )

        service = ProductService(
            supabase_client=mock_supabase, rag_service=mock_rag_service
        )
        result = await service.index_all_products()

        assert result["total"] == 1
        assert result["indexed"] == 1
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_index_all_products_with_failures(
        self, mock_supabase: MagicMock, mock_rag_service: MagicMock, sample_product: dict
    ) -> None:
        """Test indexing all products with some failures."""
        mock_supabase.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[sample_product, sample_product]
        )
        mock_rag_service.index_product = AsyncMock(
            side_effect=[Exception("Failed"), "product_test-id"]
        )
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[sample_product]
        )

        service = ProductService(
            supabase_client=mock_supabase, rag_service=mock_rag_service
        )
        result = await service.index_all_products()

        assert result["total"] == 2
        assert result["indexed"] == 1
        assert result["failed"] == 1


class TestGetProductsByIds:
    """Tests for get_products_by_ids method."""

    @pytest.mark.asyncio
    async def test_get_products_by_ids_success(
        self, mock_supabase: MagicMock, sample_product: dict
    ) -> None:
        """Test getting multiple products by IDs."""
        mock_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
            data=[sample_product]
        )

        service = ProductService(supabase_client=mock_supabase)
        results = await service.get_products_by_ids([uuid4()])

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_products_by_ids_empty_list(
        self, mock_supabase: MagicMock
    ) -> None:
        """Test getting products with empty ID list."""
        service = ProductService(supabase_client=mock_supabase)
        results = await service.get_products_by_ids([])

        assert len(results) == 0
        mock_supabase.table.assert_not_called()

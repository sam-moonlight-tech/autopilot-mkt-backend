"""Unit tests for RAGService."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.services.rag_service import RAGService


class TestBuildEmbeddingText:
    """Tests for build_embedding_text method."""

    def test_build_embedding_text_basic(self) -> None:
        """Test building embedding text with basic fields."""
        service = RAGService()
        product_data = {
            "name": "UR10e Collaborative Robot",
            "manufacturer": "Universal Robots",
            "category": "collaborative_robot",
            "description": "Versatile cobot for heavy-duty applications.",
        }

        result = service.build_embedding_text(product_data)

        assert "Product: UR10e Collaborative Robot" in result
        assert "Manufacturer: Universal Robots" in result
        assert "Category: Collaborative Robot" in result
        assert "Description: Versatile cobot for heavy-duty applications." in result

    def test_build_embedding_text_with_specs(self) -> None:
        """Test building embedding text with specifications."""
        service = RAGService()
        product_data = {
            "name": "Test Robot",
            "specs": {
                "payload_kg": 10,
                "reach_mm": 1300,
            },
        }

        result = service.build_embedding_text(product_data)

        assert "Product: Test Robot" in result
        assert "Specifications:" in result
        assert "Payload Kg: 10" in result
        assert "Reach Mm: 1300" in result

    def test_build_embedding_text_with_pricing(self) -> None:
        """Test building embedding text with pricing information."""
        service = RAGService()
        product_data = {
            "name": "Test Robot",
            "pricing": {
                "base_price_usd": 45000,
                "installation_usd": 5000,
            },
        }

        result = service.build_embedding_text(product_data)

        assert "Product: Test Robot" in result
        assert "Pricing:" in result
        assert "$45,000" in result
        assert "$5,000" in result

    def test_build_embedding_text_empty_data(self) -> None:
        """Test building embedding text with empty data."""
        service = RAGService()
        product_data = {}

        result = service.build_embedding_text(product_data)

        assert result == ""

    def test_build_embedding_text_with_model_number(self) -> None:
        """Test building embedding text with model number."""
        service = RAGService()
        product_data = {
            "name": "UR10e",
            "model_number": "UR10e-V2",
        }

        result = service.build_embedding_text(product_data)

        assert "Model: UR10e-V2" in result


class TestGenerateEmbedding:
    """Tests for generate_embedding method."""

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self) -> None:
        """Test successful embedding generation."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        mock_client.embeddings.create.return_value = mock_response

        service = RAGService(openai_client=mock_client)
        result = await service.generate_embedding("test text")

        assert result == [0.1, 0.2, 0.3]
        mock_client.embeddings.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_failure(self) -> None:
        """Test embedding generation failure handling."""
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("API error")

        service = RAGService(openai_client=mock_client)

        with pytest.raises(Exception, match="API error"):
            await service.generate_embedding("test text")


class TestIndexProduct:
    """Tests for index_product method."""

    @pytest.mark.asyncio
    async def test_index_product_success(self) -> None:
        """Test successful product indexing."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        product_id = uuid4()
        product_data = {
            "name": "Test Robot",
            "category": "collaborative_robot",
            "manufacturer": "Test Corp",
        }

        with patch("src.services.rag_service.get_pinecone_index") as mock_get_index:
            mock_index = MagicMock()
            mock_get_index.return_value = mock_index

            service = RAGService(openai_client=mock_client)
            result = await service.index_product(product_id, product_data)

            assert result == f"product_{product_id}"
            mock_index.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_product_embedding_failure(self) -> None:
        """Test product indexing when embedding fails."""
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("Embedding error")

        service = RAGService(openai_client=mock_client)

        with pytest.raises(Exception, match="Embedding error"):
            await service.index_product(uuid4(), {"name": "Test"})


class TestDeleteProductEmbedding:
    """Tests for delete_product_embedding method."""

    @pytest.mark.asyncio
    async def test_delete_product_embedding_success(self) -> None:
        """Test successful embedding deletion."""
        with patch("src.services.rag_service.get_pinecone_index") as mock_get_index:
            mock_index = MagicMock()
            mock_get_index.return_value = mock_index

            service = RAGService()
            await service.delete_product_embedding("product_123")

            mock_index.delete.assert_called_once_with(ids=["product_123"])


class TestSearchProducts:
    """Tests for search_products method."""

    @pytest.mark.asyncio
    async def test_search_products_success(self) -> None:
        """Test successful product search."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        mock_match = MagicMock()
        mock_match.metadata = {"product_id": "123", "name": "Test Robot"}
        mock_match.score = 0.95

        with patch("src.services.rag_service.get_pinecone_index") as mock_get_index:
            mock_index = MagicMock()
            mock_index.query.return_value = MagicMock(matches=[mock_match])
            mock_get_index.return_value = mock_index

            service = RAGService(openai_client=mock_client)
            results = await service.search_products("collaborative robot", top_k=5)

            assert len(results) == 1
            assert results[0]["product_id"] == "123"
            assert results[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_search_products_with_category_filter(self) -> None:
        """Test product search with category filter."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        with patch("src.services.rag_service.get_pinecone_index") as mock_get_index:
            mock_index = MagicMock()
            mock_index.query.return_value = MagicMock(matches=[])
            mock_get_index.return_value = mock_index

            service = RAGService(openai_client=mock_client)
            await service.search_products(
                "robot",
                top_k=5,
                category="collaborative_robot",
            )

            # Verify filter was passed
            call_kwargs = mock_index.query.call_args.kwargs
            assert call_kwargs["filter"] == {"category": {"$eq": "collaborative_robot"}}


class TestGetRelevantProductsForContext:
    """Tests for get_relevant_products_for_context method."""

    @pytest.mark.asyncio
    async def test_get_relevant_products_for_context_success(self) -> None:
        """Test getting relevant products for agent context."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        mock_match = MagicMock()
        mock_match.metadata = {
            "product_id": "123",
            "name": "UR10e",
            "category": "collaborative_robot",
            "manufacturer": "Universal Robots",
        }
        mock_match.score = 0.9

        with patch("src.services.rag_service.get_pinecone_index") as mock_get_index:
            mock_index = MagicMock()
            mock_index.query.return_value = MagicMock(matches=[mock_match])
            mock_get_index.return_value = mock_index

            service = RAGService(openai_client=mock_client)
            result = await service.get_relevant_products_for_context("cobot for palletizing")

            assert "Relevant products from our catalog:" in result
            assert "UR10e" in result
            assert "Universal Robots" in result
            assert "Collaborative Robot" in result

    @pytest.mark.asyncio
    async def test_get_relevant_products_for_context_empty(self) -> None:
        """Test getting relevant products when none found."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        with patch("src.services.rag_service.get_pinecone_index") as mock_get_index:
            mock_index = MagicMock()
            mock_index.query.return_value = MagicMock(matches=[])
            mock_get_index.return_value = mock_index

            service = RAGService(openai_client=mock_client)
            result = await service.get_relevant_products_for_context("something unusual")

            assert result == ""

    @pytest.mark.asyncio
    async def test_get_relevant_products_for_context_error_handling(self) -> None:
        """Test error handling in get_relevant_products_for_context."""
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("API error")

        service = RAGService(openai_client=mock_client)
        result = await service.get_relevant_products_for_context("test query")

        # Should return empty string on error, not raise
        assert result == ""

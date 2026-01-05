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
        robot_data = {
            "name": "Pudu CC1 Pro",
            "category": "Premium Combo",
            "best_for": "Indoor courts, wet cleaning",
        }

        result = service.build_embedding_text(robot_data)

        assert "Robot: Pudu CC1 Pro" in result
        assert "Category: Premium Combo" in result
        assert "Best for: Indoor courts, wet cleaning" in result

    def test_build_embedding_text_with_modes_and_surfaces(self) -> None:
        """Test building embedding text with modes and surfaces."""
        service = RAGService()
        robot_data = {
            "name": "Test Robot",
            "modes": ["Vacuum", "Wet Scrub", "Dry Sweep"],
            "surfaces": ["CushionX", "Asphalt", "Acrylic"],
        }

        result = service.build_embedding_text(robot_data)

        assert "Robot: Test Robot" in result
        assert "Cleaning modes: Vacuum, Wet Scrub, Dry Sweep" in result
        assert "Surfaces: CushionX, Asphalt, Acrylic" in result

    def test_build_embedding_text_with_pricing(self) -> None:
        """Test building embedding text with pricing information."""
        service = RAGService()
        robot_data = {
            "name": "Test Robot",
            "monthly_lease": 1200.00,
            "purchase_price": 28000.00,
        }

        result = service.build_embedding_text(robot_data)

        assert "Robot: Test Robot" in result
        assert "Monthly lease: $1,200" in result
        assert "Purchase price: $28,000" in result

    def test_build_embedding_text_empty_data(self) -> None:
        """Test building embedding text with empty data."""
        service = RAGService()
        robot_data = {}

        result = service.build_embedding_text(robot_data)

        assert result == ""

    def test_build_embedding_text_with_key_reasons_and_specs(self) -> None:
        """Test building embedding text with key reasons and specs."""
        service = RAGService()
        robot_data = {
            "name": "Test Robot",
            "key_reasons": ["High throughput", "Low maintenance"],
            "specs": ["4-in-1 Cleaning", "12h Runtime"],
        }

        result = service.build_embedding_text(robot_data)

        assert "Key benefits: High throughput, Low maintenance" in result
        assert "Specifications: 4-in-1 Cleaning, 12h Runtime" in result

    def test_build_embedding_text_with_time_efficiency(self) -> None:
        """Test building embedding text with time efficiency."""
        service = RAGService()
        robot_data = {
            "name": "Test Robot",
            "time_efficiency": 0.85,
        }

        result = service.build_embedding_text(robot_data)

        assert "Time efficiency: 85%" in result


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


class TestIndexRobot:
    """Tests for index_robot method."""

    @pytest.mark.asyncio
    async def test_index_robot_success(self) -> None:
        """Test successful robot indexing."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        robot_id = uuid4()
        robot_data = {
            "name": "Test Robot",
            "category": "Premium Combo",
            "best_for": "Indoor courts",
        }

        with patch("src.services.rag_service.get_pinecone_index") as mock_get_index:
            mock_index = MagicMock()
            mock_get_index.return_value = mock_index

            service = RAGService(openai_client=mock_client)
            result = await service.index_robot(robot_id, robot_data)

            assert result == f"robot_{robot_id}"
            mock_index.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_robot_embedding_failure(self) -> None:
        """Test robot indexing when embedding fails."""
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("Embedding error")

        service = RAGService(openai_client=mock_client)

        with pytest.raises(Exception, match="Embedding error"):
            await service.index_robot(uuid4(), {"name": "Test"})


class TestDeleteRobotEmbedding:
    """Tests for delete_robot_embedding method."""

    @pytest.mark.asyncio
    async def test_delete_robot_embedding_success(self) -> None:
        """Test successful embedding deletion."""
        with patch("src.services.rag_service.get_pinecone_index") as mock_get_index:
            mock_index = MagicMock()
            mock_get_index.return_value = mock_index

            service = RAGService()
            await service.delete_robot_embedding("robot_123")

            mock_index.delete.assert_called_once_with(ids=["robot_123"])


class TestSearchRobots:
    """Tests for search_robots method."""

    @pytest.mark.asyncio
    async def test_search_robots_success(self) -> None:
        """Test successful robot search."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        mock_match = MagicMock()
        mock_match.metadata = {"robot_id": "123", "name": "Test Robot"}
        mock_match.score = 0.95

        with patch("src.services.rag_service.get_pinecone_index") as mock_get_index:
            mock_index = MagicMock()
            mock_index.query.return_value = MagicMock(matches=[mock_match])
            mock_get_index.return_value = mock_index

            service = RAGService(openai_client=mock_client)
            results = await service.search_robots("cleaning robot", top_k=5)

            assert len(results) == 1
            assert results[0]["robot_id"] == "123"
            assert results[0]["score"] == 0.95

    @pytest.mark.asyncio
    async def test_search_robots_with_category_filter(self) -> None:
        """Test robot search with category filter."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        with patch("src.services.rag_service.get_pinecone_index") as mock_get_index:
            mock_index = MagicMock()
            mock_index.query.return_value = MagicMock(matches=[])
            mock_get_index.return_value = mock_index

            service = RAGService(openai_client=mock_client)
            await service.search_robots(
                "robot",
                top_k=5,
                category="Premium Combo",
            )

            # Verify filter was passed
            call_kwargs = mock_index.query.call_args.kwargs
            assert call_kwargs["filter"] == {"category": {"$eq": "Premium Combo"}}


class TestGetRelevantRobotsForContext:
    """Tests for get_relevant_robots_for_context method."""

    @pytest.mark.asyncio
    async def test_get_relevant_robots_for_context_success(self) -> None:
        """Test getting relevant robots for agent context."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        mock_match = MagicMock()
        mock_match.metadata = {
            "robot_id": "123",
            "name": "Pudu CC1 Pro",
            "category": "Premium Combo",
            "best_for": "Indoor courts",
        }
        mock_match.score = 0.9

        with patch("src.services.rag_service.get_pinecone_index") as mock_get_index:
            mock_index = MagicMock()
            mock_index.query.return_value = MagicMock(matches=[mock_match])
            mock_get_index.return_value = mock_index

            service = RAGService(openai_client=mock_client)
            result = await service.get_relevant_robots_for_context("robot for indoor cleaning")

            assert "Relevant cleaning robots from our catalog:" in result
            assert "Pudu CC1 Pro" in result
            assert "Premium Combo" in result
            assert "Indoor courts" in result

    @pytest.mark.asyncio
    async def test_get_relevant_robots_for_context_empty(self) -> None:
        """Test getting relevant robots when none found."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response

        with patch("src.services.rag_service.get_pinecone_index") as mock_get_index:
            mock_index = MagicMock()
            mock_index.query.return_value = MagicMock(matches=[])
            mock_get_index.return_value = mock_index

            service = RAGService(openai_client=mock_client)
            result = await service.get_relevant_robots_for_context("something unusual")

            assert result == ""

    @pytest.mark.asyncio
    async def test_get_relevant_robots_for_context_error_handling(self) -> None:
        """Test error handling in get_relevant_robots_for_context."""
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("API error")

        service = RAGService(openai_client=mock_client)
        result = await service.get_relevant_robots_for_context("test query")

        # Should return empty string on error, not raise
        assert result == ""

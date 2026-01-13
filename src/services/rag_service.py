"""RAG service for embedding generation and semantic search operations."""

import logging
from typing import Any
from uuid import UUID

from openai import OpenAI

from src.core.config import get_settings
from src.core.openai import get_openai_client
from src.core.pinecone import get_pinecone_index

logger = logging.getLogger(__name__)


class RAGService:
    """Service for RAG operations including embeddings and semantic search."""

    def __init__(self, openai_client: OpenAI | None = None):
        """Initialize RAG service.

        Args:
            openai_client: Optional OpenAI client for testing.
        """
        self._openai_client = openai_client
        self._settings = get_settings()

    @property
    def openai_client(self) -> OpenAI:
        """Get OpenAI client."""
        if self._openai_client is None:
            self._openai_client = get_openai_client()
        return self._openai_client

    def build_embedding_text(self, robot_data: dict[str, Any]) -> str:
        """Build text representation of robot for embedding.

        Combines robot fields into a single text string optimized
        for semantic search.

        Args:
            robot_data: Robot catalog data dictionary.

        Returns:
            str: Combined text for embedding generation.
        """
        parts = []

        # Add name with manufacturer (most important)
        name = robot_data.get("name", "")
        manufacturer = robot_data.get("manufacturer", "")
        if manufacturer and name:
            parts.append(f"Robot: {manufacturer} {name}")
        elif name:
            parts.append(f"Robot: {name}")

        # Add category
        if category := robot_data.get("category"):
            parts.append(f"Category: {category}")

        # Add best_for description
        if best_for := robot_data.get("best_for"):
            parts.append(f"Best for: {best_for}")

        # Add cleaning modes
        if modes := robot_data.get("modes"):
            if isinstance(modes, list) and modes:
                parts.append(f"Cleaning modes: {', '.join(modes)}")

        # Add supported surfaces
        if surfaces := robot_data.get("surfaces"):
            if isinstance(surfaces, list) and surfaces:
                parts.append(f"Surfaces: {', '.join(surfaces)}")

        # Add key reasons/benefits
        if key_reasons := robot_data.get("key_reasons"):
            if isinstance(key_reasons, list) and key_reasons:
                parts.append(f"Key benefits: {', '.join(key_reasons)}")

        # Add specs
        if specs := robot_data.get("specs"):
            if isinstance(specs, list) and specs:
                parts.append(f"Specifications: {', '.join(specs)}")

        # Add pricing information
        if monthly_lease := robot_data.get("monthly_lease"):
            parts.append(f"Monthly lease: ${float(monthly_lease):,.0f}")
        if purchase_price := robot_data.get("purchase_price"):
            parts.append(f"Purchase price: ${float(purchase_price):,.0f}")

        # Add time efficiency
        if time_efficiency := robot_data.get("time_efficiency"):
            parts.append(f"Time efficiency: {float(time_efficiency) * 100:.0f}%")

        return "\n".join(parts)

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text using OpenAI.

        Args:
            text: Text to generate embedding for.

        Returns:
            list[float]: Embedding vector.

        Raises:
            Exception: If embedding generation fails.
        """
        try:
            response = self.openai_client.embeddings.create(
                model=self._settings.embedding_model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    async def index_robot(
        self,
        robot_id: UUID,
        robot_data: dict[str, Any],
    ) -> str:
        """Index a robot in Pinecone.

        Generates embedding and upserts to Pinecone index.

        Args:
            robot_id: Robot UUID.
            robot_data: Robot data for embedding.

        Returns:
            str: Embedding ID in Pinecone.

        Raises:
            Exception: If indexing fails.
        """
        try:
            # Build text for embedding
            embedding_text = self.build_embedding_text(robot_data)

            # Generate embedding
            embedding = await self.generate_embedding(embedding_text)

            # Create embedding ID
            embedding_id = f"robot_{robot_id}"

            # Build metadata for filtering
            metadata: dict[str, Any] = {
                "robot_id": str(robot_id),
                "name": robot_data.get("name", ""),
                "category": robot_data.get("category", ""),
            }

            if best_for := robot_data.get("best_for"):
                metadata["best_for"] = best_for

            if modes := robot_data.get("modes"):
                metadata["modes"] = modes

            # Upsert to Pinecone
            index = get_pinecone_index()
            index.upsert(
                vectors=[
                    {
                        "id": embedding_id,
                        "values": embedding,
                        "metadata": metadata,
                    }
                ]
            )

            logger.info(f"Indexed robot {robot_id} with embedding ID {embedding_id}")
            return embedding_id

        except Exception as e:
            logger.error(f"Failed to index robot {robot_id}: {e}")
            raise

    async def delete_robot_embedding(self, embedding_id: str) -> None:
        """Delete a robot embedding from Pinecone.

        Args:
            embedding_id: Embedding ID to delete.
        """
        try:
            index = get_pinecone_index()
            index.delete(ids=[embedding_id])
            logger.info(f"Deleted embedding {embedding_id}")
        except Exception as e:
            logger.error(f"Failed to delete embedding {embedding_id}: {e}")
            raise

    async def search_robots(
        self,
        query: str,
        top_k: int = 10,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for robots using semantic similarity.

        Args:
            query: Search query text.
            top_k: Number of results to return.
            category: Optional category filter.

        Returns:
            list[dict]: Search results with robot_id and score.
        """
        try:
            # Generate query embedding
            query_embedding = await self.generate_embedding(query)

            # Build filter if category specified
            filter_dict: dict[str, Any] | None = None
            if category:
                filter_dict = {"category": {"$eq": category}}

            # Query Pinecone
            index = get_pinecone_index()
            results = index.query(
                vector=query_embedding,
                top_k=top_k,
                filter=filter_dict,
                include_metadata=True,
            )

            # Format results
            search_results = []
            for match in results.matches:
                search_results.append(
                    {
                        "robot_id": match.metadata.get("robot_id") if match.metadata else None,
                        "score": match.score,
                        "metadata": match.metadata,
                    }
                )

            logger.info(f"Search for '{query}' returned {len(search_results)} results")
            return search_results

        except Exception as e:
            logger.error(f"Failed to search robots: {e}")
            raise

    async def search_robots_for_discovery(
        self,
        discovery_context: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for robots using natural language discovery context.

        This method is optimized for recommendation scoring by returning
        robots that semantically match the customer's needs description.

        Args:
            discovery_context: Natural language summary of customer needs.
            top_k: Maximum candidates to return.

        Returns:
            List of dicts with robot_id, semantic_score, and metadata.
        """
        try:
            # Generate embedding from discovery context
            query_embedding = await self.generate_embedding(discovery_context)

            # Query Pinecone
            index = get_pinecone_index()
            results = index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
            )

            # Format results with semantic scores
            search_results = []
            for match in results.matches:
                search_results.append({
                    "robot_id": match.metadata.get("robot_id") if match.metadata else None,
                    "semantic_score": match.score,
                    "metadata": match.metadata,
                })

            logger.info(
                "Discovery search returned %d candidates (top score: %.3f)",
                len(search_results),
                search_results[0]["semantic_score"] if search_results else 0,
            )
            return search_results

        except Exception as e:
            logger.error("Failed to search robots for discovery: %s", str(e))
            return []

    async def get_relevant_robots_for_context(
        self,
        query: str,
        top_k: int = 5,
    ) -> str:
        """Get relevant robot information for agent context.

        Searches for robots and formats them as context text
        for the agent to use in responses.

        Args:
            query: User query or message.
            top_k: Number of robots to include.

        Returns:
            str: Formatted robot context for agent.
        """
        try:
            results = await self.search_robots(query=query, top_k=top_k)

            if not results:
                return ""

            context_parts = ["Relevant cleaning robots from our catalog:"]

            for i, result in enumerate(results, 1):
                metadata = result.get("metadata", {})
                name = metadata.get("name", "Unknown")
                category = metadata.get("category", "")
                best_for = metadata.get("best_for", "")
                score = result.get("score", 0)

                robot_info = f"{i}. {name}"
                if category:
                    robot_info += f" ({category})"
                if best_for:
                    robot_info += f" - {best_for}"
                robot_info += f" - Relevance: {score:.2f}"

                context_parts.append(robot_info)

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Failed to get relevant robots for context: {e}")
            return ""


def get_rag_service() -> RAGService:
    """Get RAG service instance.

    Returns:
        RAGService: RAG service instance.
    """
    return RAGService()

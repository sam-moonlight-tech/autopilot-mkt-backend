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

    def build_embedding_text(self, product_data: dict[str, Any]) -> str:
        """Build text representation of product for embedding.

        Combines product fields into a single text string optimized
        for semantic search.

        Args:
            product_data: Product data dictionary.

        Returns:
            str: Combined text for embedding generation.
        """
        parts = []

        # Add name (most important)
        if name := product_data.get("name"):
            parts.append(f"Product: {name}")

        # Add manufacturer
        if manufacturer := product_data.get("manufacturer"):
            parts.append(f"Manufacturer: {manufacturer}")

        # Add category
        if category := product_data.get("category"):
            # Convert snake_case to readable format
            readable_category = category.replace("_", " ").title()
            parts.append(f"Category: {readable_category}")

        # Add description
        if description := product_data.get("description"):
            parts.append(f"Description: {description}")

        # Add model number
        if model_number := product_data.get("model_number"):
            parts.append(f"Model: {model_number}")

        # Add specs as key-value pairs
        if specs := product_data.get("specs"):
            if isinstance(specs, dict) and specs:
                spec_parts = []
                for key, value in specs.items():
                    readable_key = key.replace("_", " ").title()
                    spec_parts.append(f"{readable_key}: {value}")
                parts.append(f"Specifications: {', '.join(spec_parts)}")

        # Add pricing information
        if pricing := product_data.get("pricing"):
            if isinstance(pricing, dict) and pricing:
                price_parts = []
                for key, value in pricing.items():
                    readable_key = key.replace("_", " ").title()
                    if isinstance(value, (int, float)):
                        price_parts.append(f"{readable_key}: ${value:,.0f}")
                    else:
                        price_parts.append(f"{readable_key}: {value}")
                parts.append(f"Pricing: {', '.join(price_parts)}")

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

    async def index_product(
        self,
        product_id: UUID,
        product_data: dict[str, Any],
    ) -> str:
        """Index a product in Pinecone.

        Generates embedding and upserts to Pinecone index.

        Args:
            product_id: Product UUID.
            product_data: Product data for embedding.

        Returns:
            str: Embedding ID in Pinecone.

        Raises:
            Exception: If indexing fails.
        """
        try:
            # Build text for embedding
            embedding_text = self.build_embedding_text(product_data)

            # Generate embedding
            embedding = await self.generate_embedding(embedding_text)

            # Create embedding ID
            embedding_id = f"product_{product_id}"

            # Build metadata for filtering
            metadata: dict[str, Any] = {
                "product_id": str(product_id),
                "name": product_data.get("name", ""),
                "category": product_data.get("category", ""),
            }

            if manufacturer := product_data.get("manufacturer"):
                metadata["manufacturer"] = manufacturer

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

            logger.info(f"Indexed product {product_id} with embedding ID {embedding_id}")
            return embedding_id

        except Exception as e:
            logger.error(f"Failed to index product {product_id}: {e}")
            raise

    async def delete_product_embedding(self, embedding_id: str) -> None:
        """Delete a product embedding from Pinecone.

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

    async def search_products(
        self,
        query: str,
        top_k: int = 10,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for products using semantic similarity.

        Args:
            query: Search query text.
            top_k: Number of results to return.
            category: Optional category filter.

        Returns:
            list[dict]: Search results with product_id and score.
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
                        "product_id": match.metadata.get("product_id") if match.metadata else None,
                        "score": match.score,
                        "metadata": match.metadata,
                    }
                )

            logger.info(f"Search for '{query}' returned {len(search_results)} results")
            return search_results

        except Exception as e:
            logger.error(f"Failed to search products: {e}")
            raise

    async def get_relevant_products_for_context(
        self,
        query: str,
        top_k: int = 5,
    ) -> str:
        """Get relevant product information for agent context.

        Searches for products and formats them as context text
        for the agent to use in responses.

        Args:
            query: User query or message.
            top_k: Number of products to include.

        Returns:
            str: Formatted product context for agent.
        """
        try:
            results = await self.search_products(query=query, top_k=top_k)

            if not results:
                return ""

            context_parts = ["Relevant products from our catalog:"]

            for i, result in enumerate(results, 1):
                metadata = result.get("metadata", {})
                name = metadata.get("name", "Unknown")
                category = metadata.get("category", "").replace("_", " ").title()
                manufacturer = metadata.get("manufacturer", "")
                score = result.get("score", 0)

                product_info = f"{i}. {name}"
                if manufacturer:
                    product_info += f" by {manufacturer}"
                if category:
                    product_info += f" ({category})"
                product_info += f" - Relevance: {score:.2f}"

                context_parts.append(product_info)

            return "\n".join(context_parts)

        except Exception as e:
            logger.error(f"Failed to get relevant products for context: {e}")
            return ""


def get_rag_service() -> RAGService:
    """Get RAG service instance.

    Returns:
        RAGService: RAG service instance.
    """
    return RAGService()

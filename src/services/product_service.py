"""Product service for product CRUD and search operations."""

import logging
from typing import Any
from uuid import UUID

from supabase import Client

from src.core.supabase import get_supabase_client
from src.models.product import Product, ProductCreate, ProductUpdate
from src.services.rag_service import RAGService, get_rag_service

logger = logging.getLogger(__name__)


class ProductService:
    """Service for product operations."""

    def __init__(
        self,
        supabase_client: Client | None = None,
        rag_service: RAGService | None = None,
    ):
        """Initialize product service.

        Args:
            supabase_client: Optional Supabase client for testing.
            rag_service: Optional RAG service for testing.
        """
        self._supabase_client = supabase_client
        self._rag_service = rag_service

    @property
    def supabase(self) -> Client:
        """Get Supabase client."""
        if self._supabase_client is None:
            self._supabase_client = get_supabase_client()
        return self._supabase_client

    @property
    def rag_service(self) -> RAGService:
        """Get RAG service."""
        if self._rag_service is None:
            self._rag_service = get_rag_service()
        return self._rag_service

    async def create_product(
        self,
        data: ProductCreate,
        index_embedding: bool = True,
    ) -> Product:
        """Create a new product.

        Args:
            data: Product creation data.
            index_embedding: Whether to index product in Pinecone.

        Returns:
            Product: Created product.

        Raises:
            Exception: If creation fails.
        """
        try:
            # Insert product into database
            result = (
                self.supabase.table("products")
                .insert(dict(data))
                .execute()
            )

            if not result.data:
                raise Exception("Failed to create product")

            product = result.data[0]

            # Index product embedding if requested
            if index_embedding:
                try:
                    embedding_id = await self.rag_service.index_product(
                        product_id=product["id"],
                        product_data=product,
                    )

                    # Update product with embedding_id
                    update_result = (
                        self.supabase.table("products")
                        .update({"embedding_id": embedding_id})
                        .eq("id", product["id"])
                        .execute()
                    )

                    if update_result.data:
                        product = update_result.data[0]

                except Exception as e:
                    logger.warning(f"Failed to index product embedding: {e}")
                    # Product is still created, just without embedding

            logger.info(f"Created product {product['id']}")
            return product

        except Exception as e:
            logger.error(f"Failed to create product: {e}")
            raise

    async def get_product(self, product_id: UUID) -> Product | None:
        """Get a product by ID.

        Args:
            product_id: Product UUID.

        Returns:
            Product or None if not found.
        """
        try:
            result = (
                self.supabase.table("products")
                .select("*")
                .eq("id", str(product_id))
                .execute()
            )

            if result.data:
                return result.data[0]
            return None

        except Exception as e:
            logger.error(f"Failed to get product {product_id}: {e}")
            raise

    async def update_product(
        self,
        product_id: UUID,
        data: ProductUpdate,
        reindex_embedding: bool = True,
    ) -> Product | None:
        """Update a product.

        Args:
            product_id: Product UUID.
            data: Update data.
            reindex_embedding: Whether to reindex product in Pinecone.

        Returns:
            Product or None if not found.
        """
        try:
            # Filter out None values
            update_data = {k: v for k, v in data.items() if v is not None}

            if not update_data:
                return await self.get_product(product_id)

            result = (
                self.supabase.table("products")
                .update(update_data)
                .eq("id", str(product_id))
                .execute()
            )

            if not result.data:
                return None

            product = result.data[0]

            # Reindex if requested and product has embedding
            if reindex_embedding:
                try:
                    # Delete old embedding if exists
                    if product.get("embedding_id"):
                        await self.rag_service.delete_product_embedding(
                            product["embedding_id"]
                        )

                    # Create new embedding
                    embedding_id = await self.rag_service.index_product(
                        product_id=product_id,
                        product_data=product,
                    )

                    # Update product with new embedding_id
                    update_result = (
                        self.supabase.table("products")
                        .update({"embedding_id": embedding_id})
                        .eq("id", str(product_id))
                        .execute()
                    )

                    if update_result.data:
                        product = update_result.data[0]

                except Exception as e:
                    logger.warning(f"Failed to reindex product embedding: {e}")

            logger.info(f"Updated product {product_id}")
            return product

        except Exception as e:
            logger.error(f"Failed to update product {product_id}: {e}")
            raise

    async def delete_product(self, product_id: UUID) -> bool:
        """Delete a product.

        Args:
            product_id: Product UUID.

        Returns:
            bool: True if deleted, False if not found.
        """
        try:
            # Get product first to get embedding_id
            product = await self.get_product(product_id)
            if not product:
                return False

            # Delete from database
            result = (
                self.supabase.table("products")
                .delete()
                .eq("id", str(product_id))
                .execute()
            )

            if not result.data:
                return False

            # Delete embedding if exists
            if embedding_id := product.get("embedding_id"):
                try:
                    await self.rag_service.delete_product_embedding(embedding_id)
                except Exception as e:
                    logger.warning(f"Failed to delete product embedding: {e}")

            logger.info(f"Deleted product {product_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete product {product_id}: {e}")
            raise

    async def list_products(
        self,
        category: str | None = None,
        manufacturer: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List products with optional filtering and pagination.

        Args:
            category: Filter by category.
            manufacturer: Filter by manufacturer.
            cursor: Pagination cursor (product ID).
            limit: Number of results per page.

        Returns:
            dict: Products list with pagination info.
        """
        try:
            query = (
                self.supabase.table("products")
                .select("*")
                .order("created_at", desc=True)
                .limit(limit + 1)  # Get one extra to check for more
            )

            if category:
                query = query.eq("category", category)

            if manufacturer:
                query = query.eq("manufacturer", manufacturer)

            if cursor:
                # Get the cursor product's created_at for pagination
                cursor_result = (
                    self.supabase.table("products")
                    .select("created_at")
                    .eq("id", cursor)
                    .execute()
                )

                if cursor_result.data:
                    cursor_created_at = cursor_result.data[0]["created_at"]
                    query = query.lt("created_at", cursor_created_at)

            result = query.execute()
            products = result.data or []

            # Check if there are more results
            has_more = len(products) > limit
            if has_more:
                products = products[:limit]

            # Get next cursor
            next_cursor = None
            if has_more and products:
                next_cursor = products[-1]["id"]

            return {
                "products": products,
                "next_cursor": next_cursor,
                "has_more": has_more,
            }

        except Exception as e:
            logger.error(f"Failed to list products: {e}")
            raise

    async def search_products(
        self,
        query: str,
        category: str | None = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search products using semantic similarity.

        Args:
            query: Search query text.
            category: Optional category filter.
            top_k: Number of results to return.

        Returns:
            list[dict]: Search results with product and score.
        """
        try:
            # Get semantic search results from RAG service
            search_results = await self.rag_service.search_products(
                query=query,
                category=category,
                top_k=top_k,
            )

            # Fetch full product data for results
            results = []
            for result in search_results:
                product_id = result.get("product_id")
                if product_id:
                    product = await self.get_product(UUID(product_id))
                    if product:
                        results.append({
                            "product": product,
                            "score": result.get("score", 0),
                        })

            return results

        except Exception as e:
            logger.error(f"Failed to search products: {e}")
            raise

    async def index_all_products(self) -> dict[str, Any]:
        """Index all products in Pinecone.

        Used for bulk indexing or reindexing all products.

        Returns:
            dict: Indexing results with counts.
        """
        try:
            # Get all products
            result = (
                self.supabase.table("products")
                .select("*")
                .execute()
            )

            products = result.data or []
            indexed = 0
            failed = 0

            for product in products:
                try:
                    embedding_id = await self.rag_service.index_product(
                        product_id=product["id"],
                        product_data=product,
                    )

                    # Update product with embedding_id
                    self.supabase.table("products").update(
                        {"embedding_id": embedding_id}
                    ).eq("id", product["id"]).execute()

                    indexed += 1

                except Exception as e:
                    logger.error(f"Failed to index product {product['id']}: {e}")
                    failed += 1

            logger.info(f"Indexed {indexed} products, {failed} failed")
            return {
                "total": len(products),
                "indexed": indexed,
                "failed": failed,
            }

        except Exception as e:
            logger.error(f"Failed to index all products: {e}")
            raise

    async def get_products_by_ids(self, product_ids: list[UUID]) -> list[Product]:
        """Get multiple products by their IDs.

        Args:
            product_ids: List of product UUIDs.

        Returns:
            list[Product]: List of products found.
        """
        if not product_ids:
            return []

        try:
            result = (
                self.supabase.table("products")
                .select("*")
                .in_("id", [str(pid) for pid in product_ids])
                .execute()
            )

            return result.data or []

        except Exception as e:
            logger.error(f"Failed to get products by IDs: {e}")
            raise


def get_product_service() -> ProductService:
    """Get product service instance.

    Returns:
        ProductService: Product service instance.
    """
    return ProductService()

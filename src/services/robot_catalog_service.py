"""Robot catalog business logic service."""

import logging
from typing import Any
from uuid import UUID

from src.core.supabase import get_supabase_client
from src.services.rag_service import RAGService, get_rag_service

logger = logging.getLogger(__name__)


class RobotCatalogService:
    """Service for managing robot product catalog."""

    def __init__(self, rag_service: RAGService | None = None) -> None:
        """Initialize robot catalog service.

        Args:
            rag_service: Optional RAG service for testing.
        """
        self.client = get_supabase_client()
        self._rag_service = rag_service

    @property
    def rag_service(self) -> RAGService:
        """Get RAG service."""
        if self._rag_service is None:
            self._rag_service = get_rag_service()
        return self._rag_service

    async def list_robots(self, active_only: bool = True) -> list[dict[str, Any]]:
        """List all robots in the catalog.

        Args:
            active_only: If True, only return active products.

        Returns:
            list[dict]: List of robot data.
        """
        query = self.client.table("robot_catalog").select("*")

        if active_only:
            query = query.eq("active", True)

        query = query.order("name")
        response = query.execute()

        return response.data or []

    async def get_robot(self, robot_id: UUID) -> dict[str, Any] | None:
        """Get a single robot by ID.

        Args:
            robot_id: The robot's UUID.

        Returns:
            dict | None: The robot data or None if not found.
        """
        response = (
            self.client.table("robot_catalog")
            .select("*")
            .eq("id", str(robot_id))
            .maybe_single()
            .execute()
        )

        return response.data if response and response.data else None

    async def get_robot_with_stripe_ids(
        self, robot_id: UUID
    ) -> dict[str, Any] | None:
        """Get a robot including Stripe product and price IDs.

        Used for checkout session creation.

        Args:
            robot_id: The robot's UUID.

        Returns:
            dict | None: The robot data with Stripe IDs or None if not found.
        """
        response = (
            self.client.table("robot_catalog")
            .select(
                "id, name, monthly_lease, stripe_product_id, stripe_lease_price_id, active"
            )
            .eq("id", str(robot_id))
            .maybe_single()
            .execute()
        )

        return response.data if response and response.data else None

    async def get_robots_by_ids(
        self, robot_ids: list[UUID]
    ) -> list[dict[str, Any]]:
        """Get multiple robots by their IDs.

        Args:
            robot_ids: List of robot UUIDs.

        Returns:
            list[dict]: List of robot data.
        """
        if not robot_ids:
            return []

        id_strings = [str(rid) for rid in robot_ids]
        response = (
            self.client.table("robot_catalog")
            .select("*")
            .in_("id", id_strings)
            .execute()
        )

        return response.data or []

    async def index_robot_embedding(self, robot_id: UUID) -> str | None:
        """Index a robot's embedding in Pinecone.

        Args:
            robot_id: The robot's UUID.

        Returns:
            str | None: The embedding ID or None if failed.
        """
        robot = await self.get_robot(robot_id)
        if not robot:
            logger.warning(f"Robot {robot_id} not found for indexing")
            return None

        try:
            embedding_id = await self.rag_service.index_robot(
                robot_id=robot_id,
                robot_data=robot,
            )

            # Update robot with embedding_id
            self.client.table("robot_catalog").update(
                {"embedding_id": embedding_id}
            ).eq("id", str(robot_id)).execute()

            logger.info(f"Indexed robot {robot_id}")
            return embedding_id

        except Exception as e:
            logger.error(f"Failed to index robot {robot_id}: {e}")
            return None

    async def index_all_robots(self) -> dict[str, Any]:
        """Index all active robots in Pinecone.

        Used for bulk indexing or reindexing all robots.

        Returns:
            dict: Indexing results with counts.
        """
        robots = await self.list_robots(active_only=True)

        indexed = 0
        failed = 0

        for robot in robots:
            try:
                embedding_id = await self.rag_service.index_robot(
                    robot_id=UUID(robot["id"]),
                    robot_data=robot,
                )

                # Update robot with embedding_id
                self.client.table("robot_catalog").update(
                    {"embedding_id": embedding_id}
                ).eq("id", robot["id"]).execute()

                indexed += 1

            except Exception as e:
                logger.error(f"Failed to index robot {robot['id']}: {e}")
                failed += 1

        logger.info(f"Indexed {indexed} robots, {failed} failed")
        return {
            "total": len(robots),
            "indexed": indexed,
            "failed": failed,
        }

    async def search_robots(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Search robots using semantic similarity.

        Args:
            query: Search query text.
            top_k: Number of results to return.

        Returns:
            list[dict]: Search results with robot data and score.
        """
        try:
            search_results = await self.rag_service.search_robots(
                query=query,
                top_k=top_k,
            )

            # Fetch full robot data for results
            results = []
            for result in search_results:
                robot_id = result.get("robot_id")
                if robot_id:
                    robot = await self.get_robot(UUID(robot_id))
                    if robot:
                        results.append({
                            "robot": robot,
                            "score": result.get("score", 0),
                        })

            return results

        except Exception as e:
            logger.error(f"Failed to search robots: {e}")
            return []

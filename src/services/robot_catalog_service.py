"""Robot catalog business logic service."""

import logging
from collections import Counter
from typing import Any
from uuid import UUID

from src.core.supabase import get_supabase_client
from src.schemas.robot import (
    FilterMetadata,
    FilterOption,
    RobotFilters,
    RobotSortField,
)
from src.services.rag_service import RAGService, get_rag_service

logger = logging.getLogger(__name__)

# Size categories based on coverage rate (m²/h)
SIZE_CATEGORIES = {
    "small": (0, 500),       # < 500 m²/h
    "medium": (500, 1000),   # 500-1000 m²/h
    "large": (1000, 2000),   # 1000-2000 m²/h
    "enterprise": (2000, float("inf")),  # 2000+ m²/h
}

# Price ranges for filter
PRICE_RANGES = [
    {"value": "0-500", "label": "$0 - $500", "min": 0, "max": 500},
    {"value": "500-1000", "label": "$500 - $1,000", "min": 500, "max": 1000},
    {"value": "1000-2000", "label": "$1,000 - $2,000", "min": 1000, "max": 2000},
    {"value": "2000-5000", "label": "$2,000 - $5,000", "min": 2000, "max": 5000},
    {"value": "5000+", "label": "$5,000+", "min": 5000, "max": float("inf")},
]


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

    async def list_robots_filtered(
        self,
        filters: RobotFilters,
        active_only: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        """List robots with filtering and sorting.

        Args:
            filters: Filter parameters.
            active_only: If True, only return active products.

        Returns:
            Tuple of (filtered robots list, total count).
        """
        # Start with base query
        query = self.client.table("robot_catalog").select("*")

        if active_only:
            query = query.eq("active", True)

        # Apply price filters
        if filters.price_min is not None:
            query = query.gte("monthly_lease", filters.price_min)
        if filters.price_max is not None:
            query = query.lte("monthly_lease", filters.price_max)

        # Apply category filter
        if filters.category:
            query = query.ilike("category", f"%{filters.category}%")

        # Apply search filter
        if filters.search:
            # Search in name, category, and best_for
            query = query.or_(
                f"name.ilike.%{filters.search}%,"
                f"category.ilike.%{filters.search}%,"
                f"best_for.ilike.%{filters.search}%"
            )

        # Execute query
        response = query.execute()
        robots = response.data or []

        # Apply array-based filters in Python (Supabase array filtering is limited)
        if filters.methods:
            methods_lower = [m.lower() for m in filters.methods]
            robots = [
                r for r in robots
                if any(
                    method.lower() in methods_lower
                    for method in r.get("modes", [])
                )
            ]

        if filters.surfaces:
            surfaces_lower = [s.lower() for s in filters.surfaces]
            robots = [
                r for r in robots
                if any(
                    surface.lower() in surfaces_lower
                    for surface in r.get("surfaces", [])
                )
            ]

        # Apply size filter based on coverage rate from specs
        if filters.size and filters.size in SIZE_CATEGORIES:
            min_coverage, max_coverage = SIZE_CATEGORIES[filters.size]
            robots = [
                r for r in robots
                if self._get_robot_coverage(r) >= min_coverage
                and self._get_robot_coverage(r) < max_coverage
            ]

        # Total count before sorting
        total = len(robots)

        # Apply sorting
        robots = self._sort_robots(robots, filters.sort)

        return robots, total

    def _get_robot_coverage(self, robot: dict[str, Any]) -> float:
        """Extract coverage rate from robot specs.

        Args:
            robot: Robot data.

        Returns:
            Coverage rate in m²/h, or 0 if not found.
        """
        specs = robot.get("specs", [])
        for spec in specs:
            spec_lower = spec.lower()
            if "m²/h" in spec_lower or "m2/h" in spec_lower:
                # Try to extract number from spec like "700-1000 m²/h"
                import re
                numbers = re.findall(r"(\d+)", spec)
                if numbers:
                    # Use the average if range, or single value
                    nums = [int(n) for n in numbers]
                    return sum(nums) / len(nums)
        return 500  # Default to medium if not found

    def _sort_robots(
        self,
        robots: list[dict[str, Any]],
        sort: RobotSortField,
    ) -> list[dict[str, Any]]:
        """Sort robots by the specified field.

        Args:
            robots: List of robots to sort.
            sort: Sort field enum.

        Returns:
            Sorted list of robots.
        """
        if sort == RobotSortField.PRICE_LOW:
            return sorted(robots, key=lambda r: float(r.get("monthly_lease", 0)))
        elif sort == RobotSortField.PRICE_HIGH:
            return sorted(robots, key=lambda r: float(r.get("monthly_lease", 0)), reverse=True)
        elif sort == RobotSortField.NAME_AZ:
            return sorted(robots, key=lambda r: r.get("name", "").lower())
        elif sort == RobotSortField.NAME_ZA:
            return sorted(robots, key=lambda r: r.get("name", "").lower(), reverse=True)
        elif sort == RobotSortField.EFFICIENCY:
            return sorted(robots, key=lambda r: float(r.get("time_efficiency", 0)), reverse=True)
        else:
            # FEATURED - sort by a combination of factors
            # Higher score = better featured
            def featured_score(r: dict[str, Any]) -> float:
                efficiency = float(r.get("time_efficiency", 0.5))
                has_image = 1 if r.get("image_url") else 0
                mode_count = len(r.get("modes", []))
                return efficiency * 10 + has_image * 5 + mode_count
            return sorted(robots, key=featured_score, reverse=True)

    async def get_filter_metadata(self) -> FilterMetadata:
        """Get available filter options based on current catalog.

        Returns:
            FilterMetadata with all available filter options.
        """
        robots = await self.list_robots(active_only=True)

        # Collect all unique methods
        all_methods: Counter[str] = Counter()
        for robot in robots:
            for mode in robot.get("modes", []):
                all_methods[mode] += 1

        # Collect all unique surfaces
        all_surfaces: Counter[str] = Counter()
        for robot in robots:
            for surface in robot.get("surfaces", []):
                all_surfaces[surface] += 1

        # Collect all unique categories
        all_categories: Counter[str] = Counter()
        for robot in robots:
            category = robot.get("category", "")
            if category:
                all_categories[category] += 1

        # Count robots per price range
        price_range_counts: dict[str, int] = {}
        for pr in PRICE_RANGES:
            count = sum(
                1 for r in robots
                if pr["min"] <= float(r.get("monthly_lease", 0)) < pr["max"]
            )
            price_range_counts[pr["value"]] = count

        # Count robots per size category based on coverage_rate
        # Extract coverage_rate from specs if not directly available
        import re
        size_counts: dict[str, int] = {
            "small": 0,
            "medium": 0,
            "large": 0,
            "enterprise": 0,
        }
        for robot in robots:
            coverage_rate = robot.get("coverage_rate", 0)
            
            # If not directly available, try to extract from specs
            if not coverage_rate:
                specs = robot.get("specs", [])
                for spec in specs:
                    # Look for patterns like "700-1000 m²/h" or "~2600 m²/h" or "500 m²/h"
                    match = re.search(r'(?:~|up to )?(\d+)(?:\s*-\s*(\d+))?\s*m²/h', spec.lower())
                    if match:
                        # Use the maximum value if range, otherwise the single value
                        if match.group(2):
                            coverage_rate = float(match.group(2))  # Use max of range
                        else:
                            coverage_rate = float(match.group(1))
                        break
            
            try:
                coverage_rate = float(coverage_rate) if coverage_rate else 0
            except (ValueError, TypeError):
                # Default based on price if we can't extract from specs
                monthly_lease = float(robot.get("monthly_lease", 0))
                if monthly_lease < 1000:
                    coverage_rate = 600  # Small
                elif monthly_lease < 2000:
                    coverage_rate = 1200  # Medium
                elif monthly_lease < 3000:
                    coverage_rate = 1800  # Large
                else:
                    coverage_rate = 2500  # Enterprise
            
            if coverage_rate < 500:
                size_counts["small"] += 1
            elif coverage_rate < 1000:
                size_counts["medium"] += 1
            elif coverage_rate < 2000:
                size_counts["large"] += 1
            else:
                size_counts["enterprise"] += 1

        # Build filter metadata
        return FilterMetadata(
            sort_options=[
                FilterOption(value="featured", label="Featured", count=len(robots)),
                FilterOption(value="price_low", label="Price: Low to High", count=len(robots)),
                FilterOption(value="price_high", label="Price: High to Low", count=len(robots)),
                FilterOption(value="name_az", label="Name: A-Z", count=len(robots)),
                FilterOption(value="name_za", label="Name: Z-A", count=len(robots)),
                FilterOption(value="efficiency", label="Efficiency", count=len(robots)),
            ],
            price_ranges=[
                FilterOption(
                    value=pr["value"],
                    label=pr["label"],
                    count=price_range_counts.get(pr["value"], 0),
                )
                for pr in PRICE_RANGES
            ],
            sizes=[
                FilterOption(value="small", label="Small (< 500 m²/h)", count=size_counts["small"]),
                FilterOption(value="medium", label="Medium (500-1000 m²/h)", count=size_counts["medium"]),
                FilterOption(value="large", label="Large (1000-2000 m²/h)", count=size_counts["large"]),
                FilterOption(value="enterprise", label="Enterprise (2000+ m²/h)", count=size_counts["enterprise"]),
            ],
            methods=[
                FilterOption(value=method, label=method, count=count)
                for method, count in all_methods.most_common()
            ],
            surfaces=[
                FilterOption(value=surface, label=surface, count=count)
                for surface, count in all_surfaces.most_common()
            ],
            categories=[
                FilterOption(value=cat, label=cat, count=count)
                for cat, count in all_categories.most_common()
            ],
            ship_options=[
                FilterOption(value="in_stock", label="In Stock", count=len(robots)),
                FilterOption(value="ships_soon", label="Ships Soon", count=0),
                FilterOption(value="pre_order", label="Pre-Order", count=0),
            ],
        )

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

        Used for checkout session creation. Returns environment-appropriate
        Stripe IDs based on whether test or live keys are configured.

        Args:
            robot_id: The robot's UUID.

        Returns:
            dict | None: The robot data with Stripe IDs or None if not found.
        """
        from src.core.config import get_settings

        response = (
            self.client.table("robot_catalog")
            .select(
                "id, name, monthly_lease, stripe_product_id, stripe_lease_price_id, "
                "stripe_product_id_test, stripe_lease_price_id_test, active"
            )
            .eq("id", str(robot_id))
            .maybe_single()
            .execute()
        )

        if not response.data:
            return None

        robot = response.data
        settings = get_settings()

        # Return environment-appropriate Stripe IDs
        if settings.is_stripe_test_mode:
            robot["stripe_product_id"] = robot.get("stripe_product_id_test") or robot.get("stripe_product_id")
            robot["stripe_lease_price_id"] = robot.get("stripe_lease_price_id_test") or robot.get("stripe_lease_price_id")

        return robot

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

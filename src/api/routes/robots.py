"""Robot catalog API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.schemas.robot import (
    FilterMetadata,
    RobotFilters,
    RobotListResponse,
    RobotResponse,
    RobotSortField,
)
from src.services.robot_catalog_service import RobotCatalogService

router = APIRouter(prefix="/robots", tags=["robots"])


@router.get(
    "",
    response_model=RobotListResponse,
    summary="List all robots with optional filters",
    description="Returns robots with optional filtering, sorting, and search. No authentication required.",
)
async def list_robots(
    # Sorting
    sort: Annotated[
        RobotSortField,
        Query(description="Sort order for results"),
    ] = RobotSortField.FEATURED,
    # Price filters
    price_min: Annotated[
        float | None,
        Query(ge=0, description="Minimum monthly lease price"),
    ] = None,
    price_max: Annotated[
        float | None,
        Query(ge=0, description="Maximum monthly lease price"),
    ] = None,
    # Size filter
    size: Annotated[
        str | None,
        Query(description="Size category: small, medium, large, enterprise"),
    ] = None,
    # Methods filter (can be multiple)
    methods: Annotated[
        list[str] | None,
        Query(description="Filter by cleaning modes (e.g., vacuum, mop, scrub)"),
    ] = None,
    # Surfaces filter (can be multiple)
    surfaces: Annotated[
        list[str] | None,
        Query(description="Filter by supported surfaces"),
    ] = None,
    # Category filter
    category: Annotated[
        str | None,
        Query(description="Filter by robot category"),
    ] = None,
    # Shipping filter
    ship: Annotated[
        str | None,
        Query(description="Shipping option: in_stock, ships_soon, pre_order"),
    ] = None,
    # Search
    search: Annotated[
        str | None,
        Query(description="Text search in name, category, best_for"),
    ] = None,
) -> RobotListResponse:
    """List all active robots with optional filtering.

    Args:
        sort: Sort order for results.
        price_min: Minimum monthly lease price.
        price_max: Maximum monthly lease price.
        size: Size category filter.
        methods: Cleaning methods filter (multiple allowed).
        surfaces: Surfaces filter (multiple allowed).
        category: Category filter.
        ship: Shipping/availability filter.
        search: Text search query.

    Returns:
        RobotListResponse: Filtered and sorted list of robots.
    """
    service = RobotCatalogService()

    # Build filters object
    filters = RobotFilters(
        sort=sort,
        price_min=price_min,
        price_max=price_max,
        size=size,
        methods=methods,
        surfaces=surfaces,
        category=category,
        ship=ship,
        search=search,
    )

    # Get filtered robots
    robots, total = await service.list_robots_filtered(filters, active_only=True)

    return RobotListResponse(
        items=[RobotResponse(**robot) for robot in robots],
        total=total,
        filters_applied=filters,
    )


@router.get(
    "/filters",
    response_model=FilterMetadata,
    summary="Get available filter options",
    description="Returns available filter options based on current robot catalog. Use for populating filter dropdowns.",
)
async def get_filter_options() -> FilterMetadata:
    """Get available filter options for the robot catalog.

    Returns all available options for each filter type based on
    the current robots in the catalog, with counts for each option.

    Returns:
        FilterMetadata: Available filter options.
    """
    service = RobotCatalogService()
    return await service.get_filter_metadata()


@router.get(
    "/{robot_id}",
    response_model=RobotResponse,
    summary="Get a robot by ID",
    description="Returns a single robot by its UUID. No authentication required.",
)
async def get_robot(robot_id: UUID) -> RobotResponse:
    """Get a single robot by ID.

    Args:
        robot_id: The robot's UUID.

    Returns:
        RobotResponse: The robot data.

    Raises:
        HTTPException: 404 if robot not found.
    """
    service = RobotCatalogService()
    robot = await service.get_robot(robot_id)

    if not robot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Robot not found",
        )

    return RobotResponse(**robot)

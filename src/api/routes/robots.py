"""Robot catalog API routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.schemas.robot import RobotListResponse, RobotResponse
from src.services.robot_catalog_service import RobotCatalogService

router = APIRouter(prefix="/robots", tags=["robots"])


@router.get(
    "",
    response_model=RobotListResponse,
    summary="List all robots",
    description="Returns all active robots in the catalog. No authentication required.",
)
async def list_robots() -> RobotListResponse:
    """List all active robots in the catalog.

    Returns:
        RobotListResponse: List of active robots.
    """
    service = RobotCatalogService()
    robots = await service.list_robots(active_only=True)

    return RobotListResponse(items=[RobotResponse(**robot) for robot in robots])


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

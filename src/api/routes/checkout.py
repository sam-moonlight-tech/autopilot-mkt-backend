"""Checkout API routes for Stripe integration."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.api.deps import AuthContext, DualAuth
from src.schemas.checkout import (
    CheckoutSessionCreate,
    CheckoutSessionResponse,
    OrderListResponse,
    OrderResponse,
)
from src.services.checkout_service import CheckoutService
from src.services.profile_service import ProfileService

router = APIRouter(prefix="/checkout", tags=["checkout"])


async def _get_profile_for_auth(auth: AuthContext) -> tuple[UUID | None, bool]:
    """Get the profile ID and test account flag for an authenticated user.

    Creates profile if needed.

    Returns:
        tuple: (profile_id, is_test_account)
    """
    if not auth.is_authenticated or not auth.user:
        return None, False
    service = ProfileService()
    profile = await service.get_or_create_profile(auth.user.user_id, auth.user.email)
    return UUID(profile["id"]), profile.get("is_test_account", False)


@router.post(
    "/session",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Stripe Checkout Session",
    description="Creates a Stripe Checkout Session for a robot subscription. Supports both authenticated users and anonymous sessions.",
)
async def create_checkout_session(
    data: CheckoutSessionCreate,
    auth: DualAuth,
) -> CheckoutSessionResponse:
    """Create a Stripe Checkout Session for robot subscription.

    This endpoint creates a pending order and a Stripe Checkout Session.
    The frontend should redirect to the returned checkout_url.

    Args:
        data: Checkout session creation data.
        auth: Dual auth context (user or session).

    Returns:
        CheckoutSessionResponse: Contains checkout_url for redirect.

    Raises:
        HTTPException: 400 if product not found or inactive.
    """
    service = CheckoutService()

    # Extract profile_id, is_test_account, or session_id from auth context
    profile_id, is_test_account = await _get_profile_for_auth(auth)
    session_id = auth.session.session_id if auth.session else None

    try:
        result = await service.create_checkout_session(
            product_id=data.product_id,
            success_url=str(data.success_url),
            cancel_url=str(data.cancel_url),
            profile_id=profile_id,
            session_id=session_id,
            customer_email=data.customer_email,
            is_test_account=is_test_account,
        )

        return CheckoutSessionResponse(
            checkout_url=result["checkout_url"],
            order_id=result["order_id"],
            stripe_session_id=result["stripe_session_id"],
            is_test_mode=result.get("is_test_mode", False),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# Orders router - mounted separately at /orders
orders_router = APIRouter(prefix="/orders", tags=["orders"])


@orders_router.get(
    "",
    response_model=OrderListResponse,
    summary="List my orders",
    description="Returns all orders for the authenticated user or session.",
)
async def list_orders(auth: DualAuth) -> OrderListResponse:
    """List all orders for the current user or session.

    Args:
        auth: Dual auth context (user or session).

    Returns:
        OrderListResponse: List of orders.
    """
    service = CheckoutService()
    profile_id, _ = await _get_profile_for_auth(auth)

    if profile_id:
        orders = await service.get_orders_for_profile(profile_id)
    elif auth.session:
        orders = await service.get_orders_for_session(auth.session.session_id)
    else:
        # No auth context - return empty list
        orders = []

    return OrderListResponse(items=[OrderResponse(**order) for order in orders])


@orders_router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order by ID",
    description="Returns a single order by ID. Only accessible by the order owner.",
)
async def get_order(order_id: UUID, auth: DualAuth) -> OrderResponse:
    """Get a single order by ID.

    Args:
        order_id: The order's UUID.
        auth: Dual auth context (user or session).

    Returns:
        OrderResponse: The order data.

    Raises:
        HTTPException: 404 if order not found.
        HTTPException: 403 if not authorized to view this order.
    """
    service = CheckoutService()

    # Check if user can access this order
    profile_id, _ = await _get_profile_for_auth(auth)
    session_id = auth.session.session_id if auth.session else None

    can_access = await service.can_access_order(
        order_id=order_id,
        profile_id=profile_id,
        session_id=session_id,
    )

    if not can_access:
        # Check if order exists
        order = await service.get_order(order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this order",
        )

    order = await service.get_order(order_id)
    return OrderResponse(**order)

"""Webhook API routes for external service integrations."""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from src.services.checkout_service import CheckoutService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/stripe",
    status_code=status.HTTP_200_OK,
    summary="Handle Stripe webhooks",
    description="Receives and processes Stripe webhook events. Requires valid signature.",
)
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Handle Stripe webhook events.

    This endpoint receives webhook events from Stripe and processes them.
    The Stripe signature is verified before processing.

    Handles:
    - checkout.session.completed: Updates order to completed (card) or payment_pending (ACH)
    - checkout.session.async_payment_succeeded: ACH payment settled, marks order completed
    - checkout.session.async_payment_failed: ACH payment failed, marks order cancelled
    - checkout.session.expired: Updates order to cancelled status

    Args:
        request: FastAPI request object for reading raw body and headers.

    Returns:
        dict: Acknowledgment message.

    Raises:
        HTTPException: 400 if signature is invalid.
    """
    # Get raw body for signature verification
    payload = await request.body()

    # Get Stripe signature header
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        logger.error("Missing Stripe-Signature header in webhook request")
        logger.debug("Request headers: %s", dict(request.headers))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature header",
        )

    logger.info("Received webhook with signature header (length: %d)", len(sig_header))
    logger.debug("Payload size: %d bytes", len(payload))

    service = CheckoutService()

    try:
        # Verify signature and get event (tries both production and test secrets)
        event, is_test_mode = service.verify_webhook_signature(payload, sig_header)
    except ValueError as e:
        logger.error("Invalid webhook signature: %s", str(e))
        logger.debug("Signature header: %s...", sig_header[:50] if sig_header else "None")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        ) from e

    # Process the event
    event_type = event.get("type", "")
    logger.info(
        "Processing Stripe webhook event: %s (test_mode=%s)",
        event_type,
        is_test_mode,
    )

    if event_type == "checkout.session.completed":
        await service.handle_checkout_completed(event)
        logger.info("Processed checkout.session.completed")

    elif event_type == "checkout.session.async_payment_succeeded":
        await service.handle_async_payment_succeeded(event)
        logger.info("Processed checkout.session.async_payment_succeeded")

    elif event_type == "checkout.session.async_payment_failed":
        await service.handle_async_payment_failed(event)
        logger.info("Processed checkout.session.async_payment_failed")

    elif event_type == "checkout.session.expired":
        await service.handle_checkout_expired(event)
        logger.info("Processed checkout.session.expired")

    else:
        # Log unhandled events but return 200 to acknowledge receipt
        logger.debug("Unhandled webhook event type: %s", event_type)

    # Always return 200 OK to acknowledge receipt (idempotent)
    return {"status": "received"}

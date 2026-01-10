#!/usr/bin/env python
"""Script to sync robot catalog products to Stripe.

This script:
1. Reads all robots from the robot_catalog table
2. Creates Stripe products and recurring monthly prices for each robot
3. Updates the database with real Stripe product and price IDs

Usage:
    python scripts/sync_stripe_products.py

Requirements:
    - STRIPE_SECRET_KEY environment variable must be set
    - Database must have robot_catalog table populated
    - Robots should have placeholder Stripe IDs (will be replaced) or can be created fresh

Note:
    This script will create new Stripe products each time it runs if IDs don't exist.
    To avoid duplicates, it checks if the Stripe ID starts with 'prod_' (real Stripe format).
    Placeholder IDs (like 'prod_pudu_cc1_pro') will be replaced.
"""

import asyncio
import logging
import sys
from decimal import Decimal
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.config import get_settings
from src.core.stripe import configure_stripe, get_stripe
from src.core.supabase import get_supabase_client
from src.services.robot_catalog_service import RobotCatalogService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def is_placeholder_stripe_id(stripe_id: str) -> bool:
    """Check if a Stripe ID is a placeholder (not a real Stripe ID format).

    Real Stripe IDs start with 'prod_' followed by a long alphanumeric string.
    Placeholders are simple strings like 'prod_pudu_cc1_pro'.

    Args:
        stripe_id: The Stripe ID to check.

    Returns:
        bool: True if it's a placeholder, False if it looks like a real Stripe ID.
    """
    if not stripe_id or not stripe_id.startswith("prod_"):
        return True
    
    # Real Stripe IDs are much longer (e.g., 'prod_ABC123xyz...')
    # Placeholders are shorter (e.g., 'prod_pudu_cc1_pro')
    # If it has underscores but is short, it's likely a placeholder
    parts = stripe_id.split("_")
    if len(parts) <= 4 and len(stripe_id) < 30:
        return True
    
    return False


def create_stripe_product_and_price(robot: dict) -> tuple[str, str]:
    """Create a Stripe product and recurring monthly price for a robot.

    Args:
        robot: Robot data dictionary with name, monthly_lease, etc.

    Returns:
        tuple: (stripe_product_id, stripe_price_id)
    """
    stripe = get_stripe()
    
    # Build product description from robot attributes
    description_parts = []
    if robot.get("best_for"):
        description_parts.append(f"Best for: {robot['best_for']}")
    if robot.get("modes"):
        description_parts.append(f"Modes: {', '.join(robot['modes'])}")
    if robot.get("surfaces"):
        description_parts.append(f"Surfaces: {', '.join(robot['surfaces'])}")
    if robot.get("specs"):
        description_parts.append(f"Specs: {'; '.join(robot['specs'][:3])}")  # First 3 specs
    
    description = " | ".join(description_parts) if description_parts else f"Robot cleaning solution by {robot.get('manufacturer', 'Unknown')}"
    
    # Create Stripe Product
    product_name = f"{robot.get('manufacturer', '')} {robot['name']}".strip()
    product = stripe.Product.create(
        name=product_name,
        description=description[:500],  # Stripe description limit
        metadata={
            "robot_sku": robot.get("sku", ""),
            "robot_id": str(robot["id"]),
            "category": robot.get("category", ""),
        },
    )
    
    logger.info(f"Created Stripe product: {product.id} - {product_name}")
    
    # Create recurring monthly price
    monthly_lease = robot.get("monthly_lease", 0)
    if isinstance(monthly_lease, (str, Decimal)):
        monthly_lease = float(Decimal(str(monthly_lease)))
    
    # Convert to cents for Stripe
    amount_cents = int(monthly_lease * 100)
    
    price = stripe.Price.create(
        product=product.id,
        unit_amount=amount_cents,
        currency="usd",
        recurring={"interval": "month"},
        metadata={
            "robot_id": str(robot["id"]),
            "robot_sku": robot.get("sku", ""),
        },
    )
    
    logger.info(f"Created Stripe price: {price.id} - ${monthly_lease}/month")
    
    return product.id, price.id


async def sync_all_robots_to_stripe() -> dict:
    """Sync all robots in catalog to Stripe.

    Returns:
        dict: Results with counts of processed, created, updated, and failed robots.
    """
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise ValueError("STRIPE_SECRET_KEY environment variable is not set. Cannot sync to Stripe.")
    
    configure_stripe()
    
    service = RobotCatalogService()
    client = get_supabase_client()
    stripe = get_stripe()
    
    # Get all robots (including inactive for sync purposes)
    robots = await service.list_robots(active_only=False)
    
    processed = 0
    created = 0
    updated = 0
    skipped = 0
    failed = 0
    
    for robot in robots:
        processed += 1
        robot_id = robot["id"]
        robot_name = robot.get("name", "Unknown")
        current_product_id = robot.get("stripe_product_id", "")
        current_price_id = robot.get("stripe_lease_price_id", "")
        
        try:
            # Check if we need to create Stripe products
            needs_sync = (
                is_placeholder_stripe_id(current_product_id) or
                is_placeholder_stripe_id(current_price_id) or
                not current_product_id or
                not current_price_id
            )
            
            if not needs_sync:
                # Verify the Stripe IDs actually exist in Stripe
                try:
                    stripe.Product.retrieve(current_product_id)
                    stripe.Price.retrieve(current_price_id)
                    logger.info(f"Skipping {robot_name} - Stripe products already exist")
                    skipped += 1
                    continue
                except stripe.error.InvalidRequestError:
                    # Product or price doesn't exist in Stripe, need to create
                    logger.warning(f"{robot_name} has invalid Stripe IDs, creating new ones")
                    needs_sync = True
            
            if needs_sync:
                # Create Stripe product and price
                product_id, price_id = create_stripe_product_and_price(robot)
                
                # Update database with real Stripe IDs
                client.table("robot_catalog").update({
                    "stripe_product_id": product_id,
                    "stripe_lease_price_id": price_id,
                }).eq("id", robot_id).execute()
                
                created += 1
                updated += 1
                logger.info(f"Created and updated {robot_name} with Stripe IDs: {product_id}, {price_id}")
            
        except Exception as e:
            failed += 1
            logger.error(f"Failed to sync {robot_name} (ID: {robot_id}): {e}", exc_info=True)
    
    return {
        "processed": processed,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
    }


async def main() -> None:
    """Main entry point for the sync script."""
    logger.info("Starting Stripe product synchronization...")
    
    try:
        results = await sync_all_robots_to_stripe()
        
        logger.info("=" * 60)
        logger.info("Stripe synchronization complete!")
        logger.info(f"Total robots processed: {results['processed']}")
        logger.info(f"Stripe products created: {results['created']}")
        logger.info(f"Database records updated: {results['updated']}")
        logger.info(f"Skipped (already synced): {results['skipped']}")
        logger.info(f"Failed: {results['failed']}")
        logger.info("=" * 60)
        
        if results["failed"] > 0:
            logger.warning("Some robots failed to sync. Check logs for details.")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Synchronization failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


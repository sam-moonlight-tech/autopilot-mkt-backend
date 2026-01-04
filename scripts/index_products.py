#!/usr/bin/env python
"""Script to index all products in Pinecone.

Usage:
    python scripts/index_products.py

This script connects to the database, retrieves all products,
and indexes them in Pinecone for semantic search.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.product_service import ProductService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Index all products in Pinecone."""
    logger.info("Starting product indexing...")

    try:
        service = ProductService()
        result = await service.index_all_products()

        logger.info("Indexing complete!")
        logger.info(f"Total products: {result['total']}")
        logger.info(f"Successfully indexed: {result['indexed']}")
        logger.info(f"Failed: {result['failed']}")

        if result["failed"] > 0:
            logger.warning("Some products failed to index. Check logs for details.")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

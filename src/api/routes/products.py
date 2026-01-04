"""Product API routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import get_current_user
from src.schemas.auth import UserContext
from src.schemas.product import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductSearchRequest,
    ProductSearchResponse,
    ProductSearchResult,
)
from src.services.product_service import ProductService, get_product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=ProductListResponse)
async def list_products(
    category: Annotated[str | None, Query(description="Filter by category")] = None,
    manufacturer: Annotated[str | None, Query(description="Filter by manufacturer")] = None,
    cursor: Annotated[str | None, Query(description="Pagination cursor")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Results per page")] = 20,
    product_service: ProductService = Depends(get_product_service),
) -> ProductListResponse:
    """List products with optional filtering and pagination.

    Products are publicly readable for MVP.
    """
    result = await product_service.list_products(
        category=category,
        manufacturer=manufacturer,
        cursor=cursor,
        limit=limit,
    )

    products = [ProductResponse(**p) for p in result["products"]]

    return ProductListResponse(
        products=products,
        next_cursor=result.get("next_cursor"),
        has_more=result.get("has_more", False),
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    product_service: ProductService = Depends(get_product_service),
) -> ProductResponse:
    """Get a product by ID.

    Products are publicly readable for MVP.
    """
    product = await product_service.get_product(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return ProductResponse(**product)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    current_user: Annotated[UserContext, Depends(get_current_user)],
    product_service: ProductService = Depends(get_product_service),
) -> ProductResponse:
    """Create a new product.

    Requires authentication. In production, would require admin role.
    """
    product = await product_service.create_product(
        data=data.model_dump(),
        index_embedding=True,
    )

    return ProductResponse(**product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    current_user: Annotated[UserContext, Depends(get_current_user)],
    product_service: ProductService = Depends(get_product_service),
) -> None:
    """Delete a product.

    Requires authentication. In production, would require admin role.
    """
    deleted = await product_service.delete_product(product_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )


@router.post("/search", response_model=ProductSearchResponse)
async def search_products(
    request: ProductSearchRequest,
    product_service: ProductService = Depends(get_product_service),
) -> ProductSearchResponse:
    """Search products using semantic similarity.

    Search is publicly accessible for MVP.
    """
    results = await product_service.search_products(
        query=request.query,
        category=request.category,
        top_k=request.top_k,
    )

    search_results = [
        ProductSearchResult(
            product=ProductResponse(**r["product"]),
            score=r["score"],
        )
        for r in results
    ]

    return ProductSearchResponse(
        results=search_results,
        query=request.query,
        total=len(search_results),
    )


@router.post("/index-all", status_code=status.HTTP_200_OK)
async def index_all_products(
    current_user: Annotated[UserContext, Depends(get_current_user)],
    product_service: ProductService = Depends(get_product_service),
) -> dict:
    """Index all products in Pinecone.

    Requires authentication. In production, would require admin role.
    Used for initial indexing or reindexing all products.
    """
    result = await product_service.index_all_products()
    return result

# Implementation Plan: RAG Integration

## Task Overview

This implementation plan establishes RAG (Retrieval-Augmented Generation) capabilities using Pinecone for the Autopilot backend. Tasks build from infrastructure through services to API endpoints, with agent integration last.

## Steering Document Compliance

- Files follow `structure.md` directory layout
- Uses snake_case for modules, PascalCase for classes
- Follows layered architecture: routes → services → core

## Atomic Task Requirements

**Each task meets these criteria:**
- **File Scope**: Touches 1-3 related files maximum
- **Time Boxing**: Completable in 15-30 minutes
- **Single Purpose**: One testable outcome per task
- **Specific Files**: Exact file paths specified
- **Agent-Friendly**: Clear input/output with minimal context switching

## Tasks

- [ ] 5.1. Create products table migration
  - File: `supabase/migrations/004_create_products.sql` (create)
  - Define products table with name, description, category, specs, pricing, embedding_id
  - Add indexes for category and embedding_id
  - Enable RLS (products are public read for MVP)
  - Purpose: Establish product data storage
  - _Requirements: 1_

- [ ] 5.2. Add Pinecone settings to configuration
  - File: `src/core/config.py` (modify)
  - Add pinecone_api_key field
  - Add pinecone_environment field
  - Add pinecone_index_name field
  - Add embedding_model field with default "text-embedding-3-small"
  - Purpose: Configure Pinecone integration
  - _Leverage: existing Settings class_
  - _Requirements: 6_

- [ ] 5.3. Implement Pinecone client singleton
  - File: `src/core/pinecone.py` (create)
  - Create get_pinecone_client() returning Pinecone client
  - Create get_pinecone_index() returning configured index
  - Implement check_pinecone_connection() for health checks
  - Handle connection errors gracefully
  - Purpose: Centralized Pinecone client access
  - _Leverage: src/core/config.py for settings_
  - _Requirements: 6_

- [ ] 5.4. Create product model type hints
  - File: `src/models/product.py` (create)
  - Define Product TypedDict with all table columns
  - Define ProductCategory literal type for valid categories
  - Purpose: Type-safe product data handling
  - _Requirements: 1_

- [ ] 5.5. Create product Pydantic schemas
  - File: `src/schemas/product.py` (create)
  - Define ProductBase, ProductCreate, ProductResponse
  - Define ProductSearchRequest with query, category, top_k
  - Define ProductSearchResult with product and score
  - Define ProductListResponse with pagination
  - Purpose: API request/response contracts for products
  - _Requirements: 1, 4_

- [ ] 5.6. Implement RAGService embedding generation
  - File: `src/services/rag_service.py` (create)
  - Implement generate_embedding() using OpenAI text-embedding-3-small
  - Implement build_embedding_text() to format product data
  - Handle embedding errors with logging
  - Purpose: Generate vector embeddings for products
  - _Leverage: src/core/openai.py_
  - _Requirements: 2_

- [ ] 5.7. Implement RAGService indexing operations
  - File: `src/services/rag_service.py` (modify)
  - Implement index_product() for single product upsert
  - Implement index_products_batch() for batch operations
  - Implement delete_product_embedding() for removal
  - Include product metadata in Pinecone vectors
  - Purpose: Manage product embeddings in Pinecone
  - _Leverage: src/core/pinecone.py_
  - _Requirements: 3_

- [ ] 5.8. Implement RAGService semantic search
  - File: `src/services/rag_service.py` (modify)
  - Implement search_products() querying Pinecone
  - Support category filtering via metadata
  - Return product_id and similarity score
  - Implement get_relevant_products() for agent context
  - Purpose: Enable semantic product search
  - _Leverage: src/core/pinecone.py, src/core/openai.py_
  - _Requirements: 4, 5_

- [ ] 5.9. Implement ProductService core methods
  - File: `src/services/product_service.py` (create)
  - Implement create_product() storing in Supabase
  - Implement get_product() for retrieval
  - Implement list_products() with pagination
  - Purpose: Product CRUD operations
  - _Leverage: src/core/supabase.py_
  - _Requirements: 1_

- [ ] 5.10. Add search and indexing to ProductService
  - File: `src/services/product_service.py` (modify)
  - Implement search_products() combining RAG search with Supabase data
  - Auto-index products on creation if embedding_id is null
  - Purpose: Integrated product search
  - _Leverage: src/services/rag_service.py_
  - _Requirements: 4_

- [ ] 5.11. Integrate RAG context into AgentService
  - File: `src/services/agent_service.py` (modify)
  - Import RAGService
  - Modify build_context() to get relevant products
  - Add _format_products_for_prompt() helper
  - Include product context in system prompt
  - Purpose: Agent responses include relevant products
  - _Leverage: src/services/rag_service.py_
  - _Requirements: 5_

- [ ] 5.12. Create product routes
  - File: `src/api/routes/products.py` (create)
  - Implement GET /products for listing
  - Implement GET /products/{id} for single product
  - Implement POST /products/search for semantic search
  - Products are public read (no auth required)
  - Purpose: Product API endpoints
  - _Leverage: src/services/product_service.py_
  - _Requirements: 1, 4_

- [ ] 5.13. Register product routes in main
  - File: `src/main.py` (modify)
  - Import and include products router at /api/v1/products
  - Purpose: Enable product endpoints
  - _Leverage: existing main.py router setup_
  - _Requirements: 1, 4_

- [ ] 5.14. Add Pinecone to health check
  - File: `src/api/routes/health.py` (modify)
  - Add Pinecone check to readiness endpoint
  - Call check_pinecone_connection()
  - Include in health check response
  - Purpose: Monitor Pinecone connectivity
  - _Leverage: src/core/pinecone.py_
  - _Requirements: 6_

- [ ] 5.15. Create product indexing script
  - File: `scripts/index_products.py` (create)
  - Load products from Supabase
  - Generate embeddings and index to Pinecone
  - Show progress with count/total
  - Handle errors per product (continue on failure)
  - Purpose: Initial and batch product indexing
  - _Leverage: src/services/rag_service.py_
  - _Requirements: 3_

- [ ] 5.16. Update requirements.txt with Pinecone dependency
  - File: `requirements.txt` (modify)
  - Add pinecone-client>=3.0.0
  - Purpose: Ensure Pinecone SDK is installed
  - _Leverage: existing requirements.txt_
  - _Requirements: 6_

- [ ] 5.17. Write unit tests for RAGService
  - File: `tests/unit/test_rag_service.py` (create)
  - Test build_embedding_text formats correctly
  - Test generate_embedding returns vector (mock OpenAI)
  - Test search_products returns results (mock Pinecone)
  - Purpose: Verify RAG logic
  - _Requirements: 2, 4_

- [ ] 5.18. Write unit tests for ProductService
  - File: `tests/unit/test_product_service.py` (create)
  - Test create_product stores in Supabase
  - Test search_products integrates RAG results
  - Purpose: Verify product business logic
  - _Requirements: 1, 4_

- [ ] 5.19. Write integration tests for product endpoints
  - File: `tests/integration/test_product_routes.py` (create)
  - Test GET /products returns products
  - Test POST /products/search with mocked Pinecone
  - Test GET /products/{id} returns single product
  - Purpose: Verify product API end-to-end
  - _Requirements: 1, 4_

- [ ] 5.20. Write integration test for agent with RAG context
  - File: `tests/integration/test_agent_rag.py` (create)
  - Test agent response includes product information
  - Mock OpenAI and Pinecone
  - Verify product context in system prompt
  - Purpose: Verify RAG integration with agent
  - _Requirements: 5_

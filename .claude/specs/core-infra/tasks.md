# Implementation Plan: Core Infrastructure

## Task Overview

This implementation plan establishes the foundational infrastructure for the Autopilot backend. Tasks are ordered to build from configuration through to containerization, with each task producing a testable, atomic deliverable.

## Steering Document Compliance

- All files follow the directory structure defined in `structure.md`
- Uses snake_case for modules, PascalCase for classes per naming conventions
- Follows layered architecture: core → api → routes

## Atomic Task Requirements

**Each task meets these criteria:**
- **File Scope**: Touches 1-3 related files maximum
- **Time Boxing**: Completable in 15-30 minutes
- **Single Purpose**: One testable outcome per task
- **Specific Files**: Exact file paths specified
- **Agent-Friendly**: Clear input/output with minimal context switching

## Task Format Guidelines

- Checkbox format with hierarchical numbering
- Files to create/modify specified explicitly
- Requirements referenced for traceability
- Focus on coding tasks only

## Tasks

- [ ] 1.1. Create project configuration files
  - File: `pyproject.toml` (create)
  - File: `requirements.txt` (create)
  - Define project metadata, Python version (3.11+), and dependencies
  - Dependencies: fastapi, uvicorn, pydantic, pydantic-settings, python-dotenv, supabase, httpx
  - Purpose: Establish package management foundation
  - _Requirements: 1, 2_

- [ ] 1.2. Create environment template and gitignore
  - File: `.env.example` (create)
  - File: `.gitignore` (create)
  - Define all required environment variables with placeholder values
  - Include standard Python gitignore patterns plus .env
  - Purpose: Document configuration requirements, prevent secret commits
  - _Requirements: 2_

- [ ] 1.3. Create src package structure with init files
  - File: `src/__init__.py` (create)
  - File: `src/core/__init__.py` (create)
  - File: `src/api/__init__.py` (create)
  - File: `src/api/routes/__init__.py` (create)
  - File: `src/api/middleware/__init__.py` (create)
  - File: `src/schemas/__init__.py` (create)
  - Create empty __init__.py files to establish Python packages
  - Purpose: Enable imports across the application
  - _Requirements: 1_

- [ ] 1.4. Implement Settings class in config module
  - File: `src/core/config.py` (create)
  - Create Settings class extending pydantic_settings.BaseSettings
  - Define all environment variables with types and defaults
  - Implement get_settings() singleton function with lru_cache
  - Purpose: Centralize environment configuration
  - _Requirements: 2_

- [ ] 1.5. Implement Supabase client singleton
  - File: `src/core/supabase.py` (create)
  - Create get_supabase_client() function returning Client singleton
  - Use service role key from settings for backend operations
  - Implement check_database_connection() async function
  - Purpose: Provide database access throughout application
  - _Requirements: 3_

- [ ] 1.6. Create common schemas for health and errors
  - File: `src/schemas/common.py` (create)
  - Define HealthResponse, ReadinessResponse, CheckResult schemas
  - Define ErrorDetail, ErrorResponse schemas
  - Use Pydantic v2 syntax with model_config
  - Purpose: Establish API response contracts
  - _Requirements: 4, 5_

- [ ] 1.7. Implement error handler middleware
  - File: `src/api/middleware/error_handler.py` (create)
  - Create error_handler_middleware async function
  - Define APIError base exception class
  - Format all exceptions into ErrorResponse schema
  - Log exceptions with full stack trace
  - Purpose: Ensure consistent error responses
  - _Requirements: 5_

- [ ] 1.8. Implement health check routes
  - File: `src/api/routes/health.py` (create)
  - Create router with /health and /health/ready endpoints
  - Implement basic liveness check returning HealthResponse
  - Implement readiness check calling check_database_connection()
  - Return 503 if database check fails
  - Purpose: Enable monitoring and deployment verification
  - _Requirements: 4_

- [ ] 1.9. Create FastAPI application entry point
  - File: `src/main.py` (create)
  - Create FastAPI app instance with title, description, version
  - Configure CORS middleware with settings.cors_origins
  - Add error handler middleware
  - Mount health router at root level
  - Create /api/v1 router prefix for future routes
  - Purpose: Application entry point with all middleware configured
  - _Requirements: 1_

- [ ] 1.10. Create Dockerfile for production
  - File: `Dockerfile` (create)
  - Use multi-stage build with python:3.11-slim
  - Install dependencies in builder stage
  - Copy only necessary files to final image
  - Configure uvicorn to run on port 8080
  - Set appropriate environment defaults
  - Purpose: Enable GCP Cloud Run deployment
  - _Requirements: 6_

- [ ] 1.11. Create docker-compose for local development
  - File: `docker-compose.yml` (create)
  - Define api service with build context
  - Mount src directory for hot-reloading
  - Load environment from .env file
  - Expose port 8080
  - Configure uvicorn with --reload flag
  - Purpose: Enable local development workflow
  - _Requirements: 7_

- [ ] 1.12. Create tests directory structure and conftest
  - File: `tests/__init__.py` (create)
  - File: `tests/conftest.py` (create)
  - File: `tests/unit/__init__.py` (create)
  - Set up pytest fixtures for test client and settings override
  - Configure async test support with pytest-asyncio
  - Purpose: Establish testing foundation
  - _Requirements: 1_

- [ ] 1.13. Write unit tests for config module
  - File: `tests/unit/test_config.py` (create)
  - Test Settings loads from environment variables
  - Test get_settings() returns cached singleton
  - Test validation errors for missing required vars
  - Purpose: Verify configuration management
  - _Requirements: 2_

- [ ] 1.14. Write integration tests for health endpoints
  - File: `tests/integration/__init__.py` (create)
  - File: `tests/integration/test_health.py` (create)
  - Test GET /health returns 200 with healthy status
  - Test GET /health/ready returns 200 when database connected
  - Test error responses match ErrorResponse schema
  - Purpose: Verify API endpoints work correctly
  - _Requirements: 4, 5_

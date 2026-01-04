# Project Structure

## Directory Organization

```
autopilot-mkt-backend/
├── .claude/                    # Claude Code workflow infrastructure
│   ├── agents/                 # Spec validator/executor agents
│   ├── commands/               # CLI command definitions
│   ├── specs/                  # Feature specifications
│   │   └── {feature-name}/
│   │       ├── requirements.md
│   │       ├── design.md
│   │       └── tasks.md
│   ├── steering/               # Project steering documents
│   │   ├── product.md
│   │   ├── tech.md
│   │   └── structure.md
│   └── templates/              # Spec templates
├── src/                        # Application source code
│   ├── api/                    # API layer
│   │   ├── routes/             # FastAPI router modules
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   ├── profiles.py
│   │   │   ├── companies.py
│   │   │   ├── conversations.py
│   │   │   └── products.py
│   │   ├── middleware/         # Request/response middleware
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   └── error_handler.py
│   │   └── deps.py             # Dependency injection (get_current_user, etc.)
│   ├── core/                   # Core infrastructure
│   │   ├── __init__.py
│   │   ├── config.py           # Settings from environment
│   │   ├── supabase.py         # Supabase client singleton
│   │   ├── openai.py           # OpenAI client singleton
│   │   └── pinecone.py         # Pinecone client singleton
│   ├── models/                 # Database table representations
│   │   ├── __init__.py
│   │   ├── profile.py
│   │   ├── company.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   └── product.py
│   ├── schemas/                # Pydantic request/response models
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── profile.py
│   │   ├── company.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   └── product.py
│   ├── services/               # Business logic layer
│   │   ├── __init__.py
│   │   ├── profile_service.py
│   │   ├── company_service.py
│   │   ├── conversation_service.py
│   │   ├── agent_service.py    # OpenAI agent orchestration
│   │   └── rag_service.py      # Pinecone search operations
│   └── main.py                 # FastAPI application entry point
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── unit/                   # Unit tests
│   │   ├── __init__.py
│   │   ├── test_services/
│   │   └── test_schemas/
│   └── integration/            # Integration tests
│       ├── __init__.py
│       └── test_api/
├── scripts/                    # Utility scripts
│   └── index_products.py       # One-time product indexing
├── supabase/                   # Supabase configuration
│   └── migrations/             # SQL migration files
│       ├── 001_create_profiles.sql
│       ├── 002_create_companies.sql
│       ├── 003_create_conversations.sql
│       ├── 004_create_products.sql
│       └── 005_enable_rls_policies.sql
├── .env.example                # Environment variable template
├── .gitignore
├── Dockerfile                  # Production container
├── docker-compose.yml          # Local development
├── pyproject.toml              # Project metadata and dependencies
├── requirements.txt            # Pinned dependencies
└── README.md                   # Project documentation
```

## Naming Conventions

### Files
- **Modules**: `snake_case.py` (e.g., `profile_service.py`, `error_handler.py`)
- **Routes**: Named by resource (e.g., `profiles.py`, `conversations.py`)
- **Tests**: `test_{module_name}.py` (e.g., `test_profile_service.py`)

### Code
- **Classes**: `PascalCase` (e.g., `ProfileService`, `ConversationCreate`)
- **Functions/Methods**: `snake_case` (e.g., `get_profile`, `create_conversation`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_PAGE_SIZE`, `MAX_CONTEXT_TOKENS`)
- **Variables**: `snake_case` (e.g., `user_id`, `conversation_history`)
- **Pydantic Schemas**: `{Resource}{Action}` (e.g., `ProfileUpdate`, `ConversationCreate`, `MessageResponse`)

### Database
- **Tables**: `snake_case` plural (e.g., `profiles`, `conversations`, `company_members`)
- **Columns**: `snake_case` (e.g., `user_id`, `created_at`, `display_name`)
- **Foreign Keys**: `{referenced_table_singular}_id` (e.g., `profile_id`, `company_id`)

## Import Patterns

### Import Order
1. Standard library imports
2. Third-party imports
3. Local application imports (absolute from `src`)

### Example
```python
# Standard library
from datetime import datetime
from typing import Optional
from uuid import UUID

# Third-party
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

# Local application
from src.core.supabase import get_supabase_client
from src.schemas.profile import ProfileResponse
from src.services.profile_service import ProfileService
```

### Module Organization
- Use absolute imports from `src` package
- Group related imports together
- Avoid circular imports by keeping clear layer boundaries

## Code Structure Patterns

### Router Module Pattern
```python
# src/api/routes/{resource}.py
from fastapi import APIRouter, Depends, HTTPException, status
from src.api.deps import get_current_user
from src.schemas.{resource} import {Resource}Create, {Resource}Response
from src.services.{resource}_service import {Resource}Service

router = APIRouter(prefix="/{resources}", tags=["{resources}"])

@router.post("/", response_model={Resource}Response, status_code=status.HTTP_201_CREATED)
async def create_{resource}(
    data: {Resource}Create,
    user = Depends(get_current_user)
):
    service = {Resource}Service()
    return await service.create(data, user.id)
```

### Service Module Pattern
```python
# src/services/{resource}_service.py
from uuid import UUID
from src.core.supabase import get_supabase_client
from src.schemas.{resource} import {Resource}Create, {Resource}Update

class {Resource}Service:
    def __init__(self):
        self.client = get_supabase_client()

    async def create(self, data: {Resource}Create, user_id: UUID) -> dict:
        # Implementation
        pass

    async def get_by_id(self, id: UUID) -> dict | None:
        # Implementation
        pass
```

### Schema Module Pattern
```python
# src/schemas/{resource}.py
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class {Resource}Base(BaseModel):
    # Shared fields
    pass

class {Resource}Create({Resource}Base):
    # Fields for creation
    pass

class {Resource}Update(BaseModel):
    # Optional fields for update
    pass

class {Resource}Response({Resource}Base):
    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

## Code Organization Principles

1. **Single Responsibility**: Each module has one clear purpose
2. **Layer Isolation**: Routes → Services → Models (no skipping layers)
3. **Dependency Direction**: Higher layers depend on lower layers, never reverse
4. **Testability**: Services are stateless and can be tested with mocked dependencies

## Module Boundaries

### API Layer (`src/api/`)
- Handles HTTP request/response
- Input validation via Pydantic schemas
- Authentication via middleware
- Calls service layer for business logic
- **Never accesses database directly**

### Service Layer (`src/services/`)
- Contains all business logic
- Orchestrates multiple operations
- Handles errors and edge cases
- Calls core clients for external services
- **Never handles HTTP concerns**

### Core Layer (`src/core/`)
- Client singletons (Supabase, OpenAI, Pinecone)
- Configuration management
- Shared utilities
- **No business logic**

### Schema Layer (`src/schemas/`)
- Pydantic models for API contracts
- Request validation
- Response serialization
- **No business logic**

### Model Layer (`src/models/`)
- Database table representations
- Type hints for database operations
- **No business logic**

## Code Size Guidelines

- **File size**: Target <300 lines per file; split if exceeding 500
- **Function size**: Target <30 lines per function; extract helpers if longer
- **Class complexity**: Target <10 methods per class
- **Nesting depth**: Maximum 3 levels of nesting

## Documentation Standards

- All public functions must have docstrings with parameter and return descriptions
- Complex logic should include inline comments explaining "why"
- Each module should have a module-level docstring describing its purpose
- API endpoints are documented via FastAPI's automatic OpenAPI generation

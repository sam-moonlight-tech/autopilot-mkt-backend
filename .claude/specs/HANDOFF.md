# Autopilot Backend - Implementation Handoff

## Project Overview

You are continuing work on the **Autopilot Backend**, a dockerized FastAPI application for an agent-led robotics procurement platform. All planning and specification work is complete. Your task is to **execute the implementation** following the spec-driven workflow.

## What Has Been Completed

### Steering Documents (`.claude/steering/`)
- `product.md` - Product vision and success criteria
- `tech.md` - Technology stack (Python/FastAPI/Supabase/OpenAI/Pinecone)
- `structure.md` - Project structure and coding conventions

### Feature Specifications (`.claude/specs/`)
Five complete specifications with requirements, design, and tasks:

1. **core-infra** (14 tasks) - Docker, FastAPI scaffold, Supabase client, health endpoints
2. **auth** (10 tasks) - JWT verification middleware, protected routes
3. **profiles** (20 tasks) - User profiles, companies, invitations
4. **conversations** (21 tasks) - Messages, OpenAI GPT-4o integration
5. **rag-integration** (20 tasks) - Pinecone vector search, product catalog

## Technical Stack
- **Runtime**: Python 3.11+ with FastAPI
- **Database/Auth**: Supabase (PostgreSQL + JWT auth)
- **LLM**: OpenAI GPT-4o
- **Vector DB**: Pinecone for RAG
- **Deployment**: Docker on GCP Cloud Run

## Execution Order

Execute specs in this order (dependencies flow downward):

```
core-infra → auth → profiles → conversations
                              ↘
                         rag-integration
```

## How to Execute

### Option 1: Use Spec Task Executor Agent
For each task, invoke the spec-task-executor agent:
```
Read the task from .claude/specs/{feature}/tasks.md
Execute the specific task number (e.g., 1.1, 1.2, etc.)
Mark complete when done
```

### Option 2: Manual Execution
1. Read `.claude/specs/core-infra/tasks.md`
2. Execute tasks in order (1.1 → 1.2 → ... → 1.14)
3. Move to next spec when complete

## Key Files to Create First (core-infra)

```
pyproject.toml          # Project dependencies
requirements.txt        # Pinned versions
.env.example           # Environment template
.gitignore             # Git ignore rules
src/
├── __init__.py
├── main.py            # FastAPI entry point
├── core/
│   ├── __init__.py
│   ├── config.py      # Settings management
│   └── supabase.py    # Supabase client
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── __init__.py
│   │   └── health.py  # Health endpoints
│   └── middleware/
│       ├── __init__.py
│       └── error_handler.py
└── schemas/
    ├── __init__.py
    └── common.py      # Shared schemas
Dockerfile             # Production container
docker-compose.yml     # Local development
```

## Environment Variables Required

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
OPENAI_API_KEY=your-openai-key
PINECONE_API_KEY=your-pinecone-key
PINECONE_ENVIRONMENT=your-environment
PINECONE_INDEX_NAME=autopilot-products
```

## Important Conventions

From `structure.md`:
- **Files**: snake_case (e.g., `profile_service.py`)
- **Classes**: PascalCase (e.g., `ProfileService`)
- **Functions**: snake_case (e.g., `get_profile`)
- **Schemas**: `{Resource}{Action}` (e.g., `ProfileUpdate`, `ConversationCreate`)

## Validation Agents

Before moving to the next spec, you can validate using:
- `spec-requirements-validator` - Validates requirements.md
- `spec-design-validator` - Validates design.md against requirements
- `spec-task-validator` - Validates tasks.md against design

## Success Criteria

The implementation is complete when:
- [ ] Docker container builds and runs
- [ ] Health endpoints respond correctly
- [ ] JWT auth middleware validates Supabase tokens
- [ ] Profile and company CRUD operations work
- [ ] Conversations can be created with agent responses
- [ ] Product search returns semantically relevant results
- [ ] All tests pass

## Start Here

Begin with **core-infra task 1.1**: Create project configuration files (`pyproject.toml`, `requirements.txt`)

Read the full task details in:
```
.claude/specs/core-infra/tasks.md
```

Good luck with the implementation!

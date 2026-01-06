# Autopilot Marketplace Backend

Agent-led robotics procurement platform backend API built with FastAPI.

## Overview

The Autopilot Marketplace Backend is a FastAPI-based REST API that powers an agent-led procurement experience for robotic cleaning and automation solutions. The platform enables buyers to:

- **Discover** relevant robotic solutions through guided conversational discovery
- **Evaluate** options with dynamic marketplace views and ROI calculations
- **Commit** to purchases through streamlined checkout and order management

This backend supports the three-phase user journey: Discovery → ROI Walkthrough → Greenlight/Checkout, as defined in the [Product Requirements Document](docs/PRD%20%28Clean%20v1%29%20%E2%80%94%20Autopilot%20Agent-Led%20Procurement%20Platform%20%28Internal%20MVP%29.pdf).

## Architecture

### Technology Stack

- **Framework**: FastAPI 0.109+ with Python 3.11+
- **Database**: Supabase (PostgreSQL) with Python SDK
- **AI/ML**: OpenAI GPT-4 for agent conversations, Pinecone for vector search
- **Payments**: Stripe for checkout and order processing
- **Deployment**: Docker containers on Google Cloud Run
- **Testing**: pytest with async support

### Project Structure

```
autopilot-mkt-backend/
├── src/
│   ├── api/              # API routes and middleware
│   │   ├── routes/       # Endpoint handlers
│   │   └── middleware/   # Auth, error handling
│   ├── core/             # Core services (config, clients)
│   ├── models/           # Database models
│   ├── schemas/          # Pydantic request/response schemas
│   └── services/         # Business logic services
├── knowledge/            # Extracted sales knowledge (JSON)
├── supabase/
│   └── migrations/       # Database migration scripts
├── tests/                # Test suite
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── scripts/              # Deployment and utility scripts
└── docs/                 # Documentation
```

### Key Components

- **Agent Service**: Orchestrates AI-powered conversations using OpenAI
- **RAG Service**: Retrieval-Augmented Generation for product recommendations
- **Sales Knowledge Service**: Phase-specific context injection from real customer conversations
- **Session Management**: Stateless session handling with cookie-based auth
- **Discovery Profiles**: Captures facility profiles and procurement priorities
- **Product Catalog**: Vector search-enabled product discovery
- **Checkout Service**: Stripe integration for order processing

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose (for local development)
- Supabase account and project
- OpenAI API key
- Pinecone account and index
- Stripe account (for checkout features)
- Google Cloud SDK (for deployment)

### Environment Setup

1. **Clone the repository**

```bash
git clone <repository-url>
cd autopilot-mkt-backend
```

1. **Create a virtual environment**

```bash
python3.11 -m venv venv
```

**Activate the virtual environment:**

- **Bash/Zsh**: `source venv/bin/activate`
- **Fish**: `source venv/bin/activate.fish`
- **Windows (PowerShell)**: `venv\Scripts\Activate.ps1`
- **Windows (CMD)**: `venv\Scripts\activate.bat`

You should see `(venv)` in your prompt when activated.

1. **Install dependencies**

```bash
pip install -r requirements.txt
```

1. **Configure environment variables**

Create a `.env` file in the project root:

```bash
cp .env.example .env  # If example exists, or create manually
```

Required environment variables:

```env
# Application
APP_NAME=autopilot-backend
APP_ENV=development
DEBUG=true
HOST=0.0.0.0
PORT=8080

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Auth
AUTH_REDIRECT_URL=https://autopilot-marketplace-discovery-to.vercel.app

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SECRET_KEY=your-service-role-key
SUPABASE_SIGNING_KEY_JWK={"kty":"RSA","n":"...","e":"..."}

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
MAX_CONTEXT_MESSAGES=20

# Pinecone
PINECONE_API_KEY=your-pinecone-key
PINECONE_ENVIRONMENT=your-environment
PINECONE_INDEX_NAME=autopilot-products
EMBEDDING_MODEL=text-embedding-3-small

# Session
SESSION_COOKIE_NAME=autopilot_session
SESSION_COOKIE_MAX_AGE=2592000
SESSION_COOKIE_SECURE=false  # Set to true in production
SESSION_EXPIRY_DAYS=30

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
```

1. **Run database migrations**

Apply Supabase migrations using the Supabase CLI or dashboard:

```bash
# Using Supabase CLI
supabase db push

# Or manually apply migrations from supabase/migrations/
```

1. **Start the development server**

```bash
# Option 1: Direct Python
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080

# Option 2: Docker Compose (recommended for local dev)
docker-compose up
```

The API will be available at `http://localhost:8080`

- API Documentation: `http://localhost:8080/docs` (Swagger UI)
- Alternative Docs: `http://localhost:8080/redoc` (ReDoc)

## Development

### Code Style

The project uses:

- **Ruff** for linting and formatting (configured in `pyproject.toml`)
- **mypy** for type checking (strict mode enabled)

Run linting:

```bash
ruff check src tests
ruff format src tests
```

Run type checking:

```bash
mypy src
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_config.py

# Run integration tests
pytest tests/integration/
```

### Debugging

The project includes VS Code launch configurations (`.vscode/launch.json`) for debugging:

- **Python: FastAPI** - Debug the FastAPI application
- **Python: Current File** - Debug the currently open Python file
- **Python: Pytest** - Debug pytest tests

Press `F5` in VS Code to start debugging, or use the Debug panel.

### Database Migrations

Migrations are stored in `supabase/migrations/` and should be applied in order:

1. `001_create_profiles.sql`
2. `002_create_companies.sql`
3. `003_create_conversations.sql`
4. `004_create_products.sql`
5. `005_create_sessions.sql`
6. `006_create_discovery_profiles.sql`
7. `007_create_robot_catalog.sql`
8. `008_create_orders.sql`
9. `009_update_conversations.sql`

### Sales Knowledge Extraction

The platform uses structured knowledge extracted from real sales call transcripts to enhance agent conversations. This knowledge is injected into the agent's context based on the current conversation phase.

#### Knowledge Structure

Knowledge files are stored in `knowledge/` directory:

| File | Description |
|------|-------------|
| `personas.json` | Customer/facility profiles (court counts, surfaces, staff size) |
| `pain_points.json` | Pain points in customer language |
| `questions_asked.json` | Common prospect questions by topic |
| `objections_discovery.json` | Early-stage objections |
| `buying_signals.json` | Interest indicators and their strength |
| `objection_responses.json` | Proven objection-response pairs |
| `roi_examples.json` | Real ROI calculations from customer deals |
| `closing_triggers.json` | What drives purchase decisions |
| `pricing_insights.json` | Negotiation patterns and outcomes |

#### Phase-Specific Injection

The `SalesKnowledgeService` provides context based on conversation phase:

- **DISCOVERY**: Pain points to probe, common questions, buying signals, early objections
- **ROI**: ROI examples, labor cost comparisons, value justification patterns
- **GREENLIGHT**: Objection-response pairs, closing triggers, pricing insights

#### Running Knowledge Extraction

To extract knowledge from new call transcripts:

1. **Add PDF transcripts** to the appropriate folder:
   - `Discovery Calls/` - Initial discovery conversations
   - `Greenlight Call/` - Closing and pricing conversations

2. **Run the extraction script**:

```bash
# Activate virtual environment
source venv/bin/activate

# Run extraction (requires OpenAI API key)
OPENAI_API_KEY="your-api-key" python scripts/extract_call_knowledge.py
```

3. **Review extracted knowledge** in `knowledge/` directory

The extraction script:
- Parses PDF transcripts using PyMuPDF
- Uses GPT-4 to identify and extract structured insights
- Merges knowledge from all transcripts into consolidated JSON files
- Preserves source attribution for each insight

#### Adding New Knowledge Manually

You can also manually add entries to the JSON files. Each entry should follow the existing schema:

```json
// Example pain_points.json entry
{
  "category": "time|labor|quality|cost|health|court_preservation",
  "customer_quote": "exact customer language",
  "context": "situation context",
  "source": "source file or manual"
}
```

## API Documentation

### Core Endpoints

#### Health Checks

- `GET /health` - Liveness check
- `GET /health/ready` - Readiness check (includes dependency verification)

#### Authentication

- `POST /api/v1/auth/signup` - Sign up new user with email and password
- `POST /api/v1/auth/login` - User login with email and password
- `POST /api/v1/auth/verify-email` - Verify email address with token
- `GET /api/v1/auth/verify-email` - Verify email via GET (for email link redirects)
- `POST /api/v1/auth/resend-verification` - Resend verification email
- `POST /api/v1/auth/forgot-password` - Request password reset email
- `POST /api/v1/auth/reset-password` - Reset password with token from email
- `GET /api/v1/auth/reset-password` - Reset password via GET (for email link redirects)
- `POST /api/v1/auth/change-password` - Change password for authenticated user
- `POST /api/v1/auth/refresh` - Refresh access token using refresh token
- `POST /api/v1/auth/logout` - User logout
- `GET /api/v1/auth/me` - Get current user context

#### Sessions

- `POST /api/v1/sessions` - Create anonymous session
- `GET /api/v1/sessions/{session_id}` - Get session details

#### Profiles & Companies

- `GET /api/v1/profiles/me` - Get current user profile
- `PUT /api/v1/profiles/me` - Update profile
- `GET /api/v1/companies/{company_id}` - Get company details
- `POST /api/v1/invitations` - Create company invitation

#### Discovery

- `GET /api/v1/discovery/profile` - Get discovery profile
- `PUT /api/v1/discovery/profile` - Update discovery profile

#### Conversations

- `POST /api/v1/conversations` - Create conversation
- `GET /api/v1/conversations` - List conversations
- `GET /api/v1/conversations/{id}` - Get conversation
- `DELETE /api/v1/conversations/{id}` - Delete conversation
- `POST /api/v1/conversations/{id}/messages` - Send message (triggers agent response)
- `GET /api/v1/conversations/{id}/messages` - Get message history

#### Products

- `GET /api/v1/products` - List products (with filtering)
- `GET /api/v1/products/{id}` - Get product details
- `POST /api/v1/products/search` - Semantic product search (RAG)

#### Robot Catalog

- `GET /api/v1/robots` - List all robots
- `GET /api/v1/robots/{id}` - Get robot details

#### Checkout & Orders

- `POST /api/v1/checkout` - Create checkout session
- `GET /api/v1/orders` - List orders
- `GET /api/v1/orders/{id}` - Get order details

#### Webhooks

- `POST /api/v1/webhooks/stripe` - Stripe webhook handler

### Authentication

The API supports two authentication modes:

1. **User Authentication**: Supabase JWT tokens (for authenticated users)
2. **Session Authentication**: Cookie-based sessions (for anonymous users)

Most endpoints support both modes via the `DualAuth` dependency.

## Deployment

### Google Cloud Run

The project is configured for deployment to Google Cloud Run using Docker.

#### Prerequisites

- Google Cloud SDK installed and configured
- Docker installed
- GCP project with Cloud Run API enabled
- Artifact Registry repository (created automatically by deploy script)

#### Deploy

```bash
# Basic deployment
./scripts/deploy-cloud-run.sh [SERVICE_NAME] [REGION] [PROJECT_ID]

# With custom configuration
MIN_INSTANCES=1 MAX_INSTANCES=10 CPU=2 MEMORY=1Gi ./scripts/deploy-cloud-run.sh
```

#### Using Secret Manager

For production, use Google Secret Manager:

```bash
# Set up secrets first
./scripts/setup-secrets.sh

# Deploy with secrets
USE_SECRETS=true ./scripts/deploy-cloud-run.sh
```

#### Cloud Build

The project includes `cloudbuild.yaml` for automated builds:

```bash
gcloud builds submit --config cloudbuild.yaml
```

### Environment Configuration

Production environment variables should be set via:

- Cloud Run environment variables (for non-sensitive config)
- Google Secret Manager (for API keys and secrets)

## Testing

### Test Structure

- **Unit Tests** (`tests/unit/`): Test individual components in isolation
- **Integration Tests** (`tests/integration/`): Test API endpoints and service interactions

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=term-missing

# Specific category
pytest tests/unit/
pytest tests/integration/

# Specific test
pytest tests/integration/test_health.py::test_health_check
```

### Test Fixtures

Common fixtures are defined in `tests/conftest.py`:

- `test_client`: FastAPI test client
- `mock_settings`: Override settings for testing
- `mock_supabase`: Mock Supabase client

## Monitoring & Observability

### Health Checks

- `/health` - Basic liveness probe (always returns 200 if service is running)
- `/health/ready` - Readiness probe (checks database and Pinecone connectivity)

### Logging

The application uses Python's standard logging module. Log levels are controlled via environment variables and default to INFO.

Structured logging includes:

- Request/response logging
- Error stack traces
- Startup/shutdown events

## Contributing

### Development Workflow

1. Create a feature branch from `main`
2. Make changes following the code style guidelines
3. Write/update tests
4. Run linting and type checking
5. Ensure all tests pass
6. Submit a pull request

### Code Standards

- Follow PEP 8 style guidelines (enforced by Ruff)
- Use type hints for all function signatures
- Write docstrings for public functions and classes
- Keep functions focused and single-purpose
- Write tests for new features

### Project Specifications

Detailed specifications are available in `.claude/specs/`:

- `core-infra/` - Core infrastructure requirements and design
- `profiles/` - User profile management
- `conversations/` - Agent conversation system
- `rag-integration/` - RAG service implementation
- `checkout-stripe/` - Checkout and payment processing

## Troubleshooting

### Common Issues

**Database Connection Errors**

- Verify `SUPABASE_URL` and `SUPABASE_SECRET_KEY` are correct
- Check Supabase project is active and accessible
- Ensure migrations have been applied

**OpenAI API Errors**

- Verify `OPENAI_API_KEY` is valid and has credits
- Check rate limits and quota
- Verify model name matches available models

**Pinecone Connection Errors**

- Verify `PINECONE_API_KEY` and `PINECONE_ENVIRONMENT` are correct
- Ensure index exists and is accessible
- Check index name matches `PINECONE_INDEX_NAME`

**CORS Errors**

- Verify `CORS_ORIGINS` includes your frontend URL
- Check frontend is sending correct headers
- Ensure credentials are included if using cookies

### Debug Mode

Enable debug mode for detailed error messages:

```env
DEBUG=true
```

**Note**: Never enable debug mode in production.

## License

Proprietary - Moonlight Technologies

## Support

For questions or issues, contact the development team or refer to the project specifications in `.claude/specs/`.

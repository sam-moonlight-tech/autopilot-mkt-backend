# Implementation Plan: Checkout & Stripe Integration

## Task Overview

This implementation plan establishes the robot product catalog, Stripe subscription checkout, and order management system. Tasks are ordered to build database schema first, then Stripe infrastructure, then models/schemas, then services, and finally routes.

## Steering Document Compliance

- Files follow `structure.md` directory layout
- Uses snake_case for modules, PascalCase for classes
- Follows layered architecture: routes -> services -> models

## Atomic Task Requirements

**Each task meets these criteria:**
- **File Scope**: Touches 1-3 related files maximum
- **Time Boxing**: Completable in 15-30 minutes
- **Single Purpose**: One testable outcome per task
- **Specific Files**: Exact file paths specified
- **Agent-Friendly**: Clear input/output with minimal context switching

## Tasks

### Database Layer

- [x] 7.1. Create robot_catalog table migration
  - File: `supabase/migrations/007_create_robot_catalog.sql` (create)
  - Create robot_catalog table with: id, name, category, best_for, modes (TEXT[]), surfaces (TEXT[]), monthly_lease, purchase_price, time_efficiency, key_reasons (TEXT[]), specs (TEXT[]), image_url, stripe_product_id, stripe_lease_price_id, active, timestamps
  - Add check constraint for time_efficiency between 0 and 1
  - Add indexes on active and category
  - Enable RLS with public read policy
  - Purpose: Establish robot product catalog storage
  - _Requirements: 1, 2_

- [x] 7.2. Seed robot catalog data
  - File: `supabase/migrations/007_create_robot_catalog.sql` (modify)
  - Add INSERT statements for 5 robots matching frontend ROBOT_CATALOG
  - Include placeholder Stripe IDs (to be updated with real IDs)
  - Robot data: Pudu CC1 Pro, Pudu MT1 Vac, MaxBattery Pro, FoodRunner V2, BudgetVac Mini
  - Purpose: Populate initial product catalog
  - _Requirements: 1_

- [x] 7.3. Create orders table migration
  - File: `supabase/migrations/008_create_orders.sql` (create)
  - Create order_status enum: 'pending', 'processing', 'completed', 'cancelled', 'refunded'
  - Create orders table with: id, profile_id (nullable FK), session_id (nullable FK), stripe_checkout_session_id (unique), stripe_customer_id, stripe_subscription_id, status, line_items (JSONB), total_cents, currency, customer_email, metadata, completed_at, timestamps
  - Add check constraint: profile_id OR session_id must be non-null
  - Add indexes on profile_id, session_id, stripe_checkout_session_id, status, created_at
  - Enable RLS with profile owner read policy
  - Purpose: Establish order tracking storage
  - _Requirements: 5, 6_

### Stripe Infrastructure

- [x] 7.4. Create Stripe client singleton
  - File: `src/core/stripe.py` (create)
  - Import stripe SDK
  - Create configure_stripe() function that sets stripe.api_key from settings
  - Create get_stripe() function that returns configured stripe module
  - Purpose: Centralized Stripe SDK configuration
  - _Requirements: 2, 3_

- [x] 7.5. Add Stripe configuration settings
  - File: `src/core/config.py` (modify)
  - Add stripe_secret_key: str field
  - Add stripe_webhook_secret: str field
  - Add stripe_publishable_key: str field (optional, for frontend)
  - Purpose: Configurable Stripe settings
  - _Requirements: 2, 3_

- [x] 7.6. Update environment example
  - File: `.env.example` (modify)
  - Add STRIPE_SECRET_KEY=sk_test_...
  - Add STRIPE_WEBHOOK_SECRET=whsec_...
  - Add STRIPE_PUBLISHABLE_KEY=pk_test_...
  - Purpose: Document required Stripe environment variables
  - _Requirements: Non-functional security_

### Model Layer

- [x] 7.7. Create robot model type hints
  - File: `src/models/robot.py` (create)
  - Define Robot TypedDict with all table columns
  - Include types for array fields (list[str])
  - Include Decimal for monetary fields
  - Purpose: Type-safe robot data handling
  - _Requirements: 1_

- [x] 7.8. Create order model type hints
  - File: `src/models/order.py` (create)
  - Define OrderStatus literal type
  - Define Order TypedDict with all table columns
  - Define OrderLineItem TypedDict for line_items structure
  - Purpose: Type-safe order data handling
  - _Requirements: 6_

### Schema Layer

- [x] 7.9. Create robot Pydantic schemas
  - File: `src/schemas/robot.py` (create)
  - Define RobotResponse with all fields plus computed camelCase aliases
  - Add computed_field properties for frontend compatibility: monthlyLease, purchasePrice, timeEfficiency, bestFor, keyReasons
  - Define RobotListResponse with items array
  - Purpose: API contracts for robot endpoints
  - _Requirements: 1_

- [x] 7.10. Create checkout Pydantic schemas
  - File: `src/schemas/checkout.py` (create)
  - Define CheckoutSessionCreate with: product_id, success_url, cancel_url, customer_email (optional)
  - Define CheckoutSessionResponse with: checkout_url, order_id, stripe_session_id
  - Define OrderResponse with all order fields
  - Define OrderListResponse with items array
  - Purpose: API contracts for checkout endpoints
  - _Requirements: 3, 5_

### Service Layer

- [x] 7.11. Implement RobotCatalogService
  - File: `src/services/robot_catalog_service.py` (create)
  - Implement list_robots(active_only=True) returning list of robots
  - Implement get_robot(robot_id) returning single robot or None
  - Implement get_robot_with_stripe_ids(robot_id) including Stripe IDs
  - Purpose: Robot catalog business logic
  - _Leverage: src/core/supabase.py_
  - _Requirements: 1_

- [x] 7.12. Implement CheckoutService create_checkout_session
  - File: `src/services/checkout_service.py` (create)
  - Implement create_checkout_session() that:
    - Gets robot with Stripe price ID
    - Creates pending order in database
    - Creates Stripe Checkout Session with mode='subscription'
    - Sets customer_creation='if_required' for guest checkout
    - Includes order_id and session_id in Stripe metadata
    - Updates order with stripe_checkout_session_id
    - Returns checkout URL and order ID
  - Purpose: Stripe checkout session creation
  - _Leverage: src/core/stripe.py, src/core/supabase.py, src/services/robot_catalog_service.py_
  - _Requirements: 3, 7_

- [x] 7.13. Implement CheckoutService webhook handlers
  - File: `src/services/checkout_service.py` (modify)
  - Implement verify_webhook_signature() using Stripe SDK
  - Implement handle_checkout_completed() that updates order:
    - status='completed'
    - stripe_customer_id from event
    - stripe_subscription_id from event
    - customer_email from event
    - completed_at=now()
  - Implement handle_checkout_expired() that sets status='cancelled'
  - Purpose: Stripe webhook processing
  - _Requirements: 4_

- [x] 7.14. Implement CheckoutService order methods
  - File: `src/services/checkout_service.py` (modify)
  - Implement get_order(order_id) returning single order
  - Implement get_orders_for_profile(profile_id) returning user's orders
  - Implement get_orders_for_session(session_id) returning session's orders
  - Implement transfer_orders_to_profile(session_id, profile_id) for session claim
  - Purpose: Order retrieval and management
  - _Requirements: 5, 7_

- [x] 7.15. Update SessionService for order transfer
  - File: `src/services/session_service.py` (modify)
  - Update claim_session() to call checkout_service.transfer_orders_to_profile()
  - Ensure orders are transferred along with discovery data
  - Purpose: Link orders to profile on session claim
  - _Leverage: src/services/checkout_service.py_
  - _Requirements: 7_

### Route Layer

- [x] 7.16. Create robot catalog routes
  - File: `src/api/routes/robots.py` (create)
  - Implement GET /robots returning all active robots
  - Implement GET /robots/{id} returning single robot
  - No authentication required (public endpoints)
  - Purpose: Robot catalog API endpoints
  - _Leverage: src/services/robot_catalog_service.py_
  - _Requirements: 1_

- [x] 7.17. Create checkout routes
  - File: `src/api/routes/checkout.py` (create)
  - Implement POST /checkout/session creating Stripe Checkout Session
  - Use dual auth dependency (get_current_user_or_session)
  - Extract profile_id or session_id from auth context
  - Return checkout URL for redirect
  - Purpose: Checkout API endpoint
  - _Leverage: src/api/deps.py, src/services/checkout_service.py_
  - _Requirements: 3_

- [x] 7.18. Create order routes
  - File: `src/api/routes/checkout.py` (modify)
  - Implement GET /orders listing user's orders
  - Implement GET /orders/{id} returning single order
  - Use dual auth dependency for access control
  - Verify profile_id or session_id matches order owner
  - Purpose: Order retrieval API endpoints
  - _Leverage: src/api/deps.py, src/services/checkout_service.py_
  - _Requirements: 5_

- [x] 7.19. Create webhook routes
  - File: `src/api/routes/webhooks.py` (create)
  - Implement POST /webhooks/stripe for Stripe webhooks
  - Read raw body for signature verification
  - Handle checkout.session.completed event
  - Handle checkout.session.expired event
  - Return 200 OK for all valid events (idempotent)
  - Purpose: Stripe webhook endpoint
  - _Leverage: src/services/checkout_service.py_
  - _Requirements: 4_

### Registration Layer

- [x] 7.20. Register robot and checkout routes
  - File: `src/main.py` (modify)
  - Import Stripe configuration and call configure_stripe()
  - Import and include robots router at /api/v1/robots
  - Import and include checkout router at /api/v1/checkout
  - Import and include orders router at /api/v1/orders
  - Import and include webhooks router at /api/v1/webhooks
  - Purpose: Enable new endpoints
  - _Requirements: 1, 3, 4, 5_

### Testing Layer

- [x] 7.21. Write unit tests for RobotCatalogService
  - File: `tests/unit/test_robot_catalog_service.py` (create)
  - Test list_robots returns active products
  - Test list_robots with active_only=False returns all
  - Test get_robot returns correct robot
  - Test get_robot returns None for invalid ID
  - Purpose: Verify robot catalog business logic
  - _Requirements: 1_

- [x] 7.22. Write unit tests for CheckoutService
  - File: `tests/unit/test_checkout_service.py` (create)
  - Test create_checkout_session creates order and calls Stripe
  - Test verify_webhook_signature rejects invalid signatures
  - Test handle_checkout_completed updates order correctly
  - Test handle_checkout_expired sets status to cancelled
  - Mock Stripe SDK for unit tests
  - Purpose: Verify checkout business logic
  - _Requirements: 3, 4_

- [x] 7.23. Write integration tests for robot endpoints
  - File: `tests/integration/test_robot_routes.py` (create)
  - Test GET /robots returns catalog
  - Test GET /robots/{id} returns single robot
  - Test GET /robots/{id} returns 404 for invalid ID
  - Purpose: Verify robot API works end-to-end
  - _Requirements: 1_

- [x] 7.24. Write integration tests for checkout endpoints
  - File: `tests/integration/test_checkout_routes.py` (create)
  - Test POST /checkout/session with authenticated user
  - Test POST /checkout/session with anonymous session
  - Test POST /checkout/session returns checkout URL
  - Use Stripe test mode for integration tests
  - Purpose: Verify checkout API works end-to-end
  - _Requirements: 3, 7_

- [x] 7.25. Write integration tests for order endpoints
  - File: `tests/integration/test_order_routes.py` (create)
  - Test GET /orders returns user's orders
  - Test GET /orders/{id} returns order for owner
  - Test GET /orders/{id} returns 403 for non-owner
  - Purpose: Verify order API works end-to-end
  - _Requirements: 5_

- [x] 7.26. Write webhook integration tests
  - File: `tests/integration/test_webhook_routes.py` (create)
  - Test POST /webhooks/stripe with valid signature
  - Test POST /webhooks/stripe rejects invalid signature
  - Test checkout.session.completed updates order
  - Use stripe-cli or mock signatures for testing
  - Purpose: Verify webhook handling
  - _Requirements: 4_

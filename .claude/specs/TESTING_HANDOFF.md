# Testing Handoff: Sessions, Discovery & Stripe Checkout

This document provides testing instructions for the new session management, discovery profile, and Stripe checkout functionality.

---

## Prerequisites

### Environment Setup
```bash
# Required environment variables (add to .env)
STRIPE_SECRET_KEY=sk_test_...        # Stripe test mode secret key
STRIPE_WEBHOOK_SECRET=whsec_...      # From Stripe CLI or dashboard
STRIPE_PUBLISHABLE_KEY=pk_test_...   # For frontend (optional)

# Session configuration (optional, defaults shown)
SESSION_COOKIE_NAME=autopilot_session
SESSION_COOKIE_MAX_AGE=2592000       # 30 days in seconds
SESSION_COOKIE_SECURE=false          # Set true in production
```

### Database Migrations
```bash
# Run migrations in order
supabase db push
# Or manually run:
# 005_create_sessions.sql
# 006_create_discovery_profiles.sql
# 007_create_robot_catalog.sql (includes seed data)
# 008_create_orders.sql
# 009_update_conversations.sql
```

### Stripe CLI (for webhook testing)
```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login and forward webhooks to local server
stripe login
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
```

---

## 1. Session Management

### Create Session
```bash
# Creates anonymous session and sets cookie
curl -X POST http://localhost:8000/api/v1/sessions \
  -c cookies.txt \
  -v

# Expected: 201 Created, autopilot_session cookie set
# Response: { "id": "uuid", "phase": "discovery", "current_question_index": 0, ... }
```

### Get Current Session
```bash
# Get session data using cookie
curl http://localhost:8000/api/v1/sessions/me \
  -b cookies.txt

# Expected: 200 OK with session data
# Error cases:
#   - No cookie: 404 Not Found
#   - Authenticated user: 400 Bad Request
```

### Update Session
```bash
# Update discovery progress
curl -X PUT http://localhost:8000/api/v1/sessions/me \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "phase": "roi",
    "current_question_index": 5,
    "answers": {
      "facility_size": {
        "questionId": 1,
        "key": "facility_size",
        "label": "Facility Size",
        "value": "50000",
        "group": "Facility"
      }
    },
    "roi_inputs": {
      "laborRate": 25.0,
      "utilization": 0.8,
      "maintenanceFactor": 0.1,
      "manualMonthlySpend": 5000,
      "manualMonthlyHours": 200
    }
  }'

# Expected: 200 OK with updated session
```

### Claim Session (after signup)
```bash
# Requires both JWT and session cookie
curl -X POST http://localhost:8000/api/v1/sessions/claim \
  -b cookies.txt \
  -H "Authorization: Bearer <jwt_token>"

# Expected: 200 OK
# Response: {
#   "message": "Session claimed successfully",
#   "discovery_profile_id": "uuid",
#   "conversation_transferred": true/false,
#   "orders_transferred": 0
# }
# Cookie should be cleared
```

### Test Scenarios
- [ ] Create session sets httpOnly cookie
- [ ] Session expires after 30 days
- [ ] Cannot claim already-claimed session
- [ ] Cannot claim expired session
- [ ] Claiming transfers conversation ownership
- [ ] Claiming transfers orders to profile

---

## 2. Discovery Profiles (Authenticated Users)

### Get Discovery Profile
```bash
curl http://localhost:8000/api/v1/discovery \
  -H "Authorization: Bearer <jwt_token>"

# Expected: 200 OK with discovery profile
# Creates profile if doesn't exist
```

### Update Discovery Profile
```bash
curl -X PUT http://localhost:8000/api/v1/discovery \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "phase": "greenlight",
    "selected_product_ids": ["robot-uuid-1", "robot-uuid-2"]
  }'

# Expected: 200 OK with updated profile
```

### Test Scenarios
- [ ] Unauthenticated requests return 401
- [ ] Profile auto-created on first access
- [ ] Data persists across requests
- [ ] Phase transitions: discovery → roi → greenlight

---

## 3. Robot Catalog

### List All Robots
```bash
curl http://localhost:8000/api/v1/robots

# Expected: 200 OK
# Response: {
#   "items": [
#     {
#       "id": "uuid",
#       "name": "Pudu CC1 Pro",
#       "category": "Floor Cleaner",
#       "monthlyLease": 1200.00,  # camelCase computed field
#       "monthly_lease": "1200.00",  # snake_case original
#       ...
#     }
#   ]
# }
```

### Get Single Robot
```bash
curl http://localhost:8000/api/v1/robots/{robot_id}

# Expected: 200 OK with robot data
# Error: 404 if not found
```

### Test Scenarios
- [ ] No authentication required (public endpoints)
- [ ] Only active robots returned by default
- [ ] Response includes both snake_case and camelCase fields
- [ ] Seed data contains 5 robots (Pudu CC1 Pro, Pudu MT1 Vac, MaxBattery Pro, FoodRunner V2, BudgetVac Mini)

---

## 4. Stripe Checkout

### Create Checkout Session (Anonymous)
```bash
curl -X POST http://localhost:8000/api/v1/checkout/session \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "<robot_uuid>",
    "success_url": "http://localhost:3000/success?session_id={CHECKOUT_SESSION_ID}",
    "cancel_url": "http://localhost:3000/cancel"
  }'

# Expected: 201 Created
# Response: {
#   "checkout_url": "https://checkout.stripe.com/...",
#   "order_id": "uuid",
#   "stripe_session_id": "cs_test_..."
# }
```

### Create Checkout Session (Authenticated)
```bash
curl -X POST http://localhost:8000/api/v1/checkout/session \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "<robot_uuid>",
    "success_url": "http://localhost:3000/success",
    "cancel_url": "http://localhost:3000/cancel",
    "customer_email": "user@example.com"
  }'
```

### Test Scenarios
- [ ] Checkout creates pending order in database
- [ ] Stripe session is mode: subscription
- [ ] Order metadata includes order_id and session_id
- [ ] Inactive product returns 400
- [ ] Non-existent product returns 400
- [ ] Invalid URLs return 422

---

## 5. Order Management

### List My Orders
```bash
# Anonymous (session cookie)
curl http://localhost:8000/api/v1/orders \
  -b cookies.txt

# Authenticated
curl http://localhost:8000/api/v1/orders \
  -H "Authorization: Bearer <jwt_token>"

# Expected: 200 OK
# Response: { "items": [...] }
```

### Get Single Order
```bash
curl http://localhost:8000/api/v1/orders/{order_id} \
  -b cookies.txt

# Expected: 200 OK if owner, 403 if not owner, 404 if not found
```

### Test Scenarios
- [ ] Users can only see their own orders
- [ ] Session users see session orders
- [ ] Authenticated users see profile orders
- [ ] Orders sorted by created_at desc

---

## 6. Stripe Webhooks

### Start Webhook Listener
```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
# Note the webhook signing secret (whsec_...)
```

### Trigger Test Events
```bash
# Trigger checkout completed
stripe trigger checkout.session.completed

# Trigger checkout expired
stripe trigger checkout.session.expired
```

### Manual Webhook Test
```bash
# The webhook endpoint expects raw body + signature header
curl -X POST http://localhost:8000/api/v1/webhooks/stripe \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: <signature>" \
  -d '{"type": "checkout.session.completed", ...}'
```

### Test Scenarios
- [ ] checkout.session.completed updates order to "completed"
- [ ] checkout.session.completed stores customer_id, subscription_id, email
- [ ] checkout.session.expired updates order to "cancelled"
- [ ] Invalid signature returns 400
- [ ] Missing signature header returns 400
- [ ] Unhandled events return 200 (idempotent)

---

## 7. End-to-End Flow Tests

### Anonymous User Journey
1. [ ] Land on site → GET /sessions/me creates session
2. [ ] Answer questions → PUT /sessions/me updates answers
3. [ ] View ROI → PUT /sessions/me saves roi_inputs
4. [ ] Select robot → PUT /sessions/me saves selected_product_ids
5. [ ] Checkout → POST /checkout/session creates order
6. [ ] Complete Stripe checkout
7. [ ] Webhook updates order status
8. [ ] Sign up (Supabase Auth)
9. [ ] Claim session → POST /sessions/claim transfers data

### Authenticated User Journey
1. [ ] Login (Supabase Auth)
2. [ ] GET /discovery creates/returns discovery profile
3. [ ] Answer questions → PUT /discovery updates
4. [ ] Checkout → POST /checkout/session with JWT
5. [ ] Complete Stripe checkout
6. [ ] GET /orders shows order with status "completed"

### Session Claim with Orders
1. [ ] Create session as anonymous
2. [ ] Complete checkout (order tied to session)
3. [ ] Sign up
4. [ ] Claim session
5. [ ] Verify: orders_transferred = 1
6. [ ] GET /orders with JWT shows the order

---

## 8. Database Verification

### Check Sessions Table
```sql
SELECT id, phase, current_question_index,
       claimed_by_profile_id, expires_at
FROM sessions
ORDER BY created_at DESC
LIMIT 10;
```

### Check Discovery Profiles
```sql
SELECT dp.id, dp.phase, p.email
FROM discovery_profiles dp
JOIN profiles p ON dp.profile_id = p.id
ORDER BY dp.created_at DESC;
```

### Check Robot Catalog
```sql
SELECT name, monthly_lease, active, stripe_product_id
FROM robot_catalog
ORDER BY name;
```

### Check Orders
```sql
SELECT id, status, profile_id, session_id,
       stripe_subscription_id, total_cents
FROM orders
ORDER BY created_at DESC;
```

---

## 9. Error Cases to Test

| Endpoint | Scenario | Expected |
|----------|----------|----------|
| GET /sessions/me | Authenticated user | 400 |
| PUT /sessions/me | Authenticated user | 400 |
| POST /sessions/claim | No session cookie | 400 |
| POST /sessions/claim | Already claimed | 400 |
| POST /sessions/claim | Expired session | 400 |
| GET /discovery | No JWT | 401 |
| POST /checkout/session | Inactive product | 400 |
| POST /checkout/session | Invalid product_id | 400 |
| GET /orders/{id} | Not owner | 403 |
| POST /webhooks/stripe | Invalid signature | 400 |
| POST /webhooks/stripe | Missing signature | 400 |

---

## 10. Running Automated Tests

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run specific test files
pytest tests/unit/test_session_service.py -v
pytest tests/unit/test_checkout_service.py -v
pytest tests/unit/test_robot_catalog_service.py -v
pytest tests/integration/test_session_routes.py -v
pytest tests/integration/test_checkout_routes.py -v
pytest tests/integration/test_robot_routes.py -v
pytest tests/integration/test_order_routes.py -v
pytest tests/integration/test_webhook_routes.py -v
```

---

## Notes

- Stripe test mode card: `4242 4242 4242 4242` (any future date, any CVC)
- Session cookie is httpOnly, cannot be read by JavaScript
- Webhook endpoint must receive raw body for signature verification
- All Stripe products must be pre-created in Stripe dashboard with matching IDs in robot_catalog table

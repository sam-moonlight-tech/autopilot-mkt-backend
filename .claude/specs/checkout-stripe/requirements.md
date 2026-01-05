# Requirements Document: Checkout & Stripe Integration

## Introduction

This specification defines the robot product catalog, Stripe subscription checkout flow, and order management system for the Autopilot backend. It enables users to browse robot products, initiate checkout via Stripe, and track their lease subscriptions.

## Alignment with Product Vision

Checkout and Stripe integration enables the Autopilot platform by providing:
- **Product Discovery**: Browse and compare robot cleaning solutions
- **Seamless Checkout**: Stripe-hosted checkout for secure payment processing
- **Subscription Management**: Monthly lease billing via Stripe subscriptions
- **Order Tracking**: Complete order history and status tracking
- **Guest Checkout**: Purchase without requiring account creation

## Requirements

### Requirement 1: Robot Product Catalog

**User Story:** As a user, I want to browse available robot products, so that I can see options and their specifications.

#### Acceptance Criteria

1. WHEN a user requests robot catalog (GET /robots) THEN the system SHALL return all active robots
2. WHEN robots are returned THEN the system SHALL include: name, category, bestFor, modes, surfaces, monthlyLease, purchasePrice, timeEfficiency, keyReasons, specs
3. WHEN a user requests a single robot (GET /robots/{id}) THEN the system SHALL return full product details
4. WHEN robots are listed THEN the system SHALL filter inactive products by default
5. WHEN robot data is returned THEN the system SHALL include Stripe price information for checkout

### Requirement 2: Stripe Product/Price Synchronization

**User Story:** As an administrator, I want robot products pre-created in Stripe, so that checkout sessions reference valid prices.

#### Acceptance Criteria

1. WHEN a robot is added to catalog THEN the system SHALL have corresponding Stripe Product and Price
2. WHEN robot_catalog is seeded THEN stripe_product_id and stripe_lease_price_id SHALL be stored
3. WHEN Stripe IDs are stored THEN they SHALL reference valid Stripe objects
4. WHEN prices are referenced THEN they SHALL be recurring monthly prices for subscription mode
5. WHEN products are deactivated THEN the system SHALL mark them inactive (not delete)

### Requirement 3: Checkout Session Creation

**User Story:** As a user, I want to start a checkout for a robot lease, so that I can complete my purchase.

#### Acceptance Criteria

1. WHEN a user initiates checkout (POST /checkout/session) THEN the system SHALL create a Stripe Checkout Session
2. WHEN checkout is created THEN the system SHALL use mode: 'subscription' for monthly lease
3. WHEN checkout is created THEN the system SHALL include product's stripe_lease_price_id
4. WHEN checkout is created THEN the system SHALL create a pending order record
5. WHEN checkout is created THEN the system SHALL set customer_creation: 'if_required' for guest checkout
6. WHEN checkout is created THEN the system SHALL include success_url and cancel_url
7. WHEN checkout is created THEN the system SHALL store order_id and session_id in Stripe metadata
8. WHEN checkout is created THEN the system SHALL return the Stripe checkout URL
9. IF user is authenticated THEN the system SHALL prefill customer email
10. IF user has session THEN the system SHALL link session_id to order

### Requirement 4: Checkout Webhook Handling

**User Story:** As a system, I want to process Stripe webhooks, so that orders are updated when payment completes.

#### Acceptance Criteria

1. WHEN Stripe sends checkout.session.completed THEN the system SHALL update order status to 'completed'
2. WHEN webhook is processed THEN the system SHALL store stripe_customer_id on order
3. WHEN webhook is processed THEN the system SHALL store stripe_subscription_id on order
4. WHEN webhook is processed THEN the system SHALL set completed_at timestamp
5. WHEN Stripe sends checkout.session.expired THEN the system SHALL update order status to 'cancelled'
6. WHEN processing webhooks THEN the system SHALL verify Stripe signature
7. IF signature is invalid THEN the system SHALL return 400 Bad Request
8. IF order not found THEN the system SHALL log error and return 200 (idempotent)

### Requirement 5: Order Management

**User Story:** As a user, I want to view my order status, so that I can track my purchase.

#### Acceptance Criteria

1. WHEN a user requests order (GET /orders/{id}) THEN the system SHALL return order details
2. WHEN order is returned THEN the system SHALL include status, line_items, total, customer_email
3. WHEN order is returned THEN the system SHALL include subscription_id for active leases
4. IF user is authenticated THEN the system SHALL verify profile_id matches order
5. IF user has session THEN the system SHALL verify session_id matches order
6. IF neither matches THEN the system SHALL return 403 Forbidden
7. WHEN listing user's orders (GET /orders) THEN the system SHALL return orders for profile or session

### Requirement 6: Order Data Model

**User Story:** As a developer, I want a comprehensive order model, so that all checkout data is tracked.

#### Acceptance Criteria

1. WHEN an order is created THEN the system SHALL store: id, profile_id (nullable), session_id (nullable), stripe_checkout_session_id, status, line_items, total_cents
2. WHEN order is stored THEN the system SHALL include: currency, customer_email, metadata
3. WHEN order status changes THEN the system SHALL update: status, stripe_customer_id, stripe_subscription_id, completed_at
4. WHEN order is stored THEN the system SHALL track timestamps (created_at, updated_at)
5. WHEN orders are queried THEN the system SHALL support filtering by status and date range

### Requirement 7: Guest Checkout Support

**User Story:** As an anonymous user, I want to complete checkout without signing up, so that I can purchase quickly.

#### Acceptance Criteria

1. WHEN an anonymous user initiates checkout THEN the system SHALL link order to session_id
2. WHEN guest checkout completes THEN the system SHALL capture customer email from Stripe
3. WHEN guest later signs up THEN their orders SHALL remain accessible via session claim
4. WHEN session is claimed THEN orders SHALL be linked to profile_id
5. WHEN order ownership changes THEN the system SHALL update profile_id on order

## Non-Functional Requirements

### Performance
- Robot catalog listing SHALL complete in under 100ms
- Checkout session creation SHALL complete in under 2 seconds
- Webhook processing SHALL complete in under 500ms

### Security
- Stripe webhook signature SHALL be verified on every request
- Stripe API keys SHALL be stored securely in environment
- Order access SHALL be restricted to owner (profile or session)
- Customer payment data SHALL never be stored (Stripe handles PCI compliance)

### Reliability
- Webhook processing SHALL be idempotent (same event can be processed multiple times safely)
- Order creation and Stripe session SHALL be transactional
- Failed webhooks SHALL be logged for manual review
- Stripe SDK SHALL use latest stable version with retry logic

### Scalability
- Orders table SHALL support millions of records with proper indexing
- Robot catalog SHALL be cached for frequent access
- Webhook endpoint SHALL handle burst traffic from Stripe

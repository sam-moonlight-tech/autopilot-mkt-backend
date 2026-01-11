-- Create orders table
-- Stores checkout orders linked to profiles or sessions

-- Create order_status enum
CREATE TYPE order_status AS ENUM ('pending', 'processing', 'completed', 'cancelled', 'refunded');

CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    -- Nullable to allow order creation before Stripe checkout session
    stripe_checkout_session_id VARCHAR(255) UNIQUE,
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    status order_status NOT NULL DEFAULT 'pending',
    line_items JSONB NOT NULL,
    total_cents INTEGER NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'usd',
    customer_email VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Ensure order has an owner (profile or session)
    CONSTRAINT chk_order_owner CHECK (profile_id IS NOT NULL OR session_id IS NOT NULL)
);

-- Create indexes for orders
CREATE INDEX IF NOT EXISTS idx_orders_profile_id ON orders(profile_id);
CREATE INDEX IF NOT EXISTS idx_orders_session_id ON orders(session_id);
CREATE INDEX IF NOT EXISTS idx_orders_stripe_checkout_session_id ON orders(stripe_checkout_session_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);

-- Enable Row Level Security
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own orders
CREATE POLICY "Users can view own orders"
    ON orders FOR SELECT
    USING (
        profile_id IN (
            SELECT id FROM profiles WHERE user_id = auth.uid()
        )
    );

-- Policy: Users can insert their own orders (with their profile_id)
CREATE POLICY "Users can insert own orders"
    ON orders FOR INSERT
    WITH CHECK (
        profile_id IS NOT NULL
        AND profile_id IN (
            SELECT id FROM profiles WHERE user_id = auth.uid()
        )
    );

-- Policy: Service role has full access to orders (with both USING and WITH CHECK)
CREATE POLICY "Service role full access to orders"
    ON orders FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Trigger for auto-updating updated_at
CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

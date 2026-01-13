-- Make stripe_checkout_session_id nullable to allow orders to be created
-- before Stripe checkout session is created. NULL values don't violate unique constraints.

ALTER TABLE orders 
    ALTER COLUMN stripe_checkout_session_id DROP NOT NULL;

-- Update any existing empty strings to NULL
UPDATE orders 
    SET stripe_checkout_session_id = NULL 
    WHERE stripe_checkout_session_id = '';




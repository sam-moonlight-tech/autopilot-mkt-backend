-- Add 'payment_pending' status to order_status enum for ACH delayed payments
ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'payment_pending' AFTER 'pending';

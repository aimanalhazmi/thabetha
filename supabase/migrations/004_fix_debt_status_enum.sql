-- Fix debt_status enum to include all required values

-- Add missing enum values
ALTER TYPE debt_status ADD VALUE IF NOT EXISTS 'pending_confirmation';
ALTER TYPE debt_status ADD VALUE IF NOT EXISTS 'edit_requested';
ALTER TYPE debt_status ADD VALUE IF NOT EXISTS 'rejected';
ALTER TYPE debt_status ADD VALUE IF NOT EXISTS 'overdue';
ALTER TYPE debt_status ADD VALUE IF NOT EXISTS 'payment_pending_confirmation';
ALTER TYPE debt_status ADD VALUE IF NOT EXISTS 'cancelled';

-- Update existing 'waiting_for_confirmation' to 'pending_confirmation' for consistency
UPDATE debts SET status = 'pending_confirmation' WHERE status = 'waiting_for_confirmation';

-- Update existing 'delay' to 'overdue' for consistency
UPDATE debts SET status = 'overdue' WHERE status = 'delay';

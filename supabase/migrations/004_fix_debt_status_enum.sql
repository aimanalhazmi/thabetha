-- Fix debt_status enum to include all required values

-- Add missing enum values
ALTER TYPE debt_status ADD VALUE IF NOT EXISTS 'pending_confirmation';
ALTER TYPE debt_status ADD VALUE IF NOT EXISTS 'edit_requested';
ALTER TYPE debt_status ADD VALUE IF NOT EXISTS 'rejected';
ALTER TYPE debt_status ADD VALUE IF NOT EXISTS 'overdue';
ALTER TYPE debt_status ADD VALUE IF NOT EXISTS 'payment_pending_confirmation';
ALTER TYPE debt_status ADD VALUE IF NOT EXISTS 'cancelled';

-- Update legacy enum labels (only if they still exist on this DB).
do $$
begin
  if exists (
    select 1 from pg_enum e join pg_type t on t.oid = e.enumtypid
    where t.typname = 'debt_status' and e.enumlabel = 'waiting_for_confirmation'
  ) then
    execute $sql$UPDATE debts SET status = 'pending_confirmation' WHERE status::text = 'waiting_for_confirmation'$sql$;
  end if;

  if exists (
    select 1 from pg_enum e join pg_type t on t.oid = e.enumtypid
    where t.typname = 'debt_status' and e.enumlabel = 'delay'
  ) then
    execute $sql$UPDATE debts SET status = 'overdue' WHERE status::text = 'delay'$sql$;
  end if;
end$$;

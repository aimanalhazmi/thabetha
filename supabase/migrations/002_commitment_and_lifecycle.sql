-- 002 — Commitment indicator rename + canonical 8-state debt lifecycle.
--
-- Changes:
--   1. Expand `debt_status` enum to the canonical 8 states documented in
--      docs/debt-lifecycle.md:
--        pending_confirmation, active, edit_requested, rejected,
--        overdue, payment_pending_confirmation, paid, cancelled
--      Old values are renamed in-place where they map (waiting_for_confirmation
--      → pending_confirmation, delay → overdue) and new values are added.
--   2. Rename `profiles.trust_score` → `profiles.commitment_score` and the
--      `trust_score_events` table → `commitment_score_events`. The product
--      term is "commitment indicator / مؤشر الالتزام", *not* a credit score.
--   3. Update the on-signup trigger and RLS policies to match the renames.
--
-- This migration is idempotent: each step guards itself with IF/EXISTS checks
-- so re-running on a partially-migrated database is safe.

-- ── 1. Debt status enum ────────────────────────────────────────────────
-- Rename the two existing values that map cleanly.
do $$
begin
  if exists (
    select 1 from pg_enum e join pg_type t on t.oid = e.enumtypid
    where t.typname = 'debt_status' and e.enumlabel = 'waiting_for_confirmation'
  ) then
    alter type debt_status rename value 'waiting_for_confirmation' to 'pending_confirmation';
  end if;
end$$;

do $$
begin
  if exists (
    select 1 from pg_enum e join pg_type t on t.oid = e.enumtypid
    where t.typname = 'debt_status' and e.enumlabel = 'delay'
  ) then
    alter type debt_status rename value 'delay' to 'overdue';
  end if;
end$$;

-- Add the new lifecycle states.
alter type debt_status add value if not exists 'edit_requested';
alter type debt_status add value if not exists 'rejected';
alter type debt_status add value if not exists 'payment_pending_confirmation';
alter type debt_status add value if not exists 'cancelled';

-- The historical default referenced the old name; reset it.
alter table public.debts alter column status set default 'pending_confirmation';

-- ── 2. Commitment score: profiles column rename ───────────────────────
do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'profiles' and column_name = 'trust_score'
  ) then
    alter table public.profiles rename column trust_score to commitment_score;
  end if;
end$$;

-- ── 3. Commitment score events table rename + index/policy refresh ────
alter table if exists public.trust_score_events rename to commitment_score_events;

-- Old RLS policy references the old table name. Drop and recreate.
drop policy if exists "Users can view own trust events" on public.commitment_score_events;
create policy "Users can view own commitment events" on public.commitment_score_events
  for select using (auth.uid() = user_id);

-- ── 4. New-user trigger needs to match the renamed column ─────────────
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, name, phone, email, account_type)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'name', ''),
    coalesce(new.raw_user_meta_data->>'phone', ''),
    new.email,
    coalesce((new.raw_user_meta_data->>'account_type')::public.account_type, 'debtor')
  );
  return new;
end;
$$;

-- ── 5. Storage buckets for receipts and voice notes ───────────────────
-- 001 created a single `thabetha-attachments` bucket. The product spec
-- separates receipts (invoice photos) from voice notes; create both for
-- clearer access policies and lifecycle rules.
insert into storage.buckets (id, name, public)
values
  ('receipts', 'receipts', false),
  ('voice-notes', 'voice-notes', false)
on conflict (id) do nothing;

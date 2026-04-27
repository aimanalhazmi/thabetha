-- 006 — Tighten debt lifecycle and add creditor-configured reminders.
--
-- Three changes:
--
--   1. The `rejected` debt status is removed from the lifecycle. The debtor
--      can no longer reject a debt outright; their only pushback path is
--      `edit_requested`, which the creditor approves or rejects (returning
--      the debt to `pending_confirmation` with new or original terms).
--      Existing rows in `rejected` are migrated to `cancelled`.
--
--   2. `debts.reminder_dates date[]` is added. The creditor configures a
--      list of reminder dates at debt creation; each date that passes
--      unpaid fires a one-time commitment-indicator penalty.
--
--   3. `commitment_score_events.reminder_date date` is added so the
--      missed-reminder events are uniquely identifiable per
--      `(debt_id, reminder_date)` for idempotency. A partial unique index
--      enforces the at-most-once rule.

-- ── 1. Remove `rejected` from debt_status enum ────────────────────────
do $$
begin
  if exists (
    select 1 from pg_enum e join pg_type t on t.oid = e.enumtypid
    where t.typname = 'debt_status' and e.enumlabel = 'rejected'
  ) then
    update public.debts set status = 'cancelled' where status = 'rejected';

    alter table public.debts alter column status drop default;
    alter type public.debt_status rename to debt_status_old;

    create type public.debt_status as enum (
      'pending_confirmation',
      'active',
      'edit_requested',
      'overdue',
      'payment_pending_confirmation',
      'paid',
      'cancelled'
    );

    alter table public.debts
      alter column status type public.debt_status
      using status::text::public.debt_status;

    alter table public.debts alter column status set default 'pending_confirmation';

    drop type public.debt_status_old;
  end if;
end$$;

-- ── 2. Reminder dates on debts ────────────────────────────────────────
alter table public.debts
  add column if not exists reminder_dates date[] not null default '{}'::date[];

-- ── 3. Reminder-date column on commitment_score_events + uniqueness ───
alter table public.commitment_score_events
  add column if not exists reminder_date date;

create unique index if not exists commitment_score_events_missed_reminder_uniq
  on public.commitment_score_events (debt_id, reminder_date)
  where reason = 'missed_reminder';

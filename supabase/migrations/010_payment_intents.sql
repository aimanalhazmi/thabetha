-- Migration 010: payment_intents table for Phase 7 payment-gateway settlement.
-- Tracks one charge attempt per online payment flow.

create table public.payment_intents (
  id            uuid primary key default gen_random_uuid(),
  debt_id       uuid not null references public.debts(id) on delete cascade,
  provider      text not null,                      -- 'tap' | 'mock'
  provider_ref  text,                               -- gateway transaction ID (null until returned)
  checkout_url  text,                               -- redirect URL for debtor
  status        text not null default 'pending',    -- pending | succeeded | failed | expired
  amount        numeric(12,2) not null,
  fee           numeric(12,2) not null default 0,
  created_at    timestamptz not null default now(),
  expires_at    timestamptz not null,               -- created_at + 30 min
  completed_at  timestamptz
);

create index on public.payment_intents (debt_id);
-- Partial unique: provider_ref is null until the gateway assigns one, then must be unique.
create unique index on public.payment_intents (provider_ref) where provider_ref is not null;

-- RLS: creditor and debtor of the linked debt may read their payment intents.
alter table public.payment_intents enable row level security;

create policy "payment_intents_select" on public.payment_intents
  for select using (
    exists (
      select 1 from public.debts d
      where d.id = payment_intents.debt_id
        and (d.creditor_id = auth.uid() or d.debtor_id = auth.uid())
    )
  );

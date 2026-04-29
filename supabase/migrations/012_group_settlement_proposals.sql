-- ── 012: Group Auto-Netting (UC9 Part 2) ───────────────────────────────────
-- Spec: specs/009-groups-auto-netting/
-- Phase 9 — adds settlement proposal tables, enums, RLS, and lifecycle support
-- so that a group's debts can be net-settled atomically with multi-party
-- confirmation.
--
-- Sub-steps applied below in order:
--   1. Enums: settlement_proposal_status, settlement_confirmation_status
--   2. Table: group_settlement_proposals (+ indexes incl. partial-unique)
--   3. Table: group_settlement_confirmations
--   4. RLS on both new tables (members-only select, scoped writes)
--   5. group_events.event_type CHECK widened with settlement lifecycle events
--   6. commitment_score_events: add proposal_id column + idempotency index
--      for the new reason 'settlement_neutral' (delta 0).

-- ── 1. Enums ─────────────────────────────────────────────────────────────
do $$
begin
  if not exists (select 1 from pg_type where typname = 'settlement_proposal_status') then
    create type public.settlement_proposal_status as enum (
      'open', 'rejected', 'expired', 'settlement_failed', 'settled'
    );
  end if;
  if not exists (select 1 from pg_type where typname = 'settlement_confirmation_status') then
    create type public.settlement_confirmation_status as enum (
      'pending', 'confirmed', 'rejected'
    );
  end if;
end $$;

-- ── 2. group_settlement_proposals ────────────────────────────────────────
create table if not exists public.group_settlement_proposals (
  id                uuid primary key default gen_random_uuid(),
  group_id          uuid not null references public.groups(id) on delete cascade,
  proposed_by       uuid not null references public.profiles(id) on delete restrict,
  currency          text not null,
  snapshot          jsonb not null,
  transfers         jsonb not null,
  status            public.settlement_proposal_status not null default 'open',
  failure_reason    text,
  created_at        timestamptz not null default now(),
  expires_at        timestamptz not null,
  resolved_at       timestamptz,
  reminder_sent_at  timestamptz
);

-- One open proposal per group, enforced at the DB layer.
create unique index if not exists one_open_proposal_per_group
  on public.group_settlement_proposals (group_id)
  where status = 'open';

create index if not exists ix_group_settlement_proposals_group_status_created
  on public.group_settlement_proposals (group_id, status, created_at desc);

-- ── 3. group_settlement_confirmations ────────────────────────────────────
create table if not exists public.group_settlement_confirmations (
  proposal_id   uuid not null references public.group_settlement_proposals(id) on delete cascade,
  user_id       uuid not null references public.profiles(id) on delete restrict,
  status        public.settlement_confirmation_status not null default 'pending',
  responded_at  timestamptz,
  primary key (proposal_id, user_id)
);

create index if not exists ix_group_settlement_confirmations_user_status
  on public.group_settlement_confirmations (user_id, status);

-- ── 4. RLS ───────────────────────────────────────────────────────────────
alter table public.group_settlement_proposals enable row level security;
alter table public.group_settlement_confirmations enable row level security;

-- Proposals: visible to all accepted members of the parent group; insertable
-- by accepted members (creation goes through the API so further validation
-- is in the handler/repo). Writes are gated additionally in handler code.
drop policy if exists gsp_select_members on public.group_settlement_proposals;
create policy gsp_select_members on public.group_settlement_proposals
  for select using (
    exists (
      select 1 from public.group_members gm
      where gm.group_id = group_settlement_proposals.group_id
        and gm.user_id = auth.uid()
        and gm.status = 'accepted'
    )
  );

drop policy if exists gsp_insert_members on public.group_settlement_proposals;
create policy gsp_insert_members on public.group_settlement_proposals
  for insert with check (
    exists (
      select 1 from public.group_members gm
      where gm.group_id = group_settlement_proposals.group_id
        and gm.user_id = auth.uid()
        and gm.status = 'accepted'
    )
  );

-- Confirmations: visible to all accepted members of the parent proposal's
-- group; updatable only by the row's own user (confirm/reject self).
drop policy if exists gsc_select_members on public.group_settlement_confirmations;
create policy gsc_select_members on public.group_settlement_confirmations
  for select using (
    exists (
      select 1
      from public.group_settlement_proposals p
      join public.group_members gm on gm.group_id = p.group_id
      where p.id = group_settlement_confirmations.proposal_id
        and gm.user_id = auth.uid()
        and gm.status = 'accepted'
    )
  );

drop policy if exists gsc_update_self on public.group_settlement_confirmations;
create policy gsc_update_self on public.group_settlement_confirmations
  for update using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- ── 5. group_events.event_type CHECK widening ────────────────────────────
-- Existing CHECK only covers Phase-8 group-lifecycle events. Drop and
-- recreate with the six new settlement lifecycle events appended.
alter table public.group_events
  drop constraint if exists group_events_event_type_check;

alter table public.group_events
  add constraint group_events_event_type_check
  check (event_type in (
    'created', 'renamed', 'member_invited', 'member_joined',
    'member_declined', 'member_left', 'invite_revoked',
    'ownership_transferred', 'deleted',
    -- Phase 9 — group settlement lifecycle
    'settlement_proposed', 'settlement_confirmed', 'settlement_rejected',
    'settlement_expired', 'settlement_settled', 'settlement_failed'
  ));

-- ── 6. commitment_score_events: settlement_neutral support ───────────────
-- The table uses a TEXT `reason` column. We add a nullable `proposal_id`
-- column (FK to the new proposals table) so we can record neutral
-- settlement events idempotently per (debt, proposal).
alter table public.commitment_score_events
  add column if not exists proposal_id uuid
    references public.group_settlement_proposals(id) on delete set null;

create unique index if not exists commitment_score_events_settlement_neutral_uniq
  on public.commitment_score_events (debt_id, proposal_id)
  where reason = 'settlement_neutral';

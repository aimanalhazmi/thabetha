# Phase 1 — Data Model: Group Auto-Netting

**Feature**: `009-groups-auto-netting` · **Migration**: `012_group_settlement_proposals.sql`

## New enum

### `settlement_proposal_status`

```sql
create type public.settlement_proposal_status as enum (
  'open',
  'confirmed',
  'rejected',
  'expired',
  'settlement_failed',
  'settled'
);
```

Lifecycle:

```
                   ┌──────────────────► rejected   (any required party rejects)
                   │
                   ├──────────────────► expired    (lazy sweep, expires_at < now)
open ──────────────┤
                   ├──────────────────► settlement_failed (atomic settle raised)
                   │
                   └──► confirmed ────► settled    (atomic chain succeeds)
```

`confirmed` is a transient state held during the atomic settle transaction; on success it advances to `settled`, on failure to `settlement_failed`. Application code may collapse `confirmed → settled` and never expose `confirmed` externally.

## New tables

### `group_settlement_proposals`

```sql
create table public.group_settlement_proposals (
  id              uuid        primary key default gen_random_uuid(),
  group_id        uuid        not null references public.groups(id) on delete cascade,
  proposed_by     uuid        not null references public.profiles(id) on delete restrict,
  currency        text        not null,
  snapshot        jsonb       not null,        -- list of {debt_id, debtor_id, creditor_id, amount}
  transfers       jsonb       not null,        -- list of {payer_id, receiver_id, amount}
  status          public.settlement_proposal_status not null default 'open',
  failure_reason  text,                        -- populated only when status='settlement_failed'
  created_at      timestamptz not null default now(),
  expires_at      timestamptz not null,        -- created_at + 7 days
  resolved_at     timestamptz,                 -- set when leaving 'open'
  reminder_sent_at timestamptz                 -- set by lazy sweep within 24h of expiry
);

create unique index one_open_proposal_per_group
  on public.group_settlement_proposals (group_id)
  where status = 'open';

create index group_settlement_proposals_group_id_status_idx
  on public.group_settlement_proposals (group_id, status, created_at desc);
```

**Snapshot shape** (immutable per FR-003):

```json
[
  {"debt_id": "uuid", "debtor_id": "uuid", "creditor_id": "uuid", "amount": "100.00"},
  ...
]
```

**Transfers shape** (computed by `services/netting.py`):

```json
[
  {"payer_id": "uuid", "receiver_id": "uuid", "amount": "75.00"},
  ...
]
```

### `group_settlement_confirmations`

```sql
create type public.settlement_confirmation_status as enum (
  'pending',
  'confirmed',
  'rejected'
);

create table public.group_settlement_confirmations (
  proposal_id   uuid not null references public.group_settlement_proposals(id) on delete cascade,
  user_id       uuid not null references public.profiles(id) on delete restrict,
  status        public.settlement_confirmation_status not null default 'pending',
  responded_at  timestamptz,
  primary key (proposal_id, user_id)
);

create index group_settlement_confirmations_user_idx
  on public.group_settlement_confirmations (user_id, status);
```

The roster is materialised at proposal-creation time: one row per distinct user appearing in `transfers[*].payer_id ∪ transfers[*].receiver_id`. Observers (zero-net members) get **no row**, which is the authorisation signal — `confirm`/`reject` looks up `(proposal_id, user_id)` and returns 403 on miss.

## Schema deltas (`backend/app/schemas/domain.py`)

New / extended Pydantic shapes:

```python
class SettlementProposalStatus(StrEnum):
    open = "open"
    rejected = "rejected"
    expired = "expired"
    settlement_failed = "settlement_failed"
    settled = "settled"


class SettlementConfirmationStatus(StrEnum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"


class ProposedTransferOut(BaseModel):
    payer_id: str
    receiver_id: str
    amount: Decimal


class SnapshotDebtOut(BaseModel):
    debt_id: str
    debtor_id: str
    creditor_id: str
    amount: Decimal


class SettlementConfirmationOut(BaseModel):
    user_id: str
    status: SettlementConfirmationStatus
    responded_at: datetime | None = None


class SettlementProposalCreate(BaseModel):
    """Empty body — group_id is in the path. Server snapshots and computes."""
    pass


class SettlementProposalOut(BaseModel):
    id: str
    group_id: str
    proposed_by: str
    currency: str
    transfers: list[ProposedTransferOut]
    snapshot: list[SnapshotDebtOut] | None = None  # None for observers (FR-007)
    confirmations: list[SettlementConfirmationOut]
    status: SettlementProposalStatus
    failure_reason: str | None = None
    created_at: datetime
    expires_at: datetime
    resolved_at: datetime | None = None


class SettlementConfirmationIn(BaseModel):
    """Empty body — action is in the URL verb (`/confirm` or `/reject`)."""
    pass
```

`NotificationType` gains:

```python
settlement_proposed = "settlement_proposed"
settlement_reminder = "settlement_reminder"
settlement_confirmed = "settlement_confirmed"   # one party confirmed (informational)
settlement_rejected = "settlement_rejected"
settlement_settled = "settlement_settled"
settlement_failed = "settlement_failed"
settlement_expired = "settlement_expired"
```

## Validation rules (mapped to FRs)

| Rule | Source | Enforcement |
|---|---|---|
| Snapshot only contains debts where `group_id = parent` and `status ∈ {active, overdue}` | FR-003 | `repo.create_settlement_proposal` filter |
| Single-currency snapshot | FR-004 | Pre-insert check; raise 409 `MixedCurrency` |
| One open proposal per group | FR-005 | Partial-unique index; 409 `OpenProposalExists` |
| Required-party only confirms/rejects | FR-006 | Lookup in `group_settlement_confirmations`; 403 `NotARequiredParty` |
| Expired after 7 days | FR-008 | Lazy sweep on read |
| Reject voids proposal immediately | FR-009 | Status → `rejected`; no debt mutation |
| Atomic settle, fail-safe on error | FR-010 | One transaction; status → `settlement_failed` on rollback |
| Neutral commitment update | FR-011 | `commitment_score_events.event_type = 'settlement_neutral'`, delta 0 |
| Member in open transfer cannot leave | FR-013 | Existing `leave_group` checks for any `status='open'` proposal where user is in `transfers` → 409 `LeaveBlockedByOpenProposal` |
| Notifications mandatory at create + 24h-pre-expiry | FR-014 | Created in same transaction as proposal insert; reminder fired in lazy sweep, idempotent on `reminder_sent_at` |

## Per-debt state transitions during atomic settle

Per snapshotted debt, in order, in one transaction:

1. `active|overdue → payment_pending_confirmation` — insert `debt_events(event_type='marked_paid', actor_id=debtor, metadata={source:'group_settlement', proposal_id})`.
2. `payment_pending_confirmation → paid` — insert `debt_events(event_type='payment_confirmed', actor_id=creditor, metadata={source:'group_settlement', proposal_id})`.
3. Insert `commitment_score_events(debt_id, event_type='settlement_neutral', delta=0, metadata={proposal_id})` — idempotent on `(debt_id, proposal_id)`.

If any step raises (FK violation, RLS denial, optimistic lock conflict), the entire transaction rolls back and the proposal is updated to `status='settlement_failed'` with the exception class name in `failure_reason`.

## RLS policies (added in migration 012)

```sql
-- group_settlement_proposals
alter table public.group_settlement_proposals enable row level security;

create policy gsp_select_members
  on public.group_settlement_proposals for select
  using (exists (
    select 1 from public.group_members m
     where m.group_id = group_settlement_proposals.group_id
       and m.user_id = auth.uid()
       and m.status = 'accepted'
  ));

create policy gsp_insert_members
  on public.group_settlement_proposals for insert
  with check (exists (
    select 1 from public.group_members m
     where m.group_id = group_settlement_proposals.group_id
       and m.user_id = auth.uid()
       and m.status = 'accepted'
  ));

-- group_settlement_confirmations
alter table public.group_settlement_confirmations enable row level security;

create policy gsc_select_members
  on public.group_settlement_confirmations for select
  using (exists (
    select 1 from public.group_settlement_proposals p
     join public.group_members m on m.group_id = p.group_id
     where p.id = group_settlement_confirmations.proposal_id
       and m.user_id = auth.uid()
       and m.status = 'accepted'
  ));

create policy gsc_update_self
  on public.group_settlement_confirmations for update
  using (user_id = auth.uid());
```

The backend currently runs as the Postgres role and bypasses RLS at runtime — these policies are the **authoritative authorisation contract**, mirrored in handler code via `repo.get_authorized_proposal(user_id, ...)`.

## Audit-trail summary

| Event | Table | When |
|---|---|---|
| `settlement_proposed` | `group_events` | Proposal created |
| `settlement_confirmed` | `group_events` | Each individual confirmation (informational) |
| `settlement_rejected` | `group_events` | First reject (proposal voided) |
| `settlement_expired` | `group_events` | Lazy sweep marks expired |
| `settlement_settled` | `group_events` | All confirmations + atomic settle succeeded |
| `settlement_failed` | `group_events` | Atomic settle raised |
| `marked_paid` (per debt) | `debt_events` | Settle transaction, step 1 |
| `payment_confirmed` (per debt) | `debt_events` | Settle transaction, step 2 |
| `settlement_neutral` (per debt) | `commitment_score_events` | Settle transaction, step 3 |

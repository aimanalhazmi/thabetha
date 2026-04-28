# Data Model: Payment-Gateway Settlement

**Feature**: `007-payment-gateway-settlement` | **Date**: 2026-04-28

## New Table: `payment_intents`

Represents one gateway charge attempt for a debt.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `id` | uuid | NOT NULL | PK, gen_random_uuid() |
| `debt_id` | uuid | NOT NULL | FK → debts(id) ON DELETE CASCADE |
| `provider` | text | NOT NULL | `'tap'` \| `'mock'` |
| `provider_ref` | text | NULL | Gateway transaction ID; set after checkout creation; unique when non-null |
| `checkout_url` | text | NULL | Redirect URL for debtor; set after checkout creation |
| `status` | text | NOT NULL | `'pending'` \| `'succeeded'` \| `'failed'` \| `'expired'` |
| `amount` | numeric(12,2) | NOT NULL | Gross amount in SAR |
| `fee` | numeric(12,2) | NOT NULL | Provider fee in SAR (default 0 for mock) |
| `created_at` | timestamptz | NOT NULL | default now() |
| `expires_at` | timestamptz | NOT NULL | created_at + interval '30 minutes' |
| `completed_at` | timestamptz | NULL | Set on succeeded / failed / expired |

**Indexes**:
- `payment_intents_debt_id_idx` on `(debt_id)`
- `payment_intents_provider_ref_unique` UNIQUE on `(provider_ref)` WHERE `provider_ref IS NOT NULL`

**Constraint**: at most one `pending` intent per debt enforced in application logic (lazy expiry sweep + 409 guard).

**RLS**:
- Creditor and debtor of the linked debt can `SELECT`.
- Only the application service role can `INSERT` / `UPDATE` (no client-side writes).

---

## New `debt_events.event_type` Values

These extend the existing `debt_events` audit trail (no schema migration needed — `event_type` is free-text).

| Event Type | Actor | When Written |
|---|---|---|
| `payment_initiated` | debtor user_id | `POST /debts/{id}/pay-online` succeeds; intent created |
| `payment_failed` | `system` | Webhook delivers a failed/declined charge |
| `payment_expired` | `system` | Lazy sweep marks a pending intent as expired |
| `payment_confirmed` | `system` (gateway) OR creditor user_id (manual) | Webhook delivers succeeded charge OR `POST /debts/{id}/confirm-payment` |

`payment_confirmed` intentionally uses the same event type for both paths so queries and tests can assert equivalence without branching on the actor.

**`metadata` fields for payment events**:

```json
// payment_initiated
{"intent_id": "<uuid>", "provider": "tap", "amount": 100.00, "fee": 2.75}

// payment_failed / payment_expired
{"intent_id": "<uuid>", "provider_ref": "<tap_ref_or_null>"}

// payment_confirmed (gateway path)
{"intent_id": "<uuid>", "provider_ref": "<tap_ref>", "gateway": true}

// payment_confirmed (manual path — unchanged)
{}
```

---

## Modified Tables (no schema change, behavioural clarification)

### `debts`

No new columns. State machine gains one new traversal path:

```
active/overdue --[pay-online]--> payment_pending_confirmation --[webhook/manual]--> paid
```

Both transitions already exist; `pay-online` is a new route into `payment_pending_confirmation`, not a new state.

### `payment_confirmations` (existing)

Not used by the gateway path. Created only by `mark_paid` (manual "Mark as paid" button). Left unchanged.

---

## Entity Relationship (additions only)

```
debts (1) ──< payment_intents (N)
debts (1) ──< debt_events    (N)   [extended with new event types]
```

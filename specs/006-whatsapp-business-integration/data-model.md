# Phase 1 — Data Model: WhatsApp Delivery State

**Feature**: `006-whatsapp-business-integration`
**Date**: 2026-04-28

The feature adds **only columns** to the existing `notifications` table. No new tables are introduced. No existing rows are modified at migration time.

---

## Migration: `supabase/migrations/009_whatsapp_delivery.sql`

```sql
-- 009_whatsapp_delivery.sql
-- Phase 6: Real WhatsApp Business API integration (006-whatsapp-business-integration)
-- Adds delivery-state columns to notifications. Existing RLS unchanged.

ALTER TABLE notifications
    ADD COLUMN IF NOT EXISTS whatsapp_attempted boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS whatsapp_delivered boolean,
    ADD COLUMN IF NOT EXISTS whatsapp_provider_ref text,
    ADD COLUMN IF NOT EXISTS whatsapp_failed_reason text,
    ADD COLUMN IF NOT EXISTS whatsapp_status_received_at timestamptz;

-- Idempotency: webhook keys on provider_ref. Unique partial index allows nulls
-- (rows where the WhatsApp leg was never attempted) but enforces uniqueness for
-- rows that did get a provider id back.
CREATE UNIQUE INDEX IF NOT EXISTS notifications_whatsapp_provider_ref_key
    ON notifications (whatsapp_provider_ref)
    WHERE whatsapp_provider_ref IS NOT NULL;

-- Helpful for the webhook lookup path.
CREATE INDEX IF NOT EXISTS notifications_whatsapp_provider_ref_idx
    ON notifications (whatsapp_provider_ref);
```

**Rationale for nullability**:
- `whatsapp_attempted` is `NOT NULL DEFAULT false` — every notification has a definite attempted/not state.
- `whatsapp_delivered` is **nullable** to express tristate `unknown / true / false`. Per Clarification Q3, "unknown" persists indefinitely; we model it as `attempted=true AND delivered IS NULL AND failed_reason IS NULL`.
- `whatsapp_failed_reason` is nullable; populated only on terminal failure (either send-time exception or webhook `failed` status).
- `whatsapp_provider_ref` is nullable; populated when the provider returns a message id at send time.
- `whatsapp_status_received_at` is nullable; populated by the webhook on the first forward-status callback.

**Why no policy change**: existing `notifications` SELECT policy already restricts to creditor-or-debtor parties. The new columns are presentation-filtered in the handler (see Phase 0 R-6), not at the DB layer.

---

## Conceptual states (derived, not stored as enum column)

A small computed property `WhatsAppDeliveryStatus` lives in `backend/app/schemas/domain.py`:

| Status | Computed predicate |
|---|---|
| `not_attempted` | `whatsapp_attempted = false` |
| `attempted_unknown` | `whatsapp_attempted = true AND whatsapp_delivered IS NULL AND whatsapp_failed_reason IS NULL` |
| `delivered` | `whatsapp_delivered = true` |
| `failed` | `whatsapp_attempted = true AND (whatsapp_delivered = false OR whatsapp_failed_reason IS NOT NULL)` |

This enum is the single source of truth for the frontend badge and is mirrored manually in `frontend/src/lib/types.ts`.

---

## Touched entities

### `notifications` (extended)

| Column | Type | Notes |
|---|---|---|
| `id` | uuid | unchanged |
| `user_id` | uuid | unchanged — recipient |
| `actor_id` | uuid | unchanged — sender (for our debt-state notifications, this is the creditor for debtor-facing messages and the debtor for creditor-facing messages; both can act as "sender" of a notification) |
| `notification_type` | text/enum | unchanged |
| `payload` | jsonb | unchanged |
| `created_at` | timestamptz | unchanged |
| `read_at` | timestamptz | unchanged |
| `whatsapp_attempted` | boolean NOT NULL | **NEW** — `false` means no provider call was made |
| `whatsapp_delivered` | boolean | **NEW** — tristate (NULL = unknown/in-flight) |
| `whatsapp_provider_ref` | text | **NEW** — Meta's `messages[0].id`; webhook lookup key |
| `whatsapp_failed_reason` | text | **NEW** — short machine-friendly code (e.g. `recipient_blocked`, `invalid_phone`, `template_not_approved`, `provider_5xx`, `no_template`, `no_phone_number`) |
| `whatsapp_status_received_at` | timestamptz | **NEW** — first forward-status callback time |

### `profiles` (unchanged)

Existing `whatsapp_enabled boolean` is consulted at send time. No change.

### `merchant_notification_preferences` (unchanged)

Existing per-(creditor, debtor) `whatsapp_enabled boolean` is consulted at send time. No change.

---

## Validation rules

- **VR-1**: A row with `whatsapp_provider_ref IS NOT NULL` MUST have `whatsapp_attempted = true`. Enforced in dispatch code; not a DB constraint to keep the migration cheap.
- **VR-2**: The webhook only writes when `whatsapp_provider_ref` matches an existing row. Unknown refs are dropped (idempotent no-op per spec edge case).
- **VR-3**: Status downgrades are forbidden — if `whatsapp_delivered` is already `true`, a later `failed` callback is ignored. Implementation uses a `_status_rank` map (`sent < delivered < read`; `failed` is terminal but only applies if not already `delivered=true`).
- **VR-4**: `whatsapp_failed_reason` MUST be a member of the codebook above; the webhook handler maps Meta's structured error objects onto these codes via a small lookup table.

---

## State diagram (per notification)

```text
                +--------------------+
                |  not_attempted     |
                |  (created in-app)  |
                +---------+----------+
                          |
                          | dispatcher invoked
                          v
            +---------------------------+
            | global OR per-creditor    |   --no--> stays not_attempted
            | toggle ON?                |
            +---------------------------+
                          | yes
                          v
                +---------------------+
                |  provider call      |
                +----+-----------+----+
                     |           |
            success  |           |  exception
                     v           v
        +-----------------+  +----------------+
        | attempted_      |  | failed         |
        | unknown         |  | (failed_reason)|
        +--------+--------+  +----------------+
                 |
                 | webhook callback
                 v
        +--------+--------+
        |  delivered      | -- duplicate callback --> no-op
        +-----------------+
                 |
                 | failed callback (only if not yet delivered)
                 v
        +--------+--------+
        | failed          |
        +-----------------+
```

No background sweeper transitions `attempted_unknown → failed` (Q3, FR-017).

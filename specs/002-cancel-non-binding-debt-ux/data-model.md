# Phase 1 — Data Model: Cancel Non-Binding Debt UX

**Date**: 2026-04-28
**Feature**: 002-cancel-non-binding-debt-ux

This feature does **not** introduce, alter, or remove any persisted entity. The relevant entities below already exist; they are listed here for traceability.

## Entities (read-only references — no schema changes)

### Debt (existing, `debts` table)

Relevant fields for this feature:

| Field | Type | Notes |
|-------|------|-------|
| `id` | uuid | Primary key. |
| `creditor_id` | uuid → `profiles.id` | Affordance gating: the cancel button renders only when `viewer.id == creditor_id`. |
| `debtor_id` | uuid → `profiles.id` | Recipient of the `debt_cancelled` notification. |
| `status` | `DebtStatus` enum | Affordance gating: must be `pending_confirmation` or `edit_requested`. |

State transition (already defined in `docs/debt-lifecycle.md`):

```text
pending_confirmation ─┐
                      ├──(creditor cancels)──► cancelled
edit_requested      ──┘
```

All other source states return `409 Conflict` from `POST /debts/{id}/cancel`.

### Debt Event (existing, `debt_events` table)

Written by the backend on successful cancellation. Not consumed by the UI in this feature, but listed because FR-004 references the audit trail:

| Field | Type | Value on cancel |
|-------|------|-----------------|
| `event_type` | text | `cancelled` |
| `actor_id` | uuid | The creditor's id. |
| `message` | text | The optional cancel-message text from the dialog (empty string allowed). |
| `metadata` | jsonb | Standard envelope written by the existing repository code. |

### Notification (existing, `notifications` table)

Fired by the backend on successful cancellation. Consumed by the debtor's notification surface:

| Field | Type | Value on cancel |
|-------|------|-----------------|
| `type` | `NotificationType` enum | `debt_cancelled` |
| `recipient_id` | uuid | `debtor_id` of the cancelled debt. |
| `body` | text | Built from existing copy; includes the optional message when non-empty (existing behavior, unchanged). |

## Frontend-only state (transient, in-memory)

These are not persisted; they live in the React component tree for the lifetime of the dialog:

| State | Type | Purpose |
|-------|------|---------|
| `cancelDialogDebtId` | `string \| null` | The id of the debt whose cancel dialog is open. `null` when no dialog is open. Stored on `DebtsPage.tsx`. |
| `cancelMessage` | `string` (max 200 chars) | The textarea contents in the open dialog. Reset to `""` on each open. |
| `cancelSubmitting` | `boolean` | Disables the confirm button while the request is in flight. |
| `cancelError` | `string \| null` | Translated inline error to render inside the dialog (e.g., 409 from a concurrent state change). |

## Validation rules (frontend)

- `cancelMessage`: `length ≤ 200` (enforced by `maxLength={200}` on the textarea).
- Trim leading/trailing whitespace before sending.
- Submit is allowed regardless of message length (including 0); FR-005 specifies the message is optional.

## Out of scope

- No new enum values, columns, indexes, RLS policies, or migrations.
- No changes to `frontend/src/lib/types.ts`.

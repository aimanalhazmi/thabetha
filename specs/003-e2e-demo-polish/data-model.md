# Phase 1 — Data Model: End-to-End Demo Polish

**Date**: 2026-04-28
**Feature**: 003-e2e-demo-polish

This feature does **not** introduce, alter, or remove any persisted entity. The relevant entities below are existing and listed for traceability only.

## Entities (read-only references — no schema changes)

### Profile (existing, `profiles` table)

Touched by:
- The integration tests, which read `commitment_score` from the dashboard endpoint to assert the post-payment delta.
- The demo script's final step ("Verify commitment indicator").

Relevant fields (no changes):

| Field | Type | Used by this feature |
|-------|------|----------------------|
| `id` | uuid | Identity for `auth_headers(user_id)`. |
| `commitment_score` | int (0–100, default 50) | Asserted by tests; visible in demo step 10. |
| `account_type` | enum | Demo seeds `business` for the merchant; tests rely on default `personal` for the debtor. |

### Debt (existing, `debts` table)

The two integration tests walk a debt through the full lifecycle. No fields are added; no constraints changed.

Relevant transitions exercised:

```text
Happy path:
  pending_confirmation → active → payment_pending_confirmation → paid

Edit-request branch:
  pending_confirmation → edit_requested → pending_confirmation (new terms)
  → active → payment_pending_confirmation → paid
```

### Commitment-score event (existing, `commitment_score_events` table)

Written automatically by the existing repository code on `confirm-payment`. Tests do **not** assert event rows directly — they assert the resulting `commitment_score` on the dashboard, which is the user-visible contract.

## Frontend-only state (transient, in-memory)

These are not persisted; they live in the React component tree for the lifetime of the page.

| State | Location | Purpose |
|-------|----------|---------|
| Per-action `submitting` flag | `DebtsPage.tsx`, `DashboardPage.tsx`, `NotificationsPage.tsx`, `QRPage.tsx` | Disables transition buttons while a request is in flight (FR-004). One flag per concurrent action surface; for `runAction`-style helpers, an existing local in-flight tracker may be reused. |
| Per-page `error` message | Same four pages | Translated string produced by `humanizeError` (see contracts). Replaces the existing raw-`err.message` flow. |
| Per-page `loadingDashboard`, `loadingNotifications`, etc. | Each respective page | Drives the translated empty-state vs. content fork. Some already exist (e.g., `DashboardPage.tsx:19`); the polish ensures every empty/loading branch has a translated string. |

## Test-only data (in-memory repository)

The two new integration tests create their own debts via `client.post('/api/v1/debts', ...)`; they do not depend on `SEED_DEMO_DATA=true`. The `reset_repository` autouse fixture clears state between tests.

## Out of scope

- No new enum values, columns, indexes, RLS policies, or migrations.
- No changes to `frontend/src/lib/types.ts`.
- No changes to `backend/app/services/demo_data.py` (the existing seed is sufficient per research §R3).

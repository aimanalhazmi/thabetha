# Research: Payment-Gateway Settlement

**Feature**: `007-payment-gateway-settlement` | **Date**: 2026-04-28

## Decision 1 — Payment Provider

**Decision**: Tap (production), mock (dev/test). HyperPay remains the documented fallback.

**Rationale**: Tap offers first-class SAR support, a hosted checkout page that handles PCI scope out of the app, and a simple HMAC-SHA256 webhook model identical to the existing WhatsApp webhook pattern. The provider interface is designed to be swapped, so HyperPay can be slotted in without changing calling code.

**Alternatives considered**:
- HyperPay: More prevalent in MENA merchant integrations but more complex webhook verification and hosted-page lifecycle.
- Stripe: No direct SAR issuer support without currency conversion; SAMA registration complexity.

**Key Tap API calls**:
- Create checkout: `POST https://api.tap.company/v2/charges` with `amount`, `currency: "SAR"`, `redirect.url`, `reference.order` (our `payment_intent.id`).
- Response includes `transaction.url` — redirect the debtor here.
- Webhook delivery: `POST` to our endpoint with `X-Tap-Signature` (HMAC-SHA256 of raw body, keyed on `TAP_WEBHOOK_SECRET`).
- Webhook payload key fields: `id` (provider_ref), `status` (`CAPTURED` = succeeded, `DECLINED` / `FAILED` = failed), `amount`, `fee`.

**Mock provider**: Returns `{checkout_url: "http://localhost:5173/payment/mock-return?ref={intent_id}", provider_ref: "{uuid}"}`. The mock-return page immediately POSTs a fake succeeded webhook to itself for local dev convenience.

---

## Decision 2 — Intent Expiry Mechanism

**Decision**: Lazy sweep — no background scheduler. On each `POST /debts/{id}/pay-online` call, sweep any `pending` intents for that debt where `expires_at < now()` and mark them `expired`. Only then apply the one-pending-per-debt rule.

**Rationale**: Consistent with the existing `_refresh_overdue` lazy-sweep pattern in the repository. Avoids introducing a Celery task or cron job for a 30-minute TTL at MVP scale. The expiry is exact enough for the UX requirement (debtor waits up to 30 min before retrying).

**Alternatives considered**:
- Celery beat / APScheduler: Clean but adds infra dependency not present in the codebase.
- Postgres `pg_cron`: Available in Supabase but over-engineered for MVP.

---

## Decision 3 — Debt Transition Path

**Decision**: `pay-online` endpoint reuses the `mark_paid` state-transition pattern: `active/overdue → payment_pending_confirmation`. It additionally creates a `payment_intents` row. The webhook handler then reuses `confirm_payment` logic: `payment_pending_confirmation → paid`.

**Rationale**: Constitution §I mandates `payment_pending_confirmation → paid`; direct `active → paid` is forbidden. This design reuses both existing transition paths and keeps the gateway as an automated creditor-confirmation mechanism rather than a bypass. It also means the creditor's manual confirm path continues to work for the same state (`payment_pending_confirmation`), giving a graceful fallback if the webhook never arrives.

**What changes vs `mark_paid`**: `pay-online` does not create a `payment_confirmations` row (that's the manual-path record); instead it creates a `payment_intents` row. Both produce a `debt_events` row, but with different event types (`payment_initiated` vs `payment_requested`).

**Alternatives considered**:
- Atomic `active → paid` in one webhook step: Violates constitution §I. Rejected.
- New intermediate state `payment_gateway_pending`: Unnecessary new state, violates §II. Rejected.

---

## Decision 4 — Debt State After Failed / Expired Intent

**Decision**: Debt stays in `payment_pending_confirmation` after a failed or expired intent. No state revert to `active`. The debtor can retry (new intent created); the creditor can still manually confirm.

**Rationale**: Reverting `payment_pending_confirmation → active` would require a new reverse transition not in the canonical 7-state table, violating §II. The `payment_pending_confirmation` state already supports both retry (new intent) and manual fallback (creditor confirm), so no reversion is needed. This is functionally safe: the debtor has acknowledged the obligation; a failed card attempt doesn't un-acknowledge it.

---

## Decision 5 — Fee Calculation Timing

**Decision**: Fee is calculated server-side at `pay-online` call time using the provider's advertised rate (configurable env var `TAP_FEE_PERCENT`, default 2.75%). Stored in `payment_intents.fee`. Returned to frontend as `net_amount = amount - fee` in the `pay-online` response for display before redirect.

**Rationale**: Single source of truth; prevents frontend-calculated values diverging from what the gateway actually charges. The fee rate is an env var so it can be updated without code changes.

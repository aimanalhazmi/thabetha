# Implementation Plan: Payment-Gateway Settlement

**Branch**: `007-payment-gateway-settlement` | **Date**: 2026-04-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/007-payment-gateway-settlement/spec.md`

## Summary

Integrate a payment gateway (Tap, with mock for dev/test) so the `payment_pending_confirmation → paid` debt transition can be resolved automatically by a successful gateway charge. The debtor initiates online payment via a new `POST /debts/{id}/pay-online` endpoint, which transitions the debt to `payment_pending_confirmation` and creates a `payment_intents` record. The gateway then fires a webhook that auto-completes the `payment_pending_confirmation → paid` transition — identical in all audit and commitment-score effects to the existing manual creditor confirm path.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies**: FastAPI, psycopg3/Supabase Postgres (backend); React 19 + Vite (frontend)
**Storage**: Supabase Postgres — new `payment_intents` table; existing `debt_events`, `debts`, `notifications`
**Testing**: pytest + `FastAPI.TestClient` with `REPOSITORY_TYPE=memory`; frontend smoke tests
**Target Platform**: Linux server (backend), browser (frontend)
**Project Type**: Web service + SPA
**Performance Goals**: Webhook processed in < 500 ms; checkout redirect in < 2 s
**Constraints**: Constitution §I — no direct `active → paid` bypass; §II — only canonical transitions; `payment_pending_confirmation → paid` is the only gateway-triggered transition
**Scale/Scope**: MVP scale (hackathon); single SAR currency; no saved cards

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Rule | Status | Notes |
|---|---|---|
| §I Bilateral Confirmation | ✅ PASS | `pay-online` → `active/overdue → payment_pending_confirmation`; webhook → `payment_pending_confirmation → paid`. No `active → paid` bypass. Creditor's "confirmation" is the gateway receipt. |
| §II Canonical 7-State Lifecycle | ✅ PASS | No new states. Only existing transitions used: `mark_paid` path + `confirm_payment` path (automated). |
| §III Commitment Indicator | ✅ PASS | Same `_change_commitment_score` logic called by webhook handler as by `confirm_payment`. |
| §IV Per-User Data Isolation | ✅ PASS | `pay-online` enforces debtor-only via handler check. Webhook is HMAC-gated system endpoint, not user-scoped. |
| §V Arabic-First | ✅ PASS | FR-011 mandates bilingual strings; see i18n keys in Phase 1. |
| §VII Schemas Source of Truth | ✅ PASS | New event types (`payment_initiated`, `payment_failed`, `payment_expired`) documented; `payment_intents` in new migration only. |
| §VIII Audit Trail | ✅ PASS | FR-014: `payment_initiated`, `payment_failed`, `payment_expired` written to `debt_events`; gateway confirmation writes `payment_confirmed` (same event type as manual path). |

**No violations. No Complexity Tracking entries needed.**

## Project Structure

### Documentation (this feature)

```text
specs/007-payment-gateway-settlement/
├── plan.md              ← this file
├── research.md          ← Phase 0
├── data-model.md        ← Phase 1
├── contracts/
│   └── api.md           ← Phase 1
└── tasks.md             ← Phase 2 (/speckit-tasks)
```

### Source Code

```text
backend/app/
├── api/
│   ├── debts.py                    # new POST /{id}/pay-online + GET /{id}/payment-intent
│   └── webhooks_payments.py        # new POST /api/v1/webhooks/payments
├── services/
│   └── payments/
│       ├── __init__.py
│       ├── provider.py             # ABC: create_checkout, verify_signature, parse_event
│       ├── tap.py                  # Tap Cloud API implementation
│       └── mock.py                 # dev/test mock (returns canned checkout URL)
└── repositories/
    ├── base.py                     # new abstract methods: create_payment_intent,
    │                               #   get_payment_intent_by_ref, confirm_payment_gateway
    ├── memory.py                   # implement new methods + pay_online transition
    └── postgres.py                 # implement new methods + pay_online transition

supabase/migrations/
└── 010_payment_intents.sql         # new table + indexes

frontend/src/
├── pages/
│   ├── DebtsPage.tsx               # add "Pay online" button (debtor, active/overdue)
│   └── PaymentReturnPage.tsx       # new: post-payment polling + redirect
├── lib/
│   ├── api.ts                      # new payOnline(), getPaymentIntent() helpers
│   └── i18n.ts                     # new i18n keys (AR + EN)
└── App.tsx (or router file)        # add /payment/return route
```

---

## Phase 0: Research

See [research.md](./research.md) for full findings. Key decisions:

1. **Provider**: Tap (default), mock (dev/test). Environment-gated via `PAYMENT_PROVIDER=mock|tap`.
2. **Expiry mechanism**: Lazy sweep — on each `pay-online` call, mark expired intents before checking the one-pending-intent-per-debt rule. No background scheduler.
3. **Transition path**: `pay-online` reuses the `mark_paid` state-transition pattern (`active/overdue → payment_pending_confirmation`), then also creates the `payment_intents` row. Webhook handler reuses `confirm_payment` logic.
4. **Webhook signature**: HMAC-SHA256 over raw body using `TAP_WEBHOOK_SECRET`, verified the same way as WhatsApp (`webhooks_whatsapp.py::verify_whatsapp_signature`).

---

## Phase 1: Design & Contracts

### Key implementation steps

#### 1. Migration `010_payment_intents.sql`

New table `payment_intents`:

```sql
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
create unique index on public.payment_intents (provider_ref) where provider_ref is not null;
```

RLS: read allowed for creditor and debtor of the linked debt (mirrors `debts` RLS).

#### 2. Repository ABC additions (`base.py`)

```python
@abstractmethod
def create_payment_intent(self, debt_id: str, provider: str, amount: Decimal, fee: Decimal,
                           checkout_url: str, provider_ref: str | None, expires_at: datetime) -> PaymentIntentOut: ...

@abstractmethod
def create_payment_intent_and_transition(
    self, user_id: str, debt_id: str, checkout_url: str, provider_ref: str | None,
    provider: str, amount: Decimal, fee: Decimal, expires_at: datetime
) -> PayOnlineOut:
    """Debtor-only. Validates state, blocks on pending intent, creates intent record,
    transitions active/overdue → payment_pending_confirmation, writes debt_events row.
    Provider calls (create_checkout, calculate_fee) happen at the handler layer before calling this."""

@abstractmethod
def get_active_payment_intent(self, debt_id: str) -> PaymentIntentOut | None:
    """Returns the pending intent for a debt if one exists and has not expired; marks expired ones."""

@abstractmethod
def get_payment_intent_by_ref(self, provider_ref: str) -> PaymentIntentOut | None: ...

@abstractmethod
def update_payment_intent_status(self, intent_id: str, status: str, completed_at: datetime | None = None) -> None: ...

@abstractmethod
def confirm_payment_gateway(self, provider_ref: str) -> DebtOut:
    """Idempotent. Transitions payment_pending_confirmation → paid and writes debt_events/commitment_score.
    No-ops if debt already paid. Mirrors confirm_payment() logic exactly."""
```

#### 3. `POST /api/v1/debts/{id}/pay-online` handler

```
1. get_current_user (debtor-only: 403 if user is creditor)
2. get_authorized_debt → must be active or overdue (409 otherwise)
3. get_active_payment_intent → if pending intent exists, return 409 "payment_in_progress"
4. provider = get_payment_provider()
5. fee = provider.calculate_fee(debt.amount)
6. checkout = provider.create_checkout(debt, fee)  → {checkout_url, provider_ref}
7. intent = create_payment_intent(...)
8. transition debt: active/overdue → payment_pending_confirmation  (reuse mark_paid logic)
9. _add_event(debt_id, user_id, "payment_initiated", metadata={"intent_id": ..., "provider": ...})
10. return {checkout_url, payment_intent_id, net_amount: debt.amount - fee}
```

#### 4. `POST /api/v1/webhooks/payments` handler

Mirrors `webhooks_whatsapp.py` exactly:

```
1. raw = await request.body()
2. provider.verify_signature(raw, header) → 403 if invalid
3. event = provider.parse_webhook_event(raw)  → {provider_ref, status, fee}
4. repo.confirm_payment_gateway(event.provider_ref)  ← does everything atomically
5. return {received: true}
```

`confirm_payment_gateway` internal logic:

```
1. get_payment_intent_by_ref(provider_ref) → 200 no-op if intent already succeeded
2. if event.status == "succeeded":
   a. update_payment_intent_status(intent, "succeeded", completed_at=now)
   b. get debt (must be payment_pending_confirmation; if already paid → no-op)
   c. debt = debt.model_copy(status=paid, paid_at=now)
   d. _add_event(debt_id, actor_id="system", "payment_confirmed", metadata={gateway: true})
   e. _change_commitment_score(...)  ← identical to confirm_payment()
   f. _notify(debtor, payment_confirmed)
   g. _notify(creditor, payment_confirmed)
3. if event.status == "failed":
   a. update_payment_intent_status(intent, "failed", completed_at=now)
   b. _add_event(debt_id, actor_id="system", "payment_failed", metadata={provider_ref})
   c. _notify(debtor, payment_failed)
   d. DO NOT change debt state — debtor can retry (FR-013)
```

#### 5. Frontend changes

**`DebtsPage.tsx`** — add "Pay online" button alongside "Mark as paid":

```tsx
{!isCreditor && (debt.status === 'active' || debt.status === 'overdue') && (
  <>
    <button onClick={() => void handlePayOnline(debt.id)}>
      <CreditCard size={16} /><span>{tr('payOnline')}</span>
    </button>
    <button onClick={() => void handleMarkPaid(debt.id)}>
      <WalletCards size={16} /><span>{tr('markPaid')}</span>
    </button>
  </>
)}
```

`handlePayOnline` calls `POST /debts/{id}/pay-online`, receives `{checkout_url}`, sets `window.location.href = checkout_url`.

**New `PaymentReturnPage.tsx`** — route `/payment/return?debt_id=<id>`:
- Polls `GET /debts/{id}` every 3 s for up to 60 s
- If `status === 'paid'` → show success toast, redirect to dashboard
- If timeout → show "payment processing" banner, redirect to dashboard

#### 6. i18n keys (AR + EN)

| Key | EN | AR |
|---|---|---|
| `payOnline` | Pay Online | ادفع أونلاين |
| `creditorReceives` | Creditor receives: | المبلغ الذي سيستلمه الدائن: |
| `paymentProcessing` | Payment processing… | جاري معالجة الدفع… |
| `paymentInProgress` | A payment is already in progress. Try again in {n} minutes. | الدفع جارٍ بالفعل. حاول مرة أخرى خلال {n} دقيقة. |
| `paymentFailed` | Payment failed. Please try again. | فشل الدفع. حاول مرة أخرى. |
| `paymentSucceeded` | Payment successful! | تمت عملية الدفع بنجاح! |
| `gatewayUnavailable` | Payment service unavailable. Please try again later. | خدمة الدفع غير متاحة. حاول مرة أخرى لاحقاً. |

#### 7. Environment variables

| Variable | Values | Default |
|---|---|---|
| `PAYMENT_PROVIDER` | `mock` \| `tap` | `mock` |
| `TAP_SECRET_KEY` | Tap API secret key | — |
| `TAP_WEBHOOK_SECRET` | HMAC secret for webhook verification | — |
| `PAYMENT_REDIRECT_BASE_URL` | Base URL for Tap return redirect | `http://localhost:5173` |

### Tests

| Test | Type | Description |
|---|---|---|
| `test_pay_online_success` | Integration | Debtor initiates payment on `active` debt → `payment_pending_confirmation`, intent created |
| `test_pay_online_blocks_second_attempt` | Integration | Second `pay-online` on same debt while pending → 409 |
| `test_pay_online_allows_after_expiry` | Integration | `pay-online` allowed after pending intent expires |
| `test_webhook_succeeded_transitions_debt` | Integration | Valid webhook → debt `paid`, `debt_events` written, commitment score updated |
| `test_webhook_idempotent` | Integration | Same webhook delivered twice → one transition, one event |
| `test_webhook_invalid_signature` | Integration | Bad HMAC → 403, no state change |
| `test_failed_payment_debtor_can_retry` | Integration | Failed webhook → intent `failed`, debt stays `payment_pending_confirmation`, debtor can retry |
| `test_gateway_vs_manual_equivalence` | Integration | Both `confirm_payment` and gateway webhook produce identical `debt_events.event_type` and commitment-score delta |
| `test_pay_online_creditor_forbidden` | Integration | Creditor calling `pay-online` → 403 |
| `test_pay_online_wrong_state` | Integration | `pay-online` on `paid` debt → 409 |

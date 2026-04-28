# Tasks: Payment-Gateway Settlement

**Input**: Design documents from `specs/007-payment-gateway-settlement/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.md ✅

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no blocking dependencies)
- **[Story]**: Maps to user story from spec.md
- Exact file paths included in every task

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Service package skeleton and environment configuration needed by all stories.

- [x] T001 Create `backend/app/services/payments/` package: `__init__.py` (exports `get_payment_provider()`), empty `provider.py`, `mock.py`, `tap.py`
- [x] T002 [P] Add payment env vars to `backend/app/core/config.py`: `PAYMENT_PROVIDER` (default `"mock"`), `TAP_SECRET_KEY`, `TAP_WEBHOOK_SECRET`, `TAP_FEE_PERCENT` (default `2.75`), `PAYMENT_REDIRECT_BASE_URL` (default `"http://localhost:5173"`)
- [x] T003 [P] Add payment env var examples to root `.env.example`: `PAYMENT_PROVIDER=mock`, `TAP_SECRET_KEY=`, `TAP_WEBHOOK_SECRET=`, `TAP_FEE_PERCENT=2.75`, `PAYMENT_REDIRECT_BASE_URL=http://localhost:5173`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Migration, schemas, provider interface, mock provider, and repository abstract methods that ALL user story phases depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Create migration `supabase/migrations/010_payment_intents.sql`: `payment_intents` table (id, debt_id FK, provider, provider_ref nullable — no inline UNIQUE, checkout_url, status default `'pending'`, amount, fee default 0, created_at, expires_at, completed_at), index on `debt_id`, partial unique index on `(provider_ref) where provider_ref is not null`, RLS allowing creditor/debtor of linked debt to SELECT
- [x] T005 [P] Add Pydantic schemas to `backend/app/schemas/domain.py`: `PaymentIntentOut` (all table columns + computed `net_amount`), `PayOnlineOut` (payment_intent_id, checkout_url, amount, fee, net_amount, currency, expires_at), `WebhookPaymentEvent` (provider_ref, status, amount, fee), `CheckoutSession` (checkout_url, provider_ref, fee)
- [x] T006 [P] Define provider ABC in `backend/app/services/payments/provider.py`: abstract methods `create_checkout(debt_id, amount, currency, redirect_url, order_ref) -> CheckoutSession`, `verify_signature(raw_body, header) -> bool`, `parse_webhook_event(raw_body) -> WebhookPaymentEvent`, `calculate_fee(amount) -> Decimal`
- [x] T007 Implement mock provider in `backend/app/services/payments/mock.py`: `create_checkout` returns `CheckoutSession(checkout_url=f"{PAYMENT_REDIRECT_BASE_URL}/payment/mock-return?ref={order_ref}", provider_ref=str(uuid4()), fee=Decimal("0"))`, `verify_signature` always returns True in test mode, `calculate_fee` returns `Decimal("0")`, `parse_webhook_event` parses canned JSON
- [x] T008 Implement `get_payment_provider()` factory in `backend/app/services/payments/__init__.py`: reads `settings.PAYMENT_PROVIDER`, returns `MockPaymentProvider()` for `"mock"`, `TapPaymentProvider()` for `"tap"`, raises `ValueError` otherwise
- [x] T009 [P] Add abstract methods to `backend/app/repositories/base.py`: `create_payment_intent(...)`, `get_active_payment_intent(debt_id) -> PaymentIntentOut | None` (lazy-expires pending intents past `expires_at`, returns None if none pending), `get_payment_intent_by_ref(provider_ref) -> PaymentIntentOut | None`, `update_payment_intent_status(intent_id, status, completed_at=None)`, `confirm_payment_gateway(provider_ref) -> DebtOut`

**Checkpoint**: Foundation complete — user story implementation can now begin.

---

## Phase 3: User Story 3 — Webhook Auto-Confirms Payment (Priority: P1) 🎯

**Goal**: Backend webhook endpoint receives gateway callbacks, verifies signatures, transitions `payment_pending_confirmation → paid`, writes audit events and commitment score — identical to the manual path.

**Independent Test**: POST a mock-signed webhook payload with a known `provider_ref` → assert debt status = `paid`, one `payment_confirmed` event in `debt_events`, commitment score delta matches `confirm_payment` baseline.

- [x] T010 [US3] Implement `confirm_payment_gateway(provider_ref)` in `backend/app/repositories/memory.py`: find intent by ref (404 if missing), idempotency check (return debt as-is if intent already `succeeded`), transition `payment_pending_confirmation → paid` (reuse commitment-score logic from `confirm_payment`), set `paid_at`, update intent status to `succeeded`/`completed_at`, call `_add_event(debt_id, "system", "payment_confirmed", metadata={"intent_id":..., "provider_ref":..., "gateway": True})`, call `_change_commitment_score(...)`, notify debtor and creditor
- [x] T011 [US3] Implement failed-webhook path in `backend/app/repositories/memory.py`: when webhook `status != succeeded`, call `update_payment_intent_status(intent_id, "failed", now)`, call `_add_event(debt_id, "system", "payment_failed", metadata={...})`, do NOT change debt state (FR-013)
- [x] T012 [US3] Implement `confirm_payment_gateway()` and failed-webhook path in `backend/app/repositories/postgres.py`: same logic as memory repo, use `_add_event_raw()` and existing commitment-score SQL helpers within a single transaction
- [x] T013 [US3] Create `backend/app/api/webhooks_payments.py`: `POST /api/v1/webhooks/payments` — read raw body, call `provider.verify_signature(raw, header)` → 403 if invalid, parse event, call `repo.confirm_payment_gateway(event.provider_ref)` on success or failed path, return `WebhookReceiptOut(received=True, applied=1)` — mirror `webhooks_whatsapp.py` structure exactly
- [x] T014 [US3] Register `webhooks_payments` router in `backend/app/main.py` under `/api/v1`
- [x] T015 [US3] Write integration tests in `backend/tests/test_payment_webhook.py`: webhook success (debt → paid, event written), idempotent replay (SC-002: second delivery → no state change, no duplicate event), invalid signature → 403, failed webhook → intent failed, debt stays `payment_pending_confirmation`

**Checkpoint**: Webhook endpoint functional and tested independently with mock signed payloads.

---

## Phase 4: User Story 1 — Debtor Pays Debt Online (Priority: P1) 🎯

**Goal**: Backend `pay-online` endpoint accepts debtor requests, enforces the one-pending-intent rule, transitions `active/overdue → payment_pending_confirmation`, creates the payment intent, and returns a checkout URL.

**Independent Test**: `POST /debts/{id}/pay-online` as debtor on an `active` debt → response contains `checkout_url`, debt status = `payment_pending_confirmation`, `debt_events` has `payment_initiated`, second call returns 409.

- [x] T016 [US1] Implement `create_payment_intent_and_transition(user_id, debt_id, checkout_url, provider_ref, provider, amount, fee, expires_at)` in `backend/app/repositories/memory.py`: enforce debtor-only (403), enforce `active`/`overdue` state (409), call `get_active_payment_intent(debt_id)` — if pending intent found return 409 `"payment_in_progress"`, call `create_payment_intent(...)` with passed-in values, transition debt `active/overdue → payment_pending_confirmation` (mirror `mark_paid` state transition, no `payment_confirmations` row), call `_add_event(debt_id, user_id, "payment_initiated", metadata={"intent_id":..., "provider":..., "amount":..., "fee":...})`, return `PayOnlineOut`
- [x] T017 [US1] Implement `create_payment_intent_and_transition(...)` in `backend/app/repositories/postgres.py` with the same signature and logic as T016, ensuring state transition and intent creation are in a single transaction
- [x] T018 [US1] Add `POST /api/v1/debts/{debt_id}/pay-online` route to `backend/app/api/debts.py`: `get_current_user`, `get_repository`, call `provider = get_payment_provider()`, `fee = provider.calculate_fee(debt.amount)`, `checkout = provider.create_checkout(debt_id, debt.amount, "SAR", f"{PAYMENT_REDIRECT_BASE_URL}/payment/return?debt_id={debt_id}", str(uuid4()))`, `expires_at = utcnow() + timedelta(minutes=30)`, then delegate to `repo.create_payment_intent_and_transition(user.id, debt_id, checkout.checkout_url, checkout.provider_ref, provider_name, debt.amount, fee, expires_at)`, wrap provider errors as `HTTPException(503)`
- [x] T019 [US1] Add `GET /api/v1/debts/{debt_id}/payment-intent` route to `backend/app/api/debts.py`: `get_current_user`, `get_authorized_debt` (debtor or creditor), call `repo.get_active_payment_intent(debt_id)` → 404 if None, return `PaymentIntentOut`
- [x] T020 [US1] Write integration tests in `backend/tests/test_payment_online.py`: pay_online success (200, checkout_url present, debt = `payment_pending_confirmation`, assert `response.fee == mock_provider.calculate_fee(debt.amount)` and `response.net_amount == debt.amount - response.fee` per SC-004), creditor forbidden (403), wrong state (409 for `paid`), wrong state (409 for `payment_pending_confirmation`), pending-intent blocks second attempt (409, FR-012), expiry releases block (FR-012)

**Checkpoint**: Backend pay-online flow complete. Combined with Phase 3, full server-side payment flow is testable end-to-end using mock provider.

---

## Phase 5: User Story 1 + 2 — Pay Online Frontend + Fee Transparency (Priority: P1 / P2)

**Goal**: "Pay online" button visible on active/overdue debts; fee and net-amount breakdown shown before redirect; `PaymentReturnPage` polls and shows result.

**Independent Test**: In sandbox, debtor sees "Pay online" button on active debt, taps it, sees "Creditor receives: X SAR" net of fee, gets redirected to mock gateway URL, returns to `/payment/return` page that shows "Payment successful!" after polling resolves.

- [x] T021 [P] [US1] Add `payOnline(debtId)` and `getPaymentIntent(debtId)` API helper functions to `frontend/src/lib/api.ts`
- [x] T022 [P] [US1] Add all new i18n keys to `frontend/src/lib/i18n.ts` (both `ar` and `en` objects): `payOnline`, `creditorReceives`, `paymentProcessing`, `paymentInProgress`, `paymentFailed`, `paymentSucceeded`, `gatewayUnavailable`, `paymentPendingTitle`, `paymentPendingBody`
- [x] T023 [US1] Add "Pay online" button to debtor's debt-details view in `frontend/src/pages/DebtsPage.tsx`: visible only when `!isCreditor && (debt.status === 'active' || debt.status === 'overdue')`, calls `payOnline(debt.id)`, on success sets `window.location.href = checkout_url`, on 409 `payment_in_progress` shows translated `paymentInProgress` toast with minutes remaining, on 503 shows `gatewayUnavailable` toast
- [x] T024 [US2] Add fee breakdown display to the pay-online flow in `frontend/src/pages/DebtsPage.tsx`: after `payOnline()` resolves and before redirect, show a brief modal or inline callout with `gross amount`, `fee`, and `creditorReceives: net_amount SAR` from `PayOnlineOut`; redirect only after user sees this info (or auto-close after 2s)
- [x] T025 [US1] Create `frontend/src/pages/PaymentReturnPage.tsx`: reads `?debt_id=` query param, polls `GET /debts/{debt_id}` every 3 s for up to 60 s, shows spinner with `paymentProcessing` string, on `status === 'paid'` shows success toast `paymentSucceeded` and navigates to dashboard, on 60s timeout shows `paymentProcessing` banner and navigates to dashboard (debt will update when webhook arrives)
- [x] T026 [US1] Register `/payment/return` route in `frontend/src/App.tsx` (or the project's router config file), pointing to `PaymentReturnPage`

**Checkpoint**: Full debtor payment flow visible end-to-end in the browser with mock provider.

---

## Phase 6: User Story 4 — Manual Creditor Confirmation Equivalence (Priority: P2)

**Goal**: Automated tests prove the manual confirmation path and gateway webhook path produce identical outcomes (SC-003), and that a creditor cannot re-confirm a gateway-paid debt (US4 acceptance scenario 2).

**Independent Test**: Run `backend/tests/test_payment_equivalence.py` — all assertions pass.

- [x] T027 [US4] Write `backend/tests/test_payment_equivalence.py` — SC-003 equivalence test: settle one debt via `POST /debts/{id}/confirm-payment` and another via gateway webhook with identical timing → assert both produce `event_type = "payment_confirmed"`, identical `commitment_score` delta, both debts reach `paid` status
- [x] T028 [US4] Add test in `backend/tests/test_payment_equivalence.py` — US4 acceptance scenario 2: debt already `paid` via gateway webhook, creditor calls `POST /debts/{id}/confirm-payment` → assert 409

**Checkpoint**: Manual and gateway paths verified equivalent. SC-003 passes.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Tap provider implementation, edge-case tests, RTL validation.

- [x] T029 [P] Implement `backend/app/services/payments/tap.py`: `create_checkout` POSTs to `https://api.tap.company/v2/charges` with `amount`, `currency: "SAR"`, `redirect.url`, `reference.order`; returns `CheckoutSession(checkout_url=response["transaction"]["url"], provider_ref=response["id"], fee=calculate_fee(amount))`; `verify_signature` computes HMAC-SHA256 of raw body with `TAP_WEBHOOK_SECRET` and compares against `X-Tap-Signature` header using `hmac.compare_digest`; `parse_webhook_event` maps Tap `status` values (`CAPTURED` → `succeeded`, `DECLINED`/`FAILED`/`CANCELLED` → `failed`); `calculate_fee` returns `Decimal(str(round(float(amount) * settings.TAP_FEE_PERCENT / 100, 2)))`
- [x] T030 [P] Write intent-expiry test in `backend/tests/test_payment_online.py`: create a pending intent with `expires_at` in the past, call `pay-online` → lazy sweep marks it `expired`, new intent created successfully (FR-012 auto-release)
- [x] T031 [P] Write failed-payment retry test in `backend/tests/test_payment_webhook.py`: webhook with `status=failed` → intent `failed`, debt stays `payment_pending_confirmation`, second `pay-online` call succeeds and creates new intent (FR-013)
- [ ] T032 Verify Arabic (RTL) rendering: open `DebtsPage` and `PaymentReturnPage` in AR locale, confirm all new i18n strings display correctly, fee breakdown aligns right, no overflow
- [ ] T033 [P] Update `claude-handoff/api-endpoints.md` with new endpoints: `POST /debts/{id}/pay-online`, `GET /debts/{id}/payment-intent`, `POST /webhooks/payments`
- [ ] T034 [P] Update `claude-handoff/database-schema.md` with `payment_intents` table and new `debt_events` event types

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user story phases**
- **US3 / Webhook (Phase 3)**: Depends on Phase 2
- **US1 / Pay-Online Backend (Phase 4)**: Depends on Phase 2; integrates with Phase 3 (`confirm_payment_gateway`)
- **US1+2 / Frontend (Phase 5)**: Depends on Phase 4 (needs `pay-online` endpoint running)
- **US4 / Equivalence (Phase 6)**: Depends on Phase 3 + Phase 4 (needs both paths implemented)
- **Polish (Phase 7)**: Depends on all story phases

### User Story Dependencies

- **US3 (P1)**: Can start after Phase 2 — no dependency on US1
- **US1 (P1)**: Can start after Phase 2 — calls `confirm_payment_gateway` from US3 but US3 backend can be stubbed
- **US2 (P2)**: Embedded in US1 frontend tasks (T024) — no separate dependency
- **US4 (P2)**: Depends on US1 + US3 both complete

### Within Each Phase

- `[P]`-marked tasks operate on different files and can run concurrently
- Repository memory impl before postgres impl (memory is simpler, proves logic)
- Backend complete before frontend phase begins (Phase 4 before Phase 5)

### Parallel Opportunities

```bash
# Phase 1 — all three can run simultaneously:
T001  # service package skeleton
T002  # config.py env vars
T003  # .env.example

# Phase 2 — T005, T006, T009 in parallel after T004 starts:
T004  # migration (start first)
T005 T006 T009  # schemas, mock provider, repo ABC — parallel

# Phase 3 — T010/T011 in parallel then T012:
T010 T011  # memory repo succeeded + failed paths
T012  # postgres repo (after memory proven)
T013 T014  # webhook route + router registration

# Phase 5 — T021/T022 fully independent:
T021 T022  # api.ts helpers and i18n keys
```

---

## Implementation Strategy

### MVP First (US1 + US3 — both P1)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**critical blocker**)
3. Complete Phase 3: US3 Webhook backend
4. Complete Phase 4: US1 Pay-Online backend
5. **STOP and VALIDATE**: Run `backend/tests/test_payment_webhook.py` + `test_payment_online.py` with mock provider — all assertions pass
6. Complete Phase 5: Frontend
7. **DEMO**: Full debtor flow in browser with sandbox provider

### Incremental Delivery

1. Setup + Foundational → skeleton ready
2. US3 backend → webhook processes mock events ✓
3. US1 backend → `pay-online` endpoint ✓ (combined with US3 = testable server-side flow)
4. US1+2 frontend → debtor can pay in browser ✓ → **MVP**
5. US4 equivalence → SC-003 passes ✓
6. Polish + Tap provider → production-ready

---

## Notes

- `[P]` tasks = different files, no blocking dependencies on incomplete tasks
- `[Story]` label traces each task to a spec user story for `/speckit-analyze` coverage mapping
- Memory repo implementation must precede Postgres for each new method (memory proves logic cheaply)
- Constitution §I compliance: `pay-online` → `payment_pending_confirmation` (never direct `active → paid`)
- Constitution §VIII compliance: every payment state change writes a `debt_events` row
- Tap provider (T029) is polish — mock is sufficient for all tests; Tap needed only for staging smoke test

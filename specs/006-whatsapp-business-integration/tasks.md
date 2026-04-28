---

description: "Task list for 006-whatsapp-business-integration"
---

# Tasks: Real WhatsApp Business API Integration

**Input**: Design documents from `/specs/006-whatsapp-business-integration/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/whatsapp_provider.md ✅, contracts/webhook_meta.md ✅, quickstart.md ✅

**Tests**: Tests are required by the constitution (§12 — every new state transition or auth-affecting change ships with a `FastAPI.TestClient` test). Test tasks are included for every story that introduces new behaviour.

**Organization**: Tasks are grouped by user story. US1 + US2 are both P1 (US1 is the MVP slice — sending real messages; US2 layers preference enforcement on top). US3 is P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks).
- **[Story]**: User story this task belongs to (US1 / US2 / US3). Setup, Foundational, and Polish phases carry no story label.
- File paths are absolute-relative-to-repo-root and must match plan.md §Source Code.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the empty module + test directories. Everything else is foundational.

- [ ] T001 Create the WhatsApp service module skeleton: `backend/app/services/whatsapp/__init__.py` (empty), and ensure `backend/tests/services/whatsapp/__init__.py` and `backend/tests/api/` exist (create the directories if missing).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Database migration, configuration, the provider interface ABC, repository methods, and schemas. No user-story work can start until these land.

**⚠️ CRITICAL**: Phase 3 (US1) cannot begin until every Phase 2 task is complete.

- [ ] T002 Add migration `supabase/migrations/009_whatsapp_delivery.sql` adding `whatsapp_attempted boolean NOT NULL DEFAULT false`, `whatsapp_delivered boolean`, `whatsapp_provider_ref text`, `whatsapp_failed_reason text`, `whatsapp_status_received_at timestamptz` to `notifications`, plus the unique partial index `notifications_whatsapp_provider_ref_key` on `whatsapp_provider_ref WHERE NOT NULL` and the `notifications_whatsapp_provider_ref_idx` lookup index per `data-model.md`.
- [ ] T003 Extend `Settings` in `backend/app/core/config.py` with `whatsapp_phone_number_id: str | None = None`, `whatsapp_webhook_secret: str | None = None`, `whatsapp_verify_token: str | None = None` (the existing `whatsapp_provider`, `whatsapp_access_token`, `whatsapp_from_number` stay).
- [ ] T004 [P] Add `WhatsAppDeliveryStatus` (StrEnum: `not_attempted`, `attempted_unknown`, `delivered`, `failed`) and the new fields on the notification response models in `backend/app/schemas/domain.py`. Define **two** response shapes — `NotificationOut` (no delivery columns; debtor-facing) and `NotificationOutCreditor` (extends `NotificationOut` with `whatsapp_attempted`, `whatsapp_delivered`, `whatsapp_failed_reason`, `whatsapp_status: WhatsAppDeliveryStatus`).
- [ ] T005 [P] Mirror the new enum and the `NotificationOutCreditor` shape in `frontend/src/lib/types.ts`. Keep the debtor-facing `NotificationOut` unchanged.
- [ ] T006 Define the `WhatsAppProvider` ABC plus the dataclasses `SendOutcome`, `SendRequest`, `SendResult`, `StatusUpdate` in `backend/app/services/whatsapp/provider.py`, exactly matching the contract in `contracts/whatsapp_provider.md`.
- [ ] T007 Extend the `Repository` ABC in `backend/app/repositories/base.py` with `mark_whatsapp_attempted(notification_id, result: SendResult)` and `apply_whatsapp_status(update: StatusUpdate) -> bool` (returns True if a row was updated, False on unknown ref).
- [ ] T008 [P] Implement the two new repository methods on `InMemoryRepository` in `backend/app/repositories/memory.py` with forward-only state semantics (delivered=true is sticky; failed after delivered is no-op).
- [ ] T009 [P] Implement the two new repository methods on `PostgresRepository` in `backend/app/repositories/postgres.py` using the single-statement UPDATE shown in `contracts/webhook_meta.md` §Handler algorithm.
- [ ] T010 [P] Update `backend/tests/conftest.py` to force `WHATSAPP_PROVIDER=mock` (in addition to the existing `REPOSITORY_TYPE=memory`). Wire a `mock_whatsapp` autouse fixture that resets `MockWhatsAppProvider.calls` between tests.

**Checkpoint**: Foundation ready — US1, US2, and US3 may begin (US3 has a soft dependency on US1's `MockWhatsAppProvider` for the webhook test fixtures, but the webhook router itself is independent).

---

## Phase 3: User Story 1 — Real WhatsApp Delivery on Debt-State Events (Priority: P1) 🎯 MVP

**Goal**: When a debt-state notification fires, an actual WhatsApp message is sent to the recipient (in their preferred locale) via the configured provider, and the in-app notification fires regardless of whether the WhatsApp leg succeeds.

**Independent Test**: With `WHATSAPP_PROVIDER=cloud_api` in staging, walk a debt through `pending_confirmation → active → paid` between two real test accounts; each transition produces a real WhatsApp message on the debtor's / creditor's handset within 30 seconds (SC-001), and the underlying transitions never fail because of a provider error (SC-003). Locally, the same flow works against the mock provider with deterministic results.

### Tests for User Story 1 ⚠️

> Write these first; they MUST FAIL before T015–T017 land.

- [ ] T011 [P] [US1] Provider-contract tests in `backend/tests/services/whatsapp/test_provider_contract.py` exercising `MockWhatsAppProvider.send_template`, `verify_webhook_signature` (constant-time, prefix handling), and `parse_status_callback` shape. Cover `outcome=sent`, `outcome=blocked` (preprogrammed via `mock.set_next_outcome`), and `outcome=error`.
- [ ] T012 [P] [US1] Dispatch resilience test in `backend/tests/services/whatsapp/test_dispatch_resilience.py`: preprogram the mock to raise an exception, fire a debt transition that creates a notification, assert (a) the debt transition committed, (b) the notification row exists, (c) the notification has `whatsapp_attempted=true, whatsapp_failed_reason="provider_5xx"`. Verifies FR-005.
- [ ] T013 [P] [US1] Locale-fallback test in `backend/tests/services/whatsapp/test_templates_locale.py`: pin `profile.preferred_language="ar"`, drop the `ar` template for one notification type, assert the `en` template is selected; drop both, assert `failed_reason="no_template"`.

### Implementation for User Story 1

- [ ] T014 [P] [US1] Implement `MockWhatsAppProvider` in `backend/app/services/whatsapp/mock.py`. Move all current mock-send logic here (find any inlined mock-send code in `backend/app/api/notifications.py` or services). Expose `calls: list[SendRequest]` and `set_next_outcome(outcome, failed_reason=None)` for tests. `verify_webhook_signature` accepts a fixed dev secret. `parse_status_callback` mirrors the Cloud API shape so test fixtures are reusable.
- [ ] T015 [P] [US1] Implement `CloudAPIWhatsAppProvider` in `backend/app/services/whatsapp/cloud_api.py` using `httpx`. POST to `https://graph.facebook.com/v20.0/{settings.whatsapp_phone_number_id}/messages` with `Authorization: Bearer {settings.whatsapp_access_token}`. Map HTTP errors onto the `failed_reason` codebook in `contracts/whatsapp_provider.md`. Implement `verify_webhook_signature` with `hmac.compare_digest` over `sha256=<hex>` against `settings.whatsapp_webhook_secret`. Implement `parse_status_callback` walking `entry[].changes[].value.statuses[]` per `contracts/webhook_meta.md`.
- [ ] T016 [P] [US1] Build the template registry in `backend/app/services/whatsapp/templates.py`: `TEMPLATE_REGISTRY: dict[NotificationType, dict[Literal["ar","en"], TemplateBinding]]` covering every `NotificationType` listed in `research.md` §R-3, plus `pick_template(notification_type, preferred_locale) -> (template_id, locale, params_layout)` with the other-locale fallback rule.
- [ ] T017 [US1] Provider factory `get_provider()` in `backend/app/services/whatsapp/__init__.py` selecting `MockWhatsAppProvider` when `settings.whatsapp_provider == "mock"`, `CloudAPIWhatsAppProvider` when `"cloud_api"`. Memoise per process. (Depends on T014 + T015.)
- [ ] T018 [US1] Implement `dispatch_notification(notification, repo, provider)` in `backend/app/services/whatsapp/dispatch.py` per the algorithm in `contracts/whatsapp_provider.md` §Dispatcher contract — preference gate (US2 fills its body in T020), phone gate, template lookup with locale fallback, build params from notification payload, call provider in `try/except`, persist result via `repo.mark_whatsapp_attempted`. (Depends on T016 + T017 + T007.)
- [ ] T019 [US1] Wire `dispatch_notification` into the notification-creation path. Audit `backend/app/api/notifications.py` and `backend/app/api/debts.py` for every site that creates an in-app notification today (debt created, accepted, edit_requested, edit_approved, edit_rejected, payment_pending_confirmation, payment_confirmed, debt_cancelled, reminder_due) and insert a call to `dispatch_notification(notification)` immediately after the notification row is committed. The call MUST NOT be inside the transition's DB transaction.

**Checkpoint**: US1 is functional — sending real (or mocked) WhatsApp messages on every debt-lifecycle event, with `attempted` / `provider_ref` persisted on the notification row. US2 fills in the preference gate next; without it, sends go out unconditionally (acceptable for the MVP increment but not for ship).

---

## Phase 4: User Story 2 — Debtor Controls WhatsApp Contact Per Creditor (Priority: P1)

**Goal**: A debtor's global toggle and per-creditor opt-out are honoured by the dispatcher; when off, no provider call is made; in-app notifications still fire.

**Independent Test**: Two creditors A and B; debtor opts out of WhatsApp from A only; A's notification is suppressed at the provider boundary, B's is sent normally, and both are present in the debtor's in-app feed (acceptance scenarios in spec.md US2).

### Tests for User Story 2 ⚠️

- [ ] T020 [P] [US2] Preference tests in `backend/tests/services/whatsapp/test_dispatch_preferences.py` covering all four scenarios from spec.md US2:
    1. global ON, per-creditor A OFF → A suppressed, in-app row exists with `whatsapp_attempted=false`.
    2. global ON, per-creditor B unset → B sent, mock receives one call.
    3. global OFF → no creditor's messages sent regardless of per-creditor preferences.
    4. no preference recorded for a creditor → global preference governs (default opt-in unless globally disabled).
   Plus an additional case: T021's edge — recipient has no phone number → `whatsapp_attempted=true, whatsapp_failed_reason="no_phone_number"`.

### Implementation for User Story 2

- [ ] T021 [US2] Implement the preference gate at the top of `dispatch_notification` in `backend/app/services/whatsapp/dispatch.py`: read `recipient_profile.whatsapp_enabled`; if false → leave `whatsapp_attempted=false` and return. Otherwise, when the notification is sent from a creditor to a debtor, look up `merchant_notification_preferences` row for `(creditor_id, debtor_id)`; if found and `whatsapp_enabled=false` → leave `whatsapp_attempted=false` and return. Add structured logging line `[whatsapp.dispatch] suppressed reason=<global_off|per_creditor_opt_out> user=<id> creditor=<id>`.
- [ ] T022 [US2] Add a repository method `get_merchant_notification_preference(creditor_id, debtor_id) -> Preference | None` to `backend/app/repositories/base.py` if one does not already exist; implement on `memory.py` and `postgres.py`. (Skip if the existing `Repository` already exposes this — verify first by grepping for `merchant_notification_preferences` in the repo files.)

**Checkpoint**: US2 is functional. Combined with US1, the system is production-safe for outbound: opt-outs are enforced and in-app fallbacks always work. This is the minimum viable ship for Phase 6.

---

## Phase 5: User Story 3 — Operators / Creditors See Delivery Status (Priority: P2)

**Goal**: The sending creditor sees per-message delivery status (`attempted` / `delivered` / `failed (reason)`) on their notifications view. Inbound delivery callbacks from the provider are signature-verified and applied idempotently.

**Independent Test**: Send to a known-bad number — creditor's notifications view shows "failed: invalid phone" (translated). Send to a good number — creditor sees "attempted, status unknown" within 1s, then "delivered" within ~5s after Meta's webhook lands. Debtor sees neither badge (Q1).

### Tests for User Story 3 ⚠️

- [ ] T023 [P] [US3] Webhook handler tests in `backend/tests/api/test_webhooks_whatsapp.py` covering exactly the cases listed in `contracts/webhook_meta.md` §Tests required: `test_signature_valid_applies_status`, `test_signature_invalid_returns_403`, `test_signature_missing_returns_403`, `test_unknown_provider_ref_is_noop`, `test_duplicate_callback_idempotent`, `test_failed_after_delivered_is_noop`, `test_get_verification_handshake_ok_and_403`. Use `MockWhatsAppProvider`'s `verify_webhook_signature` plus a fixed dev secret to drive the signature path.
- [ ] T024 [P] [US3] Notification-response shape tests in `backend/tests/api/test_notifications_whatsapp_visibility.py`: as the creditor (sender), `GET /api/v1/notifications` returns rows including `whatsapp_attempted`, `whatsapp_delivered`, `whatsapp_failed_reason`, `whatsapp_status`. As the debtor (recipient), the same notification's `GET` response excludes those fields entirely. Verifies Q1 / FR-006.

### Implementation for User Story 3

- [ ] T025 [P] [US3] Add a `verify_whatsapp_signature(raw_body: bytes, signature_header: str) -> bool` helper in `backend/app/core/security.py` that delegates to the active provider (so the webhook router does not couple to a specific provider). Returns False on any error or empty header.
- [ ] T026 [US3] Implement the webhook router in `backend/app/api/webhooks_whatsapp.py`:
    - `POST /api/v1/webhooks/whatsapp`: read `await request.body()`, verify signature, parse JSON (400 on invalid), call `provider.parse_status_callback`, apply each `StatusUpdate` via `repo.apply_whatsapp_status`, return `{"received": true, "applied": <n>}`. Log INFO per applied callback, WARN on signature failure (never log the body), ERROR on DB failure.
    - `GET /api/v1/webhooks/whatsapp`: handle Meta's `hub.mode=subscribe&hub.verify_token=...&hub.challenge=...` handshake. Return `200` with the challenge as plain text iff `hub.verify_token == settings.whatsapp_verify_token`; else `403`.
   No Supabase JWT dependency on this router (it is third-party-callable).
- [ ] T027 [US3] Mount the webhook router in `backend/app/api/router.py` under `/api/v1`.
- [ ] T028 [US3] Update the notifications list/detail handlers in `backend/app/api/notifications.py` to project `NotificationOutCreditor` when `notification.actor_id == current_user.id` and the recipient's debt counterparty (i.e. the creditor side of the implicit (creditor, debtor) tuple) matches the caller; otherwise project `NotificationOut`. Add a derived `whatsapp_status` computed from the four columns per `data-model.md`.
- [ ] T029 [P] [US3] Create `frontend/src/components/WhatsAppDeliveryBadge.tsx` — a small presentational component that takes `{status: WhatsAppDeliveryStatus, failedReason?: string}` and renders a translated badge. Renders nothing for `not_attempted`. Uses i18n keys from T031.
- [ ] T030 [P] [US3] Render the badge from T029 in `frontend/src/pages/NotificationsPage.tsx` only when the notification carries delivery fields (i.e. when the response is `NotificationOutCreditor`). Do not show it for `NotificationOut`. Match the existing layout — the badge sits next to the notification timestamp.
- [ ] T031 [P] [US3] Add i18n strings (AR + EN) to `frontend/src/lib/i18n.ts`: `whatsapp_status_attempted`, `whatsapp_status_delivered`, `whatsapp_status_failed`, plus a `whatsapp_failed_reason_*` mapping for every code in the `failed_reason` codebook (`recipient_blocked`, `invalid_phone`, `template_not_approved`, `template_param_mismatch`, `provider_4xx`, `provider_5xx`, `network_error`, `no_template`, `no_phone_number`).

**Checkpoint**: US3 is functional — creditors see honest delivery state for every message they sent, debtors see nothing extra, and the webhook is signature-verified and idempotent.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T032 [P] Update `docs/spec-kit/api-endpoints.md` with the `POST /api/v1/webhooks/whatsapp` and `GET /api/v1/webhooks/whatsapp` rows (note: signature-auth, not Supabase JWT).
- [ ] T033 [P] Update `docs/spec-kit/database-schema.md` with the `notifications` delta from migration 009.
- [ ] T034 [P] Update `docs/spec-kit/use-cases.md` UC6 row from current status to ✅ once US1+US2 ship and to fully-shipped once US3 lands.
- [ ] T035 Update `docs/spec-kit/project-status.md` — move "Real WhatsApp" from "Out of MVP scope" to "Shipped" once US3 closes.
- [ ] T036 Run `quickstart.md` §Local development end-to-end with the mock provider and capture any frictions back into either `quickstart.md` or `tasks.md` follow-ups.
- [ ] T037 Re-run `uv run pytest -k whatsapp` and `uv run ruff check --fix backend/app/services/whatsapp backend/app/api/webhooks_whatsapp.py` and confirm green.

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1) → Foundational (Phase 2) → US1 (Phase 3) → US2 (Phase 4) → US3 (Phase 5) → Polish (Phase 6).
- US2 strictly depends on US1 because US2's preference gate sits *inside* `dispatch_notification` (T018). Although they're both P1, US1 ships the dispatch path that US2 then constrains.
- US3 depends on US1 for `MockWhatsAppProvider` (T014) being callable from webhook tests (T023); independent of US2.

### Within Each User Story

- Tests first (T011–T013, T020, T023–T024) → must FAIL before implementation lands.
- Models / contracts (T006) → providers (T014, T015) → registry (T016) → factory (T017) → dispatcher (T018) → wiring (T019).
- Webhook router (T026) depends on signature helper (T025) and provider parsing (T015 from US1).
- Frontend (T029, T030, T031) is independent of backend wiring within US3 once `NotificationOutCreditor` lands (T004 in Foundational).

### Parallel Opportunities

- Phase 2: T004 + T005 (Pydantic + TS mirror), T008 + T009 (memory + postgres repos), T010 (conftest) all parallel after T002 + T003 + T006 + T007 land.
- Phase 3: T011 + T012 + T013 (tests) parallel; T014 + T015 + T016 (providers + templates) parallel; T017 then T018 then T019 sequential.
- Phase 4: T020 (test) parallel with T022 (repo method) — but T021 must follow T018 from Phase 3.
- Phase 5: T023 + T024 (tests) parallel; T025 parallel with T026 (router needs T025); T029 + T030 + T031 (frontend) parallel.
- Phase 6: T032 + T033 + T034 parallel.

---

## Parallel Example: User Story 1

```bash
# Round 1 — write the failing tests in parallel:
Task: "Provider-contract tests in backend/tests/services/whatsapp/test_provider_contract.py"
Task: "Dispatch resilience test in backend/tests/services/whatsapp/test_dispatch_resilience.py"
Task: "Locale-fallback test in backend/tests/services/whatsapp/test_templates_locale.py"

# Round 2 — implement providers + registry in parallel:
Task: "MockWhatsAppProvider in backend/app/services/whatsapp/mock.py"
Task: "CloudAPIWhatsAppProvider in backend/app/services/whatsapp/cloud_api.py"
Task: "Template registry in backend/app/services/whatsapp/templates.py"

# Round 3 — sequential because they touch the same module / import each other:
Task: "Provider factory in backend/app/services/whatsapp/__init__.py"
Task: "Dispatcher in backend/app/services/whatsapp/dispatch.py"
Task: "Wire dispatch into notification-creation sites in backend/app/api/{notifications,debts}.py"
```

---

## Implementation Strategy

### MVP First (US1 + US2 — both P1)

1. Phase 1 + Phase 2 → foundation in place.
2. Phase 3 (US1) → real sends work, but unconditionally.
3. Phase 4 (US2) → preference gate added; **this is the minimum production-safe ship**.
4. **STOP & VALIDATE**: walk `quickstart.md` §Local development. Confirm acceptance signals 1 + 2 from spec.md.
5. Tag-and-deploy if staging looks good; US3 can follow as a P2 increment.

### Incremental Delivery

1. Phase 1+2 → no user-visible change yet.
2. + Phase 3 → real outbound works; debtors with global=on are reachable.
3. + Phase 4 → opt-outs respected (production-safe).
4. + Phase 5 → creditors see delivery state; webhooks complete the picture.
5. + Phase 6 → docs current, project-status updated, ruff clean.

### Parallel Team Strategy

After Phase 2:

- Dev A: US1 (T011–T019) — backend send path.
- Dev B: US3 backend (T023, T025, T026, T027, T028) — webhook + response shape. Can begin in parallel with Dev A once `NotificationOutCreditor` (T004) is merged.
- Dev C: US3 frontend (T029, T030, T031) — independent files.
- US2 (T020–T022) is small (~half a day) and best owned by whoever finishes US1 first.

---

## Notes

- [P] tasks touch different files and have no in-flight prerequisites.
- Constitution §IV: backend currently runs as the Postgres role and bypasses RLS at runtime — handler-level filtering in T028 is the only line of defence for Q1's "debtors don't see delivery columns" rule until Phase 10 lands. Document this in T028's PR description.
- Constitution §V: every new user-visible string MUST land in `frontend/src/lib/i18n.ts` for both AR and EN (T031). The lint rule from Phase 5 will flag any miss.
- Constitution §VII: schema enums MUST stay in lockstep — T004 (backend) and T005 (frontend) together.
- FR-016: there is no retry queue. If a single send fails, the notification stays `failed`; the user can manually re-trigger by repeating the underlying business action (e.g. resending an edit request).
- FR-017: there is no background sweeper. `attempted_unknown` lives forever absent a real callback; T029 must render this state as "attempted, awaiting confirmation" rather than "delivered".

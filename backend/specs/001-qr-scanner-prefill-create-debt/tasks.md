---

description: "Task list for QR-scanner pass-through to Create Debt"
---

# Tasks: QR-scanner pass-through to Create Debt

**Input**: Design documents from `/specs/001-qr-scanner-prefill-create-debt/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/frontend-routes.md, quickstart.md

**Tests**: One backend integration test is included because the constitution (§ Development Workflow & Quality Gates) requires a test for any change that touches the create-debt path. No frontend test harness exists in this repo today, so frontend verification is manual via `quickstart.md`.

**Organization**: Tasks are grouped by user story (US1 = QR happy path, US2 = error handling, US3 = manual-entry parity). US1 is the MVP slice.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete dependencies)
- **[Story]**: Which user story this task belongs to ([US1], [US2], [US3])
- File paths are absolute or repo-relative as appropriate

## Path Conventions

Web application (Option 2 in plan.md):
- Backend root: `backend/` (this is also `REPO_ROOT` for `/specify`)
- Frontend root: `frontend/`
- All paths below are relative to the repository root (`thabetha/`).

---

## Phase 1: Setup

**Purpose**: Confirm the existing surfaces this feature builds on are still where the plan says they are. No new dependencies, no project init.

- [x] T001 [P] Verify `backend/app/api/qr.py` still exposes `GET /qr/resolve/{token}` returning `ProfileOut` (line ~31). If the signature has changed since the plan was written, flag in PR before proceeding.
- [x] T002 [P] Verify `backend/app/schemas/domain.py` `DebtCreate` still has both `debtor_name: str` and `debtor_id: str | None` (around lines 120–122). No changes — this is a pre-flight read only.
- [x] T003 [P] Confirm the four new i18n keys are not already present in `frontend/src/lib/i18n.ts`: `qr_expired_ask_refresh`, `cannot_bill_self`, `clear_debtor`, `scanned_debtor_label`. If any exist with different copy, surface the conflict in the PR description.

---

## Phase 2: Foundational

**Purpose**: Shared scaffolding used by all three user stories. Must complete before US1 can ship.

**⚠️ CRITICAL**: No user-story work can begin until this phase is complete.

- [x] T004 Add the four new bilingual strings to `frontend/src/lib/i18n.ts` for both `ar` and `en` locales: `qr_expired_ask_refresh`, `cannot_bill_self`, `clear_debtor`, `scanned_debtor_label`. AR copy must use natural Arabic, not transliteration. Also add `create_debt_for_person` and `cancel` if missing (verify first per T003).
- [x] T005 Define the `debtorSource` state union and `Prefilled` type at the top of `frontend/src/pages/DebtsPage.tsx` (or a small adjacent type module if the page already isolates types). Mirror the shape in `specs/001-qr-scanner-prefill-create-debt/data-model.md`. No behavior change yet — types only, so subsequent tasks can reference them.
- [x] T005a Implement the shared `clear_debtor` handler in `frontend/src/pages/DebtsPage.tsx`: clear `prefilled`, set `debtorSource = 'manual'`, and remove `qr_token` from the URL via `navigate({ search: '' }, { replace: true })`. Used by US2's "Switch to manual entry" recovery and by US3's "clear / change debtor" link (per research.md R5, FR-005). Hoisted to foundational because both stories depend on it.

**Checkpoint**: i18n keys + form-state types + clear-debtor handler exist. US1, US2, US3 can now be implemented.

---

## Phase 3: User Story 1 — Creditor scans → prefilled Create Debt → submit (Priority: P1) 🎯 MVP

**Goal**: A creditor scans a debtor's QR, confirms on the scanner sheet, lands on a prefilled-and-locked Create Debt form, and submits a debt linked by `debtor_id`.

**Independent Test**: From the `quickstart.md` "Happy path" section — Browser A scans Browser B's QR, taps "Create debt for this person", fills amount + description, submits, and Browser B sees the new `pending_confirmation` debt attributed to A with the correct linkage.

### Tests for User Story 1

- [x] T006 [P] [US1] Create `backend/tests/test_create_debt_with_debtor_id.py`. Test must: spin up the in-memory repo, mint a QR token for demo user B (`POST /qr/current` or equivalent helper), resolve it as demo user A (`GET /qr/resolve/{token}`), `POST /debts` as A with both `debtor_id` (from the resolve) and `debtor_name`, then assert (a) the response carries `debtor_id`, (b) `GET /debts` as B returns the debt, (c) the debt is in `pending_confirmation`. Uses the standard `client` and `auth_headers` fixtures.

### Implementation for User Story 1

- [x] T007 [US1] In `frontend/src/pages/QRPage.tsx`, after a successful `GET /qr/resolve/{token}` from the camera read, render an in-page confirm overlay showing the resolved debtor's name, last-4 of phone, and commitment-indicator badge with two buttons: `create_debt_for_person` and `cancel`. "Cancel" closes the overlay; the camera stays live. (Per research.md R1.)
- [x] T008 [US1] On the overlay's confirm action, `navigate(\`/debts?qr_token=\${encodeURIComponent(token)}\`)` using React Router. Do not perform a second resolve here — the Create Debt screen will re-resolve on mount.
- [x] T009 [US1] In `frontend/src/pages/DebtsPage.tsx`, on the Create Debt route mount, parse `qr_token` from `useSearchParams()`. If absent → `debtorSource = 'manual'` (existing behavior). If present → set `debtorSource = 'qr-resolving'` and call `GET /qr/resolve/{token}`.
- [x] T010 [US1] On a successful resolve where `resolved.id !== currentUser.id`, set `debtorSource = 'qr-resolved'` and populate `prefilled = { debtor_id, debtor_name, phone_last4, commitment_score }`. Render the preview header (name + last-4 + commitment-indicator badge) above the form.
- [x] T011 [US1] In the same `DebtsPage.tsx` form, when `debtorSource === 'qr-resolved'`: render the debtor-name field as read-only, decorated with `scanned_debtor_label`, and render a visible `clear_debtor` link/button next to it. The remaining debt fields (amount, currency, description, due date, reminders) stay editable.
- [x] T012 [US1] On submit when `debtorSource === 'qr-resolved'`: re-call `GET /qr/resolve/{token}`. If it succeeds, post `DebtCreate` with both `debtor_id = prefilled.debtor_id` and `debtor_name = prefilled.debtor_name`. (Failure handling lives in US2 — for now, on any failure abort submit and surface a generic error so the form doesn't post stale identity.)
- [x] T013 [US1] After a successful `POST /debts` from the QR-prefilled path, navigate to the existing post-create destination using `replace: true` so the resulting URL no longer carries `qr_token`. This satisfies the client-side single-use guarantee (Q2 clarification, FR-012).
- [x] T014 [US1] While `debtorSource === 'qr-resolving'`, render a skeleton in place of the preview header and disable (do not hide) the debt fields and submit button. (Per research.md R2.)

**Checkpoint**: US1 fully functional. The `quickstart.md` happy path runs green and `pytest backend/tests/test_create_debt_with_debtor_id.py` passes.

---

## Phase 4: User Story 2 — QR errors handled gracefully (Priority: P2)

**Goal**: Expired tokens, self-scans, and unknown/network errors are all surfaced with translated messages, and the creditor's already-entered debt fields survive the error.

**Independent Test**: From `quickstart.md` "Error path 1" and "Error path 2" — type values into the form, expire/self-scan the token, observe the right banner, observe submit is hidden, observe amount + description are still in the form.

### Implementation for User Story 2

- [x] T015 [US2] In `frontend/src/pages/DebtsPage.tsx`, on a 404 / expired-token response from the mount-time or submit-time resolve, set `debtorSource = 'qr-expired'`. Replace the preview header with an error banner using the `qr_expired_ask_refresh` string and two actions: "Rescan" (navigate to `/qr`) and "Switch to manual entry" (calls the `clear_debtor` handler from T005a). Keep all other form values intact. (Per research.md R3, FR-006, SC-004.)
- [x] T016 [US2] On any other failure response (non-404 4xx, 5xx, network error) from the mount-time resolve, set `debtorSource = 'qr-error'`. Same banner shape as `qr-expired` but with a generic translated error and a "Retry" action that re-fires the resolve. Submit remains hidden. (Per FR-008.)
- [x] T017 [US2] When `debtorSource === 'qr-expired'` or `'qr-error'`, hide the submit button entirely (do not merely disable it) and ensure the user can still edit non-debtor fields so they can copy values out before recovering. This locks SC-004 in place.
- [x] T018 [US2] In `frontend/src/pages/DebtsPage.tsx`, after the mount-time resolve completes, compare `resolved.id` against the auth context's current user `id`. If equal, set `debtorSource = 'qr-self'`. Render the `cannot_bill_self` translated message in place of the preview header, and **hide** the submit button entirely (per research.md R4 and FR-007). The `clear_debtor` link remains visible.
- [x] T018a [US2] In `backend/app/api/debts.py`, in the existing `POST /debts` handler, reject the request with `409 cannot_bill_self` when `payload.debtor_id` equals the authenticated `user.id`. Mirrors the UI guard from T018 so the self-billing rule is enforced twice (constitution §IV). Extend `backend/tests/test_create_debt_with_debtor_id.py` (T006) with a negative case asserting the 409 when creditor and debtor ids match.
- [x] T019 [US2] Update the submit handler to short-circuit (no network call) when `debtorSource ∈ {'qr-resolving', 'qr-self', 'qr-expired', 'qr-error'}` — defense-in-depth so a stray Enter key cannot bypass the hidden submit affordance.

**Checkpoint**: US2 covered. The two error paths in `quickstart.md` run green; SC-003, SC-004, SC-005 verifiable manually.

---

## Phase 5: User Story 3 — Manual-entry parity (Priority: P3)

**Goal**: Visiting Create Debt without a QR token, or tapping "clear / change debtor" from a prefilled state, produces today's manual-entry behavior with no regression.

**Independent Test**: `quickstart.md` "Manual-path regression" — open `/debts/new` without a `qr_token`, confirm the form is editable as before and submission produces a debt without `debtor_id`. Plus: from a prefilled state, tap "clear / change debtor" and confirm the URL no longer has `qr_token` and the back button does not restore the prefilled state.

### Implementation for User Story 3

- [x] T020 [US3] Wire the `clear_debtor` handler from T005a to the visible "clear / change debtor" link rendered in US1 (T011). No new logic — purely the binding from the link's `onClick`.
- [x] T021 [US3] Verify the existing manual submission path remains unchanged: when `debtorSource === 'manual'`, the form posts `DebtCreate` with `debtor_name` only and no `debtor_id` (matching today's behavior, per FR-009). Add a code-level note (one-line comment) only if the conditional was non-obvious; otherwise leave clean.
- [x] T022 [US3] Render the `clear_debtor` link only when `debtorSource ∈ {'qr-resolved', 'qr-self', 'qr-expired', 'qr-error'}` — never in `manual` (where there's nothing to clear).

**Checkpoint**: US3 done. The manual-entry regression check from `quickstart.md` runs green.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T023 [P] Manually walk the entire `quickstart.md` (Setup → Happy path → Error path 1 → Error path 2 → Manual-path regression → Bilingual check) and paste the result as a checklist into the PR description.
- [x] T024 [P] Run `cd backend && uv run pytest` and confirm `test_create_debt_with_debtor_id.py` passes alongside the existing suite.
- [x] T025 [P] Run `cd backend && uv run ruff check --fix .` and `cd frontend && npm run typecheck && npm run build`. Fix any lint/type fallout from the new code.
- [ ] T026 RTL spot-check the new UI surfaces in Arabic locale: scanner confirm overlay, prefilled preview header, expired-token banner, self-scan message. Verify caret position on debt-input fields and that the preview header's last-4 phone digits read correctly in RTL context.
- [x] T027 Update `docs/spec-kit/project-status.md` (or the equivalent handoff doc the PR template references) to move the QR-scanner pass-through bullet from in-progress to shipped, and tick UC4 in `docs/use-cases.md` if it exists. (Per the implementation-plan Phase 2 PR checklist.)
- [ ] T028 [P] Time the scan→prefilled-form path on a healthy local Supabase: open DevTools Performance, perform a scan (or visit `/debts/new?qr_token=<live-token>` directly), and confirm the form is fully rendered with the preview header in under 1 second (SC-006). Paste the timing into the PR description. If above budget, profile the single mount-time `GET /qr/resolve/{token}` call before adding optimizations.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup, T001–T003)**: No dependencies. Pure read/verify; can start immediately.
- **Phase 2 (Foundational, T004–T005)**: Depends on Phase 1. Blocks every user story.
- **Phase 3 (US1, T006–T014)**: Depends on Phase 2. Delivers the MVP slice on its own.
- **Phase 4 (US2, T015–T019)**: Depends on Phase 2 + Phase 3 (US2 reuses the `clear_debtor` handler from US3 — see note below). Functionally testable independently.
- **Phase 5 (US3, T020–T022)**: Depends on Phase 2. Some of US2's "Switch to manual entry" actions point at US3's T020 handler — implement T020 before T015 if the two are not done in the same pass.
- **Phase 6 (Polish, T023–T027)**: Depends on whichever user stories are in scope for the PR.

### User Story Dependencies

- **US1 (P1)**: Independent of US2 and US3.
- **US2 (P2)**: Independent. Recovery action reuses the foundational `clear_debtor` handler (T005a).
- **US3 (P3)**: Independent. Mostly a no-regression check plus the `clear_debtor` handler.

### Within Each User Story

- For US1: T006 (test) can be written in parallel with T007–T014 (implementation). Test must pass before merge.
- Models / type definitions (T005) come before any code that consumes them.
- US1's T009–T011 share `DebtsPage.tsx` and must be sequenced (no [P]).

### Parallel Opportunities

- T001, T002, T003 — all read-only verifications, fully parallel.
- T004 (i18n) and T005 (types) touch different files and are parallel.
- T006 (backend test) is parallel with all US1 frontend tasks.
- T023, T024, T025 in Phase 6 are parallel.

---

## Parallel Example: Phase 1

```bash
# All three setup verifications can run in parallel:
Task: "Verify GET /qr/resolve/{token} signature in backend/app/api/qr.py"
Task: "Verify DebtCreate fields in backend/app/schemas/domain.py"
Task: "Verify i18n key absence in frontend/src/lib/i18n.ts"
```

## Parallel Example: User Story 1

```bash
# Backend test runs alongside frontend implementation:
Task: "Backend integration test in backend/tests/test_create_debt_with_debtor_id.py"
# Frontend tasks must be sequenced in DebtsPage.tsx but can interleave with QRPage.tsx:
Task: "QRPage.tsx confirm overlay (T007)"
# After T009 lands the URL parsing, T010+T011+T014 layer on top in DebtsPage.tsx.
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1 (T001–T003) — verify surfaces.
2. Phase 2 (T004–T005) — i18n + types.
3. Phase 3 (T006–T014) — happy path.
4. **STOP and VALIDATE**: run `quickstart.md` happy path + `test_create_debt_with_debtor_id.py`.
5. Ship as MVP if needed; otherwise continue.

### Incremental Delivery

1. MVP (US1) → demo-able.
2. Add US3's T020 handler → enables "Switch to manual entry" downstream.
3. Add US2 (T015–T019) → all error paths land.
4. Add US3 (T021–T022) → manual-entry parity verified.
5. Polish phase → ship.

### Single-PR Strategy (recommended for this phase size)

This feature is small enough (S in the implementation plan) that a single PR covering all three stories is reasonable. Order tasks: Phase 1 → Phase 2 → T020 (US3 handler) → Phase 3 (US1) → Phase 4 (US2) → remaining T021/T022 → Phase 6.

---

## Notes

- Tests are intentionally minimal: one backend integration test (constitution-mandated for create-debt path changes) plus a manual frontend walkthrough. No new frontend test harness in this phase.
- The QR token is read but never persisted — Principle IX preserved; client-side single-use via URL strip is additive.
- Every new user-visible string lands in `frontend/src/lib/i18n.ts` for both AR and EN — Principle V.
- No backend source change, no migration, no schema change. If a task tempts you to add one, stop and re-read the plan.

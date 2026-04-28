---

description: "Task list for the End-to-End Demo Polish feature"
---

# Tasks: End-to-End Demo Polish

**Input**: Design documents from `/specs/003-e2e-demo-polish/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/humanize-error.md ✅, quickstart.md ✅

**Tests**: This feature explicitly requires tests (US3, FR-007, FR-008). The two integration tests (`test_canonical_happy_path`, `test_edit_request_branch`) are part of the deliverable, not optional.

**Organization**: Tasks are grouped by user story. Foundational tasks (humanizeError helper + i18n keys) block US1 and US2's polish work and are intentionally placed in Phase 2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User-story label (US1, US2, US3, US4) for tasks inside a story phase
- All paths are repo-relative

## Path Conventions

Web app layout — `frontend/src/` and `backend/` at repo root, per plan.md → Project Structure.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm working environment. Near-zero work because this phase is a polish + tests + doc bundle on top of existing infrastructure.

- [x] T001 Confirm working tree is on branch `003-e2e-demo-polish`; `develop` rebased into the branch (run `git status && git branch --show-current`).
- [x] T002 Confirm prior phases' code is present: `frontend/src/components/CancelDebtDialog.tsx` (Phase 3), QR pass-through in `DebtsPage.tsx` (Phase 2), receipt uploader in `frontend/src/components/AttachmentUploader.tsx` (Phase 1). If any are missing, the demo flow won't work — investigate before proceeding.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ship the cross-cutting helper and i18n keys that US1 and US2 both depend on.

**⚠️ CRITICAL**: T003–T005 must be complete before any page-level polish work in US1/US2 begins.

- [x] T00X [P] Add 6 new i18n keys to `frontend/src/lib/i18n.ts` (both Arabic and English exactly as listed in `contracts/humanize-error.md` §"New i18n keys"): `errorGeneric`, `errorLoadDebts`, `errorLoadDashboard`, `errorLoadNotifications`, `errorTransitionStateChanged`, `errorTransitionForbidden`. Keep the existing key style (camelCase identifiers).
- [x] T00X [P] Create `frontend/src/lib/errors.ts` implementing the contract in `contracts/humanize-error.md`: export `ErrorContext` union type and `humanizeError(err, language, context?)` function that parses the `^(\d{3}):` shape from `apiRequest`-thrown Errors and returns `t(language, <mapped key>)`. Default to `errorGeneric` on any parse failure or unknown (status, context) pair. Never throw.
- [x] T00X [US3-prep] Create empty `backend/tests/test_e2e_demo_path.py` with the standard imports (`from datetime import date, timedelta`; `from fastapi.testclient import TestClient`; `from tests.conftest import auth_headers`). Will be filled in by US3.

**Checkpoint**: After T005, the helper is callable and the test file exists. US1, US2, US3, US4 can now proceed in any order.

---

## Phase 3: User Story 1 — Happy-path demo runs end-to-end without dev help (Priority: P1) 🎯 MVP

**Goal**: A new contributor walks the canonical happy path on local Supabase using only `docs/demo-script.md` and finishes without dev help, with no raw errors and no blank panels on the four target pages.

**Independent Test**: A contributor unfamiliar with the codebase executes `docs/demo-script.md` Steps 0–10 (skipping the optional Step 11) on local Supabase, finishes in under 5 min median, and reports zero off-script actions. The four target pages render translated empty-states and translated errors.

### Implementation for User Story 1

- [x] T00X [US1] In `frontend/src/pages/DebtsPage.tsx`, import `humanizeError` from `../lib/errors`. Replace every `setMessage(err instanceof Error ? err.message : '<English literal>')` with `setMessage(humanizeError(err, language, '<context>'))`. Use `'loadDebts'` for the GET-list catch, `'transition'` for `runAction` catches, `'generic'` (or omit context) elsewhere. Audit `runAction` itself (around line 391) and the load function (around line 188).
- [x] T00X [US1] In `frontend/src/pages/DebtsPage.tsx`, ensure every transition action button (accept, mark-paid, confirm-payment, edit-approve, edit-reject) is `disabled` while its `runAction` invocation is in flight. If `runAction` does not currently expose an in-flight flag, add a small per-debt-id `inFlightActions` set (or per-button `submitting` state) and gate `disabled` on it. Match the visual idiom from `AuthPage.tsx:175` (`{submitting ? '…' : tr('actionLabel')}`).
- [x] T00X [P] [US1] In `frontend/src/pages/DashboardPage.tsx`, replace the existing error catch block to use `humanizeError(err, language, 'loadDashboard')`. Confirm the existing `loading` empty-state already renders translated `tr('loading')`. Add a translated empty-state for any sub-panel (overdue, recent debts, debtors) that currently renders blank when its array is empty — pick or add an i18n key per panel as needed; collect any newly-added keys into the same PR.
- [x] T00X [P] [US1] In `frontend/src/pages/NotificationsPage.tsx`, replace the error catch block to use `humanizeError(err, language, 'loadNotifications')`. Add a translated empty-state ("No notifications yet" / equivalent AR) when the list is empty after load. Confirm any mark-as-read button has a loading state and uses `humanizeError` on failure.
- [x] T010 [P] [US1] In `frontend/src/pages/QRPage.tsx`, replace any error catch block to use `humanizeError(err, language, 'qrResolve')` (which maps 404/410 to the existing `qr_expired_ask_refresh` key). Confirm the scanner's idle/empty state has translated copy — if the scanner panel renders blank before a scan, add an instruction string ("Point camera at QR code" / equivalent AR) using a new i18n key collected for this PR.
- [x] T011 [US1] During the sweep above, capture **untranslated existing strings** found in the four target pages as a list of `path:line — "literal"` pairs. Store them in a scratch text file locally; this list goes into the PR description's "Phase 5 hand-off — untranslated strings" section per FR-010 and research §R8. Do **not** translate them now.
- [x] T012 [US1] Run `cd frontend && npm run typecheck`; resolve any TypeScript errors introduced by T006–T010.

**Checkpoint**: After T012, US1 is fully implementable. Manual verification per quickstart.md §A on the happy path.

---

## Phase 4: User Story 2 — Edit-request branch completes cleanly (Priority: P1)

**Goal**: The single in-scope branch (debtor → request edit → creditor approves with new terms → debtor accepts → rest of happy path) is as polished as US1.

**Independent Test**: Same setup as US1 but at script Step 7 the debtor clicks "Request edit" instead of "Accept". The branch completes in under 5 min median with the same polish guarantees.

> **Note**: With T006 + T007 from US1 in place, the polish work is **already** applied to the edit-request controls (they live in `DebtsPage.tsx` and use the same `runAction` helper). The tasks below are the targeted verification + any branch-specific copy.

### Implementation for User Story 2

- [ ] T013 [US2] Manually walk the edit-request flow in the running app: debtor enters the request-edit dialog → types reason + proposed amount → submits. Verify the submit button is disabled in flight (per T007) and any error renders via `humanizeError`. If a code path was missed in T007, fix it now in `frontend/src/pages/DebtsPage.tsx`.
- [ ] T014 [US2] In the creditor's edit-request review surface (the inline form on the debt card, around `DebtsPage.tsx:778`), confirm both the approve and reject buttons follow the disabled-while-submitting pattern. If either was missed in T007, fix it.
- [ ] T015 [US2] Verify the "creditor approved → debtor sees new terms" surface renders within 800 ms perceived latency on local Supabase (per FR-011); if the debtor's debt card does not refresh, confirm the existing `refresh()` is called after `runAction` for the approval.

**Checkpoint**: After T015, US2 is verified end-to-end. The branch path is demoable.

---

## Phase 5: User Story 3 — Canonical regression test (Priority: P1)

**Goal**: Two backend integration tests in `backend/tests/test_e2e_demo_path.py` walk the full happy path and the edit-request branch against `REPOSITORY_TYPE=memory`, asserting the exact status sequence and the final `commitment_score == 53` (50 base + 3 early payment).

**Independent Test**: `cd backend && uv run pytest tests/test_e2e_demo_path.py -v` runs both tests in under 5 seconds combined and both pass.

### Tests for User Story 3 (these *are* the deliverable)

- [x] T016 [US3] In `backend/tests/test_e2e_demo_path.py` (created in T005), implement `test_canonical_happy_path(client: TestClient) -> None`. The test:
  1. Creates two profiles via `client.get('/api/v1/profiles/me', headers=auth_headers(...))` for `creditor-demo` and `debtor-demo`.
  2. Creditor `POST /api/v1/debts` with `due_date = today + 2`, asserts `status == 'pending_confirmation'`.
  3. Debtor `POST /api/v1/debts/{id}/accept`, asserts `status == 'active'`.
  4. Debtor `POST /api/v1/debts/{id}/mark-paid` with a note, asserts `status == 'pending_creditor_confirmation'` (current canonical name; fall back to whatever `DebtStatus` enum currently uses for this state).
  5. Creditor `POST /api/v1/debts/{id}/confirm-payment`, asserts `status == 'paid'`.
  6. Asserts `client.get('/api/v1/dashboard/debtor', ...)['commitment_score'] == 53` (early-payment bonus).
- [x] T017 [US3] In the same file, implement `test_edit_request_branch(client: TestClient) -> None`. The test:
  1. Same profile setup as T016.
  2. Creditor creates a debt; assert `pending_confirmation`.
  3. Debtor `POST /api/v1/debts/{id}/edit-request` with a `message` + `requested_amount`, assert `status == 'edit_requested'`.
  4. Creditor `POST /api/v1/debts/{id}/edit-request/approve` with the requested terms, assert `status == 'pending_confirmation'` and the debt's `amount` reflects the approved value.
  5. Debtor accepts → mark-paid → creditor confirm-payment, asserting each transition.
  6. Asserts `commitment_score == 53` on the debtor's dashboard.
- [x] T018 [US3] Run `cd backend && uv run pytest tests/test_e2e_demo_path.py -v --durations=10`; confirm both tests pass and combined runtime is under 5 seconds. If runtime exceeds, drop unnecessary fixture overhead — do not weaken assertions.
- [x] T019 [US3] Run `cd backend && uv run pytest -q`; confirm the full suite is still green (allowing for the pre-existing `test_late_payment_penalty_doubles_per_missed_reminder` failure which is out of scope per quickstart.md "Backend regression check").

**Checkpoint**: After T019, the regression net is in place.

---

## Phase 6: User Story 4 — Self-serve demo script (Priority: P2)

**Goal**: `docs/demo-script.md` exists, has 8–12 numbered steps covering both the happy path and the edit-request branch, and a fresh contributor can complete it in under 5 minutes median.

**Independent Test**: Three contributors execute the script back-to-back; median time under 5 minutes; each finishes without skipping a step.

### Implementation for User Story 4

- [x] T020 [US4] Create `docs/demo-script.md` with the 11-step structure outlined in research §R7. Steps must be: prereqs check; (one-time) signup of two demo accounts via Inbucket; sign in as creditor; QR scan debtor; create debt with one receipt; sign in as debtor; accept (or request-edit + creditor-approve + accept for branch); mark paid; sign in as creditor; confirm payment; verify commitment indicator; (optional) Arabic re-test. Each step ≤ 2 sentences. Total document fits one printed page (~one A4).
- [x] T021 [US4] Cross-link the demo script: add a "How to demo" line in the project root `README.md` pointing to `docs/demo-script.md`, and reference it from `docs/local-development.md` ("after setup, see `docs/demo-script.md`"). Both edits are one line each.
- [ ] T022 [US4] Hand the demo script to one fresh tester (someone who hasn't run the app); have them execute it and time them. Note any rough edge they hit (off-script question, blocked step, raw error). If they finish in over 5 minutes or hit any rough edge, fold the fix into Phase 3/4 tasks before re-running.

**Checkpoint**: After T022, the script is validated by at least one fresh-eyes pass. Two more passes (per SC-001) happen post-merge by reviewers.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates, lint/typecheck final pass, and PR opening.

- [x] T023 [P] Run `cd frontend && npm run typecheck` and `cd frontend && npm run build`; confirm both pass with zero errors.
- [x] T024 [P] Run `cd backend && uv run ruff check .` and `cd backend && uv run pytest -q`; confirm ruff is clean and the only failure is the pre-existing `test_late_payment_penalty_doubles_per_missed_reminder` (which is not in scope).
- [x] T025 Update `claude-handoff/project-status.md` (or `docs/spec-kit/project-status.md` if that is the canonical location) — mark the "End-to-end demo path" entry as ✅ shipped.
- [x] T026 Compile the "Phase 5 hand-off — untranslated strings" inventory from T011 into the PR description. Format each entry as `frontend/src/pages/<file>:<line> — "<literal>"`.
- [ ] T027 Run the full quickstart.md verification (sections A through F) end-to-end; tick each section in the PR description.
- [ ] T028 Open PR titled `feat(uc1-uc6): end-to-end demo polish` against `develop`. Populate the per-phase deliverable checklist from `docs/spec-kit/implementation-plan.md` Phase 4 entry. Body must include: median demo timing from T022, the untranslated-strings inventory, the test runtime from T018.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. T003 and T004 are `[P]` (different files); T005 is independent.
- **User Stories**: All depend on Phase 2 completion.
  - **US1 (Phase 3)**: Independent. Largest implementation phase.
  - **US2 (Phase 4)**: Depends on US1's T006 + T007 (the helper sweep covers both happy path and branch in the same file).
  - **US3 (Phase 5)**: Depends only on T005. Can run in parallel with US1 and US2 (different file).
  - **US4 (Phase 6)**: Depends on US1 + US2 being implementable (the script references their UI). T020 itself is independent.
- **Polish (Phase 7)**: Depends on all stories complete.

### Within Each User Story

- **US1**: T006 → T007 (same file, sequential). T008, T009, T010 in parallel (different files). T011 runs alongside the sweep. T012 last.
- **US2**: T013 → T014 → T015 sequential (manual verification chain).
- **US3**: T016 + T017 in parallel (independent functions, same file — but write sequentially to avoid merge friction); T018 → T019 sequential.
- **US4**: T020 → T021 → T022 sequential.

### Parallel Opportunities

- Phase 2: T003 ∥ T004 ∥ T005.
- Phase 3: T008 ∥ T009 ∥ T010 after T006/T007 land.
- Phases 3 + 5 can be developed in parallel by two engineers (different file scopes: frontend vs backend test).
- Phase 7: T023 ∥ T024.

---

## Parallel Example: Phase 2 + Phase 3 entry

```bash
# After T001/T002, kick off the foundational trio in parallel:
Task: "T003 — add 6 i18n keys × AR + EN to frontend/src/lib/i18n.ts"
Task: "T004 — implement humanizeError in frontend/src/lib/errors.ts"
Task: "T005 — scaffold backend/tests/test_e2e_demo_path.py"

# Once T003 + T004 land, US1 page sweep can split:
Task: "T008 — DashboardPage.tsx polish"
Task: "T009 — NotificationsPage.tsx polish"
Task: "T010 — QRPage.tsx polish"
# (T006, T007 must complete first because they share DebtsPage.tsx with each other.)
```

---

## Implementation Strategy

### MVP scope

US1 alone (Phase 1 → Phase 2 → Phase 3) delivers the demoable happy path with translated errors + empty-states + loading indicators. Stop at T012 to ship a partial PR if needed; the demo script and edit-request polish can follow.

### Incremental delivery

1. Phases 1–2 → helper + keys ready.
2. Phase 3 → US1 demoable (happy path is polished).
3. Phase 4 → US2 demoable (edit-request branch polished — usually delivered in the same PR because it shares files).
4. Phase 5 → regression net in place; safe to merge.
5. Phase 6 → demo script published.
6. Phase 7 → PR open.

### Parallel team strategy

Two-engineer split is natural:

- **Engineer A**: Phases 2 + 3 + 4 (frontend polish).
- **Engineer B**: Phases 2 (T005) + 5 (backend tests) + 6 (demo script).

Reconvene at Phase 7 for typecheck + ruff + PR.

---

## Notes

- This phase introduces **no** new endpoints, schemas, migrations, or state transitions. All backend touches are tests; all frontend touches are surfacing existing behavior more cleanly.
- New strings must land in `frontend/src/lib/i18n.ts` for **both** Arabic and English (constitution §V).
- Untranslated **existing** strings discovered during the sweep go into the PR description, not into separate fixes.
- The existing `test_late_payment_penalty_doubles_per_missed_reminder` failure is **out of scope** — do not fix it as part of this phase.
- Stop at any phase checkpoint to validate against `quickstart.md`.
- The PR must tick the deliverable checklist in `docs/spec-kit/implementation-plan.md` Phase 4 entry.

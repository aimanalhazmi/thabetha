---

description: "Task list for the Cancel Non-Binding Debt UX feature"
---

# Tasks: Cancel Non-Binding Debt UX

**Input**: Design documents from `/specs/002-cancel-non-binding-debt-ux/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/cancel-debt-ui.md ✅

**Tests**: Constitution §12 requires a test for every new state transition. This feature introduces NO new transitions, but the spec asks to re-verify the existing backend transition tests and to close one small gap (empty-message cancel). Those targeted backend tests are included; no new frontend test harness is being introduced in this phase.

**Organization**: Tasks are grouped by user story. The MVP (and the demo path for this XS phase) is User Story 1 alone.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: User-story label (US1, US2, US3) for tasks inside a story phase
- All paths are repo-relative

## Path Conventions

Web app layout — `frontend/src/` and `backend/` at repo root, per plan.md → Project Structure.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: This phase has near-zero work because the feature is a UI surfacing on top of existing backend, schemas, and notification infrastructure.

- [x] T001 Confirm working tree is clean and on branch `002-cancel-non-binding-debt-ux` (run `git status`); pull latest `develop` and rebase if needed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Confirm the existing pieces this feature depends on are still in place. No code change required — read-only verification.

**⚠️ CRITICAL**: If any verification fails, file an issue and stop; the assumptions in plan.md are wrong.

- [x] T002 [P] Verify `POST /debts/{id}/cancel` exists and accepts `ActionMessageIn` in `backend/app/api/debts.py` (currently line 122).
- [x] T003 [P] Verify `repo.cancel_debt(user_id, debt_id, message)` exists on both `backend/app/repositories/memory.py` and `backend/app/repositories/postgres.py` and writes a `cancelled` row to `debt_events`.
- [x] T004 [P] Verify `NotificationType.debt_cancelled` is defined in `backend/app/schemas/domain.py` and is fired by the cancel code path.
- [x] T005 [P] Verify the existing creditor-side cancel button in `frontend/src/pages/DebtsPage.tsx` (currently around line 683) is the only entry point to cancel from the debts UI — confirm by grepping `frontend/src/` for `/cancel`.

**Checkpoint**: Foundation ready. User-story implementation can now begin.

---

## Phase 3: User Story 1 — Creditor cancels a debt awaiting debtor confirmation (Priority: P1) 🎯 MVP

**Goal**: A creditor can cancel a debt in `pending_confirmation` or `edit_requested` via a two-tap dialog, the debt transitions to `cancelled`, the debtor receives a `debt_cancelled` in-app notification, and the creditor remains on the debt details page with the new status visible.

**Independent Test**: Sign in as creditor → create debt → click "Cancel debt" → confirm in dialog → assert (a) debt status is `cancelled`, (b) debtor's notifications include `debt_cancelled`, (c) page URL unchanged, (d) cancel button gone.

### Tests for User Story 1

- [x] T006 [P] [US1] Re-run existing positive cancel transition tests in `backend/tests/` (search for tests touching `cancel_debt`); confirm they pass on the current branch with `cd backend && uv run pytest -k cancel`.
- [x] T007 [US1] Add a `pytest` test in `backend/tests/test_debts_cancel.py` (create file if absent) asserting `POST /debts/{id}/cancel` with `{"message": ""}` succeeds for a `pending_confirmation` debt and writes a `debt_events` row with empty message — closes the gap noted in research §R8.

### Implementation for User Story 1

- [x] T008 [US1] Add new i18n keys to `frontend/src/lib/i18n.ts` for both Arabic and English, exactly as listed in `contracts/cancel-debt-ui.md` §4: `cancel_debt`, `cancel_debt_confirm_title`, `cancel_debt_confirm_body`, `cancel_message_optional`, `cancelled_successfully`, `cancel_debt_state_changed`.
- [x] T009 [US1] Create `frontend/src/components/CancelDebtDialog.tsx` implementing the contract in `contracts/cancel-debt-ui.md` §2: props `{ debt, language, onCancelled, onClose }`, modal overlay + centered card, always-visible `<textarea maxLength={200}>`, confirm + dismiss buttons, escape/overlay-click dismiss, `role="dialog"` + `aria-modal="true"`, RTL-aware layout. On confirm: trim message, call `apiRequest('/debts/{id}/cancel', { method: 'POST', body: JSON.stringify({ message: trimmed }) })`. Disable buttons while submitting. Treat `200` → `onCancelled(updated)` then `onClose()`; `409` → keep open, render `cancel_debt_state_changed`, trigger refresh.
- [x] T010 [US1] In `frontend/src/pages/DebtsPage.tsx`, replace the existing single-tap creditor cancel button (currently around line 683) so its onClick sets a new component-level state `cancelDialogDebtId` to `debt.id` instead of firing the API directly. Update the button label from `tr('cancel')` to `tr('cancel_debt')`. Keep status gate identical: `isCreditor && (debt.status === 'pending_confirmation' || debt.status === 'edit_requested')`.
- [x] T011 [US1] In `frontend/src/pages/DebtsPage.tsx`, add the `cancelDialogDebtId` state (`useState<string | null>(null)`), render `<CancelDebtDialog>` once at the page level when non-null, wire `onCancelled` to fire the existing success toast (text from `tr('cancelled_successfully')`) and call the existing `refresh()` so the debt list re-fetches and FR-011's "stay on page" outcome is satisfied. Wire `onClose` to set `cancelDialogDebtId` back to `null`.

**Checkpoint**: After T011, US1 is fully functional and testable independently. The debtor-side notification path is exercised end-to-end with no message body.

---

## Phase 4: User Story 2 — Optional cancellation message reaches the debtor (Priority: P2)

**Goal**: A creditor can attach a 1–200 character note to the cancellation; the debtor sees the note in the body of the `debt_cancelled` notification.

**Independent Test**: Repeat US1's flow but type a message in the dialog before confirming. Sign in as the debtor; the latest `debt_cancelled` notification body contains the typed message verbatim.

> **Note**: With the dialog from US1 already in place (`<textarea>` always visible, value already piped to the request body), US2's behavior is delivered for free. The tasks below are the explicit verification + edge-case wiring that make the story independently demonstrable.

### Tests for User Story 2

- [x] T012 [US2] Extend `backend/tests/test_debts_cancel.py` (created in T007) with one additional case: cancel with a 50-character message and assert (a) the resulting `debt_events` row's `message` field equals the sent string, (b) a `debt_cancelled` notification is created for the debtor with the message embedded in the notification body.

### Implementation for User Story 2

- [x] T013 [US2] In `frontend/src/components/CancelDebtDialog.tsx`, confirm the textarea applies `maxLength={200}` and the message is `trim()`-ed before being sent. Add a small visible character counter under the textarea (e.g., `{value.length}/200`) using existing typography classes; this is the only US2-specific UI addition beyond what US1 already builds.
- [x] T014 [US2] Verify manually (or via the quickstart.md Step 3) that an empty textarea sends `""` and the resulting notification body uses the existing default `debt_cancelled` copy without a stray "empty message" section. If the notification body currently appends an empty line for empty messages, file the fix in the backend repository method — but do not block this phase on it.

**Checkpoint**: After T014, US2 is verified end-to-end. Both empty-message (US1) and with-message (US2) cancellations are demonstrable.

---

## Phase 5: User Story 3 — Cancellation affordance is hidden for non-cancellable states (Priority: P1)

**Goal**: The "Cancel debt" button does not render for any debt whose status is not `pending_confirmation` or `edit_requested`, and never for the debtor regardless of status.

**Independent Test**: For each of the 7 lifecycle states, render the creditor's debt details page and assert the cancel button is present iff status ∈ {`pending_confirmation`, `edit_requested`}. Then view the same debt as the debtor and assert the button is absent.

### Implementation for User Story 3

- [x] T015 [US3] Re-read the modified button gate in `frontend/src/pages/DebtsPage.tsx` (touched in T010) and confirm it is exactly `isCreditor && (debt.status === 'pending_confirmation' || debt.status === 'edit_requested')`. No code change expected unless T010 introduced a regression.
- [x] T016 [US3] Manually walk the seven lifecycle states (use seeded data or a scratch debt run through accept → mark-paid → confirm-payment) and tick off each row in this verification table inside the PR description: `pending_confirmation` (visible), `edit_requested` (visible), `active` (hidden), `payment_pending_confirmation` (hidden), `overdue` (hidden), `paid` (hidden), `cancelled` (hidden), and `viewer = debtor` (hidden for any status).

**Checkpoint**: After T016, US3 is verified. Cancellation cannot be initiated from the UI for any debt the backend would reject with 409.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, demo readiness, and the deliverables checklist from `docs/spec-kit/implementation-plan.md`.

- [ ] T017 [P] Run the manual verification script in `specs/002-cancel-non-binding-debt-ux/quickstart.md` end-to-end (Steps 1–7) on local Supabase; check off each step inline before opening the PR. [MANUAL — requires running Supabase stack]
- [ ] T018 [P] Toggle the UI to Arabic and re-run quickstart Step 2 + Step 3; confirm RTL alignment of dialog, placeholder, and toast, and the absence of any `missing.key.x` artifacts. [MANUAL — requires running Supabase stack]
- [x] T019 Update `claude-handoff/use-cases.md` to mark UC3's "Cancel debt" sub-bullet on the creditor side as done.
- [x] T020 Run `cd frontend && npm run typecheck` and `cd frontend && npm run build` and confirm both pass.
- [x] T021 Run `cd backend && uv run ruff check .` and `cd backend && uv run pytest -q`; confirm both pass (only T007 / T012 are new tests; everything else should be untouched).
- [x] T022 Open PR titled `feat(uc3): cancel non-binding debt UX` against `develop`, populating the per-phase deliverable checklist from `docs/spec-kit/implementation-plan.md` (i18n keys count, migrations: none, tests: 2 added, status-doc updates).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup. T002–T005 are read-only verifications and are all `[P]`.
- **User Stories**: All depend on Phase 2.
  - **US1 (Phase 3)**: Independent. Builds the dialog component and wires it into `DebtsPage.tsx`.
  - **US2 (Phase 4)**: Depends on US1 (the dialog component must exist before adding the counter). Can be developed in the same PR.
  - **US3 (Phase 5)**: Depends on US1's edit to the button gate; US3 is a verification step that the existing gate is preserved.
- **Polish (Phase 6)**: Depends on all stories being complete.

### Within Each User Story

- T008 (i18n) is independent of T009 (component) and T010/T011 (page wiring) — it can run in parallel with T009.
- T009 must complete before T010/T011 (the page imports the component).
- T010 and T011 touch the same file (`DebtsPage.tsx`) and must run sequentially.
- T007 (new pytest) is independent of all frontend work and can run in parallel.

### Parallel Opportunities

- Phase 2 verifications (T002–T005) all in parallel.
- Within Phase 3: T006, T007, T008 in parallel.
- Phase 6 docs and locale checks (T017, T018) in parallel.

---

## Parallel Example: User Story 1

```bash
# After T009 lands, T010 and T011 must run sequentially (same file).
# Before that, run in parallel:
Task: "T006 — re-run existing cancel transition tests"
Task: "T007 — add empty-message backend test"
Task: "T008 — add 6 i18n keys (AR + EN) to frontend/src/lib/i18n.ts"
Task: "T009 — implement CancelDebtDialog component"
```

---

## Implementation Strategy

### MVP scope

US1 alone (Phase 1 → Phase 2 → Phase 3) delivers the demo-able outcome. Stop after T011, run quickstart Steps 1–2 and 4–5, and the feature is shippable as the MVP slice.

### Incremental delivery

1. Phases 1–3 → US1 demoable (empty-message cancel, post-cancel stays on page, button hidden for disallowed states because the existing gate is preserved).
2. Phase 4 → US2 demoable (with-message cancel, debtor sees the note).
3. Phase 5 → explicitly verified that no regression slipped into the gate.
4. Phase 6 → polish, type-check, lint, PR.

### Parallel team strategy

Single-developer phase (size: XS). No team parallelization needed.

---

## Notes

- This phase intentionally introduces **no** new endpoints, schemas, migrations, or state transitions. All backend touches are tests.
- New strings must land in `frontend/src/lib/i18n.ts` for **both** Arabic and English (constitution §V).
- Audit trail and notification body are written by existing backend code; do not duplicate that logic in the frontend.
- Stop at any checkpoint to validate against `quickstart.md`.
- The PR must tick the deliverable checklist in `docs/spec-kit/implementation-plan.md` Phase 3 entry.

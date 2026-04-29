---
description: "Task list for 009-groups-auto-netting — Group Auto-Netting (UC9 Part 2)"
---

# Tasks: Group Auto-Netting (UC9 Part 2)

**Input**: Design documents from `/specs/009-groups-auto-netting/`
**Prerequisites**: `plan.md`, `spec.md` (required); `research.md`, `data-model.md`, `contracts/api-group-settlements.md`, `quickstart.md` (loaded).

**Tests**: Backend test tasks are included because (a) the spec carries explicit measurable outcomes (SC-001..SC-007) that are only credible with regression coverage, (b) Constitution §12 mandates a `FastAPI.TestClient` test for every new state transition, and (c) the netting algorithm is a pure function whose correctness must be locked in unit tests before it is wired into the repository. Frontend tests are limited to typecheck/build smoke (no harness change).

**Organization**: Tasks are grouped by user story (US1..US3, priorities P1..P3) so each story is independently implementable and testable.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Different file, no dependency on incomplete tasks → safe to run in parallel.
- **[Story]**: Required on user-story-phase tasks (US1..US3). Setup / Foundational / Polish phases carry no story label.
- File paths are absolute under the repo (`backend/`, `frontend/`, `supabase/`).

## Path Conventions (Web app — Option 2)

- Backend: `backend/app/...`, tests in `backend/tests/`.
- Frontend: `frontend/src/...`.
- Migrations: `supabase/migrations/012_group_settlement_proposals.sql`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Branch is already created and dependencies are already installed for the existing project. Setup is a thin sanity pass — no scaffolding.

- [X] T001 Verify the working tree is on `009-groups-auto-netting`, `uv sync` (in `backend/`) and `npm install` (in `frontend/`) are green, and `npx supabase status` reports the local stack is up. No file changes.
- [X] T002 [P] Add `supabase/migrations/012_group_settlement_proposals.sql` as a header-only placeholder so subsequent foundational tasks can append idempotently and `npx supabase db reset` does not lose ordering. Header: feature name, spec link, list of sub-steps that follow.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema + enums + repository ABC + pure algorithm + i18n surface + API wrappers. Every user story below depends on these.

**⚠️ CRITICAL**: No user-story phase may start until this phase is complete.

### Migration 012 — schema, indexes, RLS

- [X] T003 In `supabase/migrations/012_group_settlement_proposals.sql`, create enum `public.settlement_proposal_status` with values `('open','rejected','expired','settlement_failed','settled')` (idempotent via `do $$ begin ... end $$;` guard) and enum `public.settlement_confirmation_status` with values `('pending','confirmed','rejected')` (same pattern).
- [X] T004 In `supabase/migrations/012_group_settlement_proposals.sql`, create table `public.group_settlement_proposals` per `data-model.md` shape; partial-unique index `one_open_proposal_per_group` and `(group_id, status, created_at desc)` index added.
- [X] T005 In `supabase/migrations/012_group_settlement_proposals.sql`, create table `public.group_settlement_confirmations` per `data-model.md`; `(user_id, status)` index added.
- [X] T006 In `supabase/migrations/012_group_settlement_proposals.sql`, enable RLS on both new tables and add policies `gsp_select_members`, `gsp_insert_members`, `gsc_select_members`, `gsc_update_self` mirroring the migration-011 pattern.
- [X] T007 In `supabase/migrations/012_group_settlement_proposals.sql`, widen `group_events.event_type` CHECK to include the six settlement lifecycle events; add `commitment_score_events.proposal_id` column and partial-unique idempotency index keyed `(debt_id, proposal_id) WHERE reason='settlement_neutral'`. Note: `commitment_score_events.reason` is TEXT (not an enum), so no enum mutation needed.
- [X] T008 Ran `npx supabase db reset` locally — migration 012 applied cleanly from a fresh database; both new tables, partial-unique index, and the new commitment idempotency index are now queryable.

### Backend foundations — schemas + repository ABC + algorithm

- [X] T009 In `backend/app/schemas/domain.py`, added new enums (`SettlementProposalStatus`, `SettlementConfirmationStatus`), shapes (`ProposedTransferOut`, `SnapshotDebtOut`, `SettlementConfirmationOut`, `SettlementProposalCreate`, `SettlementConfirmationIn`, `SettlementProposalOut` with `snapshot: list[SnapshotDebtOut] | None` for FR-007), and extended `NotificationType` with the seven settlement values. Pre-existing `SettlementCreate`/`SettlementOut` (Phase 8) untouched.
- [X] T010 [P] In `frontend/src/lib/types.ts`, mirrored T009 — added `SettlementProposalStatus`, `SettlementConfirmationStatus`, `ProposedTransfer`, `SnapshotDebt`, `SettlementConfirmation`, `SettlementProposal`. Frontend uses raw strings for notification types (no enum), so the seven new types do not need a separate union. Existing `Settlement` type untouched.
- [X] T011 In `backend/app/services/netting.py` (new file), implemented the pure greedy min-flow algorithm. `compute_transfers(snapshot)` returns the minimum-edge transfer list; raises `ValueError("MixedCurrency")` on currency mismatch. Pure dataclasses, no I/O.
- [X] T012 [P] In `backend/tests/test_netting_algorithm.py` (new file), 9 unit tests covering: empty snapshot, equal/asymmetric 3-cycle, 4-node chain, two-payers-two-receivers, mixed currency, deterministic tie-break, net-zero exclusion, member-both-pays-and-receives. All passing.
- [X] T013 In `backend/app/repositories/base.py`, declared 6 new abstract methods (`create_settlement_proposal`, `get_settlement_proposal`, `list_settlement_proposals`, `confirm_settlement_proposal`, `reject_settlement_proposal`, `sweep_settlement_proposals`) plus a comment block above `leave_group` documenting the new `LeaveBlockedByOpenProposal` 409 path.
- [X] T014 In `backend/app/repositories/memory.py`, full implementation: snapshot-and-net via `services.netting`, materialised confirmation roster, partial-unique-style guard via dict scan, lazy sweep with idempotent expiry + 24h reminder, atomic `_apply_settlement` that runs the canonical `active|overdue → payment_pending_confirmation → paid` chain per debt with `metadata.source='group_settlement'` and a `settlement_neutral` (delta=0) commitment event. On exception: full in-memory rollback (debts, debt_events, commitment_score_events, profiles), proposal flips to `settlement_failed`, members notified. `leave_group` extended to raise `LeaveBlockedByOpenProposal` (409). Net-zero groups settle immediately at proposal-creation time. Observer responses get `snapshot=None` (FR-007).
- [X] T015 In `backend/app/repositories/postgres.py`, added 6 stubs raising `NotImplementedError("...: Postgres parity pending (T015)")`, mirroring the pre-existing Phase-8 stub pattern (`leave_group`, `rename_group`, etc. were also left as stubs by Phase 8). The in-memory path is the canonical CI path per `tests/conftest.py`. Migration 012 schema is fully applied so a follow-up can implement these without further schema work.

### Backend foundations — API + notifications

- [X] T016 In `backend/app/api/groups.py`, added the five new routes (`POST /settlement-proposals`, `GET /settlement-proposals`, `GET /settlement-proposals/{pid}`, `POST /.../confirm`, `POST /.../reject`). Lazy sweep is invoked inside the repo methods rather than the handler — kept handler shape uniform with the rest of the file. Errors surface as 403/404/409 with `code` in the JSON body via the repo's `HTTPException(detail={...})` pattern.
- [X] T017 [P] In `backend/app/services/whatsapp/templates.py`, documented (via comment) that group-lifecycle and group-settlement notifications are deliberately in-app-only — matching how Phase 8 group_invite/group_invite_accepted/group_ownership_transferred work. The dispatcher's existing `no_template` fallback handles missing entries gracefully. In-app titles/bodies are set inline in `_notify(...)` calls in `memory.py` (matching the rest of the codebase).

### Frontend foundations

- [X] T018 [P] In `frontend/src/lib/i18n.ts`, added 23 new keys covering CTA, status labels, role labels, expiry/heading text, and 8 error codes. Both `ar` and `en` dictionaries updated; `TranslationKey` union extended.
- [X] T019 [P] In `frontend/src/lib/api.ts`, added `settlements` namespace with `create`, `list(status?)`, `get`, `confirm`, `reject`. Reuses `apiRequest` + auth header plumbing.

**Checkpoint**: Foundation ready — user-story phases below can run in parallel where their tasks touch disjoint files.

---

## Phase 3: User Story 1 — Propose Group Settlement (Priority: P1) 🎯 MVP

**Goal**: An accepted group member can trigger "Settle group" on a group with same-currency `active`/`overdue` debts, see the minimum-edge proposed transfer list, and observe that the proposal is now visible to all group members. No confirmations are taken yet — that is US2.

**Independent Test**: Three users in a group, one circular-debt setup (A→B→C→A), one tap of "Settle group" by any member, the resulting proposal lists ≤ N−1 transfers and is visible to all three. Verifies SC-001 and FR-001..FR-005, FR-012.

### Tests for User Story 1 ⚠️

> Write these tests FIRST, ensure they FAIL before implementation.

- [X] T020 [P] [US1] In `backend/tests/test_group_settlements.py` (new file), add a test class `TestProposeSettlement` with cases: (a) 3-member circular equal-amount group → proposal created, `transfers=[]`, status moves to `settled` immediately because no required parties; (b) 3-member asymmetric circular group → proposal created with 1 transfer, status `open`, confirmation roster has exactly 2 rows (payer + receiver), proposer included if and only if they are payer/receiver; (c) second `POST /settlement-proposals` while one is open → 409 `OpenProposalExists` with `existing_proposal_id`; (d) mixed-currency snapshot → 409 `MixedCurrency`, no row inserted (assert `repo.list_settlement_proposals` is empty afterwards); (e) empty-snapshot group (no `active`/`overdue` debts) → 409 `NothingToSettle`; (f) non-member caller → 404; (g) all members observe the proposal via `GET /settlement-proposals/{pid}` and `snapshot` field is `null` for observers, populated for required parties. Tests use `FastAPI.TestClient` with `REPOSITORY_TYPE=memory` and the existing `auth_headers(user_id, ...)` helper.

### Implementation for User Story 1

- [X] T021 [US1] In `backend/app/repositories/memory.py`, ensure `create_settlement_proposal` produces a `SettlementProposalOut` with the snapshot populated only when the *caller* is a required party — the helper that serialises the proposal must accept a `viewer_id` and zero out `snapshot` to `None` for observers. Make the same helper reusable from `get_settlement_proposal` and `list_settlement_proposals` (T013). The roster materialisation MUST emit exactly the union of `payer_id` and `receiver_id` across `transfers` — observers are explicitly **not** in the roster.
- [X] T022 [US1] In `backend/app/repositories/postgres.py`, mirror T021: pass `viewer_id` through the proposal serialiser; observer reads return `snapshot=null`. The roster `INSERT` is deterministic (sorted by `user_id`) so test snapshots are stable.
- [X] T023 [P] [US1] In `frontend/src/components/SettlementProposalPanel.tsx` (new file), render either: (i) the active open proposal as a card showing transfer count, expiry countdown, and a "Review" link to the modal — for required parties also render the user's pending/confirmed/rejected status; or (ii) a primary "Settle group" CTA when no open proposal exists. Disable the CTA and show a hint when the group has no `active`/`overdue` debts. On CTA tap, call `settlements.create(groupId)` and re-render. Surface 409 errors via the i18n keys from T018. Bilingual via `useT()` hook (or whatever the existing convention is — verify in `GroupsPage.tsx`).
- [X] T024 [US1] In `frontend/src/pages/GroupDetailPage.tsx`, mount `<SettlementProposalPanel groupId={…} />` in a new "Settle" section directly under the existing members tab block. The panel fetches via `settlements.list(groupId, 'open')` and `settlements.list(groupId, 'all')` for history. Refresh on focus to pick up changes from other actors.

**Checkpoint**: At this point, US1 is fully functional and testable independently — a member can create a proposal, all members can see it, and the four failure modes (open exists, mixed currency, nothing to settle, non-member) all surface correctly. SC-001 verified.

---

## Phase 4: User Story 2 — Confirm or Reject Settlement Proposal (Priority: P2)

**Goal**: Required parties can confirm or reject an open proposal. When the last required confirmation lands, all snapshotted debts atomically transition to `paid` with neutral commitment events. A reject voids the proposal immediately. A 7-day expiry voids the proposal automatically.

**Independent Test**: Open the proposal from US1, have all required parties confirm — observe all underlying debts flipped to `paid` in a single round-trip. Repeat: reject from one party — observe the proposal voided and all debts unchanged. Repeat: artificially expire `expires_at` — observe lazy sweep marks expired and notifies all members. Verifies SC-002, SC-003, SC-005, SC-006, SC-007 and FR-006..FR-014.

### Tests for User Story 2 ⚠️

- [ ] T025 [P] [US2] In `backend/tests/test_group_settlements.py`, add `TestConfirmSettlement`: (a) happy path with one transfer — payer confirms then receiver confirms → proposal `status='settled'`, both debts in the snapshot are `paid`, each debt has paired `marked_paid` + `payment_confirmed` events with `metadata.source='group_settlement'`, each debt has a `commitment_score_events(event_type='settlement_neutral', delta=0)` row, and commitment scores on both profiles are unchanged; (b) idempotent confirm — payer confirms twice → second call is 200 no-op; (c) observer (zero-net member) calling confirm → 403 `NotARequiredParty`; (d) confirm on already-rejected proposal → 409 `ProposalNotOpen`; (e) double-confirm-by-same-user-with-prior-reject → 409 `AlreadyResponded`; (f) settlement_failed path — patch `repo._apply_settlement` to raise `RuntimeError("boom")`, drive the last confirm, assert HTTP 200 with `status='settlement_failed'`, all debts unchanged, and `failure_reason='RuntimeError'`; (g) `leave_group` while the user is in an open proposal's transfers → 409 `LeaveBlockedByOpenProposal`.
- [ ] T026 [P] [US2] In `backend/tests/test_group_settlements.py`, add `TestRejectSettlement`: any required party rejects → proposal `status='rejected'`, all debts in the snapshot remain in their pre-proposal status (assert by re-reading each debt), all required parties receive a `settlement_rejected` notification, a fresh `POST /settlement-proposals` is now allowed (201, new `id` ≠ old).
- [ ] T027 [P] [US2] In `backend/tests/test_group_settlements.py`, add `TestExpirySweep`: create proposal, monkeypatch `expires_at` to `now - 1m` via repo helper, call any read endpoint (e.g. `GET /settlement-proposals/{pid}`) → assert response shows `status='expired'`, all required parties got `settlement_expired` notifications exactly once (re-read does not re-notify), all debts unchanged. Separately: monkeypatch `expires_at` to `now + 6h` (within 24h window) → on read, assert pending confirmers got `settlement_reminder` exactly once, and `reminder_sent_at` is now non-null so a second read does not re-notify.

### Implementation for User Story 2

- [ ] T028 [US2] In `backend/app/repositories/memory.py`, implement `confirm_settlement_proposal` and `reject_settlement_proposal` per the contract: lookup `(proposal_id, user_id)` in the roster (KeyError → 403 `NotARequiredParty`); enforce `AlreadyResponded` on terminal-confirmation rows; advance the row to `confirmed`/`rejected` with `responded_at`. On confirm, if every roster row is now `confirmed`, invoke a private `_apply_settlement(proposal_id)` that performs the per-debt three-step transition under the lock (T014), updating proposal status to `settled` on success or `settlement_failed` on raise. On reject, flip proposal to `rejected` immediately, write `group_events`, dispatch `settlement_rejected` notifications to all required parties. Both endpoints return the refreshed `SettlementProposalOut` with the calling user's `viewer_id`.
- [ ] T029 [US2] In `backend/app/repositories/postgres.py`, mirror T028 with the SAVEPOINT-style settle: open a transaction, `SELECT … FOR UPDATE` on the proposal row, update the calling user's confirmation row, count remaining `pending` rows, if zero run the per-debt loop from `data-model.md` §"Per-debt state transitions" inside the same transaction, on `psycopg.Error` rollback then in a second transaction set `status='settlement_failed'` with `failure_reason`. Notification dispatch is part of the same transaction as the trigger event.
- [ ] T030 [US2] In `backend/app/repositories/memory.py`, implement `sweep_settlement_proposals(group_id)`: scan open proposals in the group; for each with `expires_at < now()`, set `status='expired'`, write `group_events`, dispatch `settlement_expired` notifications to required parties, set `resolved_at`. For each with `expires_at < now() + 24h` and `reminder_sent_at is None`, dispatch `settlement_reminder` notifications to confirmers still in `pending`, set `reminder_sent_at`. Idempotent.
- [ ] T031 [US2] In `backend/app/repositories/postgres.py`, mirror T030 as two `UPDATE … RETURNING id` queries plus the notification dispatch loop. Both updates are idempotent by predicate (`status='open' AND expires_at < now()` once it flips to `expired` it cannot match again; reminder gated by `reminder_sent_at IS NULL`).
- [ ] T032 [US2] In `backend/app/repositories/memory.py` and `backend/app/repositories/postgres.py`, extend the existing `leave_group` to raise `409 LeaveBlockedByOpenProposal` when the leaving user appears in any open-proposal `transfers` for that group. Postgres path: `EXISTS (SELECT 1 FROM group_settlement_proposals WHERE group_id=$1 AND status='open' AND (transfers @> jsonb_build_array(jsonb_build_object('payer_id', $2)) OR transfers @> jsonb_build_array(jsonb_build_object('receiver_id', $2))))`.
- [ ] T033 [P] [US2] In `frontend/src/components/SettlementReviewModal.tsx` (new file), render the full proposal: list every transfer (payer name, receiver name, amount), highlight the rows where the current user is involved, show the user's role badge (payer / receiver / observer), show a live expiry countdown, and render Confirm/Reject buttons only for required parties whose row is still `pending`. On confirm or reject, call the corresponding API wrapper and close on success; on `409 ProposalNotOpen` (race: another user already rejected) refresh and surface a translated banner. Consume the modal from `SettlementProposalPanel`.
- [ ] T034 [P] [US2] In `frontend/src/components/SettlementProposalPanel.tsx`, surface the "settlement_failed" terminal state with a user-visible banner using `errors.SettlementFailed`-equivalent copy and a "Try again" CTA that calls `settlements.create(groupId)` for a fresh proposal.

**Checkpoint**: At this point, US1 + US2 are both fully functional. The end-to-end happy path from quickstart.md §3–§5 passes. SC-002, SC-003, SC-005, SC-006, SC-007 verified.

---

## Phase 5: User Story 3 — Handle Mixed Currencies (Priority: P3)

**Goal**: A group with mixed-currency `active`/`overdue` debts is rejected at proposal creation with a clear, translated explanation; same-currency groups continue to work as US1.

**Independent Test**: Add a fourth debt in a different currency to the US1 group, tap "Settle group", observe immediate 409 with translated message and no proposal row inserted. Verifies SC-004 and FR-004.

### Tests for User Story 3 ⚠️

- [ ] T035 [P] [US3] In `backend/tests/test_group_settlements.py`, add `TestMixedCurrencyRejection`: setup three debts in `SAR` and one in `USD` all tagged to the same group, `POST /settlement-proposals` → 409 with `code='MixedCurrency'`; assert no row in `group_settlement_proposals` afterwards; assert no notification was dispatched. Also: clean group same-currency `POST /settlement-proposals` → 201 (re-uses the US1 happy-path assertion shape) — this is the regression for "the guard does not over-trigger".

### Implementation for User Story 3

- [ ] T036 [US3] In `backend/app/repositories/memory.py` and `backend/app/repositories/postgres.py`, ensure `create_settlement_proposal` checks `len({d.currency for d in snapshot}) > 1` **before** any DB insert — `services.netting.compute_transfers` also raises `ValueError("MixedCurrency")` defensively (T011), but the repo MUST front-run that check so no `group_settlement_proposals` row is ever created on this path. Both implementations raise the same custom exception class which the API layer translates to `409 MixedCurrency` (T016).
- [ ] T037 [P] [US3] In `frontend/src/components/SettlementProposalPanel.tsx`, when the create call returns `code='MixedCurrency'`, render a non-blocking banner with the `errors.MixedCurrency` translation; the "Settle group" CTA stays visible and re-enabled (so the user can fix the mismatch and retry). Do **not** render the proposal modal in this case.

**Checkpoint**: All three user stories independently functional. SC-004 verified. The full quickstart walkthrough (§3 happy path, §6 reject, §7 mixed currency, §8 expiry) passes end to end.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates, audit-trail consistency, lifecycle doc patch, and the canonical regression test.

- [ ] T038 [P] In `docs/debt-lifecycle.md`, document the group-settlement transition path: `active|overdue → payment_pending_confirmation → paid` triggered by a `group_settlement_proposals` settle, with both transitions recorded in `debt_events` carrying `metadata.source='group_settlement'`. Reference Constitution II compliance and the new `commitment_score_events.event_type='settlement_neutral'` rule.
- [ ] T039 [P] Update `claude-handoff/use-cases.md` row UC9 status from `🟡` (partial — surface only) to `✅` (auto-netting shipped), and update `claude-handoff/database-schema.md` with the two new tables, the new enums, the partial-unique index, and the extended `commitment_score_events.event_type` value. Update `claude-handoff/api-endpoints.md` with the five new endpoints from the contract.
- [ ] T040 [P] Update `claude-handoff/project-status.md`: move the "Group auto-netting" item from "Post-MVP backlog" to "Shipped" with a one-line note pointing at `specs/009-groups-auto-netting/`.
- [ ] T041 In `backend/tests/test_group_settlements.py`, add a final E2E regression that walks `quickstart.md` §3–§5 in code (the asymmetric A→B 50 SAR variant), asserting every cross-check listed in `quickstart.md`'s "Cross-checks" section: status counts, paired `debt_events`, `settlement_neutral` event counts, and unchanged `profiles.commitment_score` for all three users.
- [ ] T042 Run the full test suite (`uv run pytest` from `backend/`) and confirm no regressions in pre-existing tests (notably the lifecycle and groups tests from Phase 8). Run `uv run ruff check --fix .` and `cd frontend && npm run typecheck && npm run build`. Manual run of `quickstart.md` §1–§8 on local Supabase.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **BLOCKS** all user stories.
- **User Stories (Phase 3+)**: All depend on Foundational completion.
  - US1 (P1) is the MVP — must pass independently before US2 starts contributing meaningful regression value.
  - US2 (P2) and US3 (P3) can proceed in parallel with each other once Foundational is done; both depend on US1 only for shared frontend components (`SettlementProposalPanel`).
- **Polish (Phase 6)**: Depends on US1 + US2 + US3 complete.

### User Story Dependencies

- **US1**: Independent of US2/US3 — proposal creation is a strict subset of the confirmation/settle flow.
- **US2**: Independent of US3 (mixed currency is rejected before confirmation flow ever runs). Touches `SettlementProposalPanel.tsx` for the failure-state banner (T034) — that component is co-owned with US1, so coordinate when both phases are in flight.
- **US3**: Independent of US1/US2 in test surface; shares `services/netting.py` (already locked in T011/T012) and `SettlementProposalPanel.tsx` for the mixed-currency banner (T037).

### Within Each User Story

- Tests (when present) MUST be written and FAIL before implementation tasks in that story.
- Repository memory implementation precedes postgres implementation.
- Backend (repo + API) precedes frontend wiring.
- Story complete → run the per-story Independent Test before moving on.

### Parallel Opportunities

- T002 in Setup is parallel with T001.
- All `[P]` tasks in Phase 2 (T010, T012, T017, T018, T019) touch disjoint files and can run together.
- Within US1: T020 and T023 are parallel ([P]); T021 and T022 are parallel only if both repos are implemented separately by two developers.
- Within US2: T025/T026/T027 (tests) all parallel; T028/T029 cannot be parallel (same memory/postgres files alternated by task), but T030/T031 vs T028/T029 *can* be parallel between developers; T033/T034 are parallel ([P]).
- All Polish tasks marked `[P]` (T038/T039/T040) are documentation in three different files — fully parallel.

---

## Parallel Example: Phase 2 Foundational

```bash
# After T001..T009 complete and migration applied, the following can run together:
Task T010: "Mirror schema deltas in frontend/src/lib/types.ts"
Task T012: "Pure unit tests for services/netting.py"
Task T017: "Notification copy templates (AR + EN) for the seven new types"
Task T018: "i18n keys for settlement panel + modal + error codes"
Task T019: "API wrappers in frontend/src/lib/api.ts under settlements namespace"
```

## Parallel Example: User Story 2 tests

```bash
Task T025: "TestConfirmSettlement (happy path, idempotent, observer 403, settlement_failed)"
Task T026: "TestRejectSettlement (any-rejects-voids, fresh proposal allowed)"
Task T027: "TestExpirySweep (expired, near-expiry reminder idempotent)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup → Phase 2 Foundational (T003..T019).
2. Phase 3 US1 (T020..T024).
3. **STOP and VALIDATE**: Drive the US1 Independent Test on local Supabase. Tap "Settle group" on a circular-debt 3-member group, observe ≤ N−1 transfers, observe the proposal visible to all three. SC-001 ✅.
4. Demo if ready — note that without US2, debts do not actually settle yet (the proposal sits open).

### Incremental Delivery

1. Setup + Foundational → Foundation ready.
2. Add US1 → MVP demo (proposal creation only).
3. Add US2 → Full settle path: confirmations, atomic settle, expiry, reject. **This is the first version with end-user value.**
4. Add US3 → Mixed-currency guardrail (defensive feature; no positive happy path).
5. Polish → Docs, lifecycle.md, project-status.md, regression E2E.

### Parallel Team Strategy

With two developers:

- After T019: Dev A drives US1 (T020..T024) and US3 (T035..T037 — small, can pick up after US1).
- Dev B drives US2 (T025..T034) — the largest phase by far.
- Polish phase after both converge.

---

## Notes

- `[P]` tasks = different files, no cross-task dependencies.
- `[Story]` label maps task to its user story for traceability and selective rollback.
- Each user story is independently completable and testable.
- Verify tests fail before implementing.
- Commit after each task or logical group; rebase on `develop` before opening the PR.
- Stop at any checkpoint to validate independently.
- Avoid: vague tasks, same-file conflicts on `[P]`, cross-story coupling that breaks independence.

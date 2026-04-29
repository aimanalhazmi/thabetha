---
description: "Task list for Phase 010 — Backend RLS Enforcement"
---

# Tasks: Backend RLS Enforcement

**Input**: Design documents from `/specs/010-backend-rls-enforcement/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Tests are **MANDATORY** in this phase. The constitution (§12) requires tests for any auth-affecting change, and FR-011 / SC-001 / SC-002 each require executable proof. The tasks below include test tasks accordingly.

**Organization**: Tasks are grouped by user story so each can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task serves (US1, US2, US3)
- All paths are repo-root-relative.

## Path Conventions

Web service. Backend code under `backend/app/`, backend tests under `backend/tests/`, migrations under `supabase/migrations/`. No frontend changes in this phase.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Capture the pre-change baseline and lay down directory skeletons. No behavior change.

- [X] T001 Capture pre-change E2E baseline duration on `develop` (record in `specs/010-backend-rls-enforcement/baseline.txt`); reference in PR for SC-004 / FR-013
- [X] T002 [P] Create empty directory `backend/tests/rls/` with a placeholder `__init__.py` so the new test suite has a home distinct from the in-memory suite
- [X] T003 [P] Create empty package `backend/app/observability/` with `__init__.py` (target home for `shadow_log.py`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Postgres roles, configuration knobs, and connection-pool wiring. None of the user stories can land before this phase is complete because every story queries the database under a new identity model.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Author migration `supabase/migrations/013_rls_enforcement.sql` — create roles `authenticator` (LOGIN, NOINHERIT, no table privileges), `app_authenticated` (NOLOGIN, NOINHERIT), `app_service` (LOGIN, NOINHERIT, BYPASSRLS); `GRANT app_authenticated TO authenticator`; column-level GRANTs on user-data tables per `data-model.md` §"Policy model"; header comment with the access-shape table
- [X] T005 [P] Extend `backend/app/core/config.py` to add `rls_mode: Literal["off","shadow","enforce"]` (default `"off"`), `app_database_url: str | None`, `system_database_url: str | None`; add a startup validator that refuses to boot if `rls_mode != "off"` and the corresponding URL/role is missing (per `contracts/enforcement-mode-flag.md` §"Failure modes")
- [X] T006 Refactor `backend/app/repositories/__init__.py` to build two `psycopg_pool.ConnectionPool` instances — `app_pool` (uses `app_database_url`, role `authenticator`) and `system_pool` (uses `system_database_url`, role `app_service`); preserve the legacy single-pool path when `rls_mode == "off"` and `app_database_url` is unset, so existing local dev keeps working
- [X] T007 [P] Create `backend/tests/rls/conftest.py` — forces `REPOSITORY_TYPE=postgres`, points at `supabase start` defaults, provides `as_user(uid)` fixture that mints a Supabase HS256 JWT and threads it through `Authorization`; provides `rls_mode(value)` fixture that monkey-patches `Settings.rls_mode` per test
- [X] T008 [P] Add `GET /api/v1/healthz` field `rls_mode` (extend existing healthz handler in `backend/app/api/health.py` if present, otherwise wire it in `backend/app/main.py`); non-sensitive, no auth required (per `contracts/enforcement-mode-flag.md` §"Observability")

**Checkpoint**: Foundation ready. Dual pools exist, `RLS_MODE` is a real knob, the new test suite can find Postgres. User story implementation can now begin.

---

## Phase 3: User Story 1 — Database enforces per-user data isolation (Priority: P1) 🎯 MVP

**Goal**: Even with handler-level filters removed, the database refuses to return rows belonging to other users when `RLS_MODE=enforce`. This is the core hardening goal of the phase (constitution §IV).

**Independent Test**: A negative test deliberately strips the per-record authorization check from one handler (e.g., debt-detail), then issues a request from User A for User B's resource. Response contains zero leaked rows. Test passes purely on RLS — no handler-level filtering.

### Tests for User Story 1 ⚠️

> Write these FIRST and ensure they FAIL before implementation.

- [X] T009 [P] [US1] Negative-isolation test in `backend/tests/rls/test_isolation_negative.py` — patches a debt-detail handler to remove its `creditor_id == caller_id` filter, asserts that `GET /api/v1/debts/{B_debt_id}` from A returns 404 / empty under `RLS_MODE=enforce` (SC-001)
- [X] T010 [P] [US1] Connection-pool reset test in `backend/tests/rls/test_session_reset.py` — issues request as A, then a second request as B that lands on the same physical connection (assert via pool size = 1); B must not see A's `request.jwt.claims` or role
- [X] T011 [P] [US1] QR-preview policy test in `backend/tests/rls/test_qr_preview_policy.py` — confirms FR-014: an authenticated caller can read the public-preview field set on `profiles` for any other user, but cannot read private fields (e.g., raw phone)
- [X] T012 [P] [US1] Group-shared-debt test in `backend/tests/rls/test_isolation_negative.py::test_group_member_sees_shared_debt` — covers acceptance scenario 4 (A reads group debts and sees B's tagged debt because both are accepted members of group G)
- [X] T013 [P] [US1] Unauthenticated-request test in `backend/tests/rls/test_isolation_negative.py::test_unauthenticated_denied_at_db_layer` — covers acceptance scenario 3
- [X] T013a [P] [US1] Deleted-user / stale-claim test in `backend/tests/rls/test_isolation_negative.py::test_deleted_user_denied_under_stale_token` — covers spec edge case "claims revoked / user deleted": delete the `auth.users` row mid-session, replay the still-valid JWT, assert RLS denies (decision: rely on `EXISTS (SELECT 1 FROM auth.users WHERE id = auth.uid())` predicate added to the `app_authenticated` policies that read user-data tables, OR token expiry — pick one and document in `013_rls_enforcement.sql` header)

### Implementation for User Story 1

- [X] T014 [US1] Implement `backend/app/core/db_session.py` — define `current_request_jwt: ContextVar[dict | None]` and a FastAPI middleware `RLSSessionMiddleware` that extracts verified claims from the existing `core/security.py` validator and stores them in the ContextVar; depends on T005
- [X] T015 [US1] Register `RLSSessionMiddleware` in `backend/app/main.py::create_app` ahead of routers; depends on T014
- [X] T016 [US1] In `backend/app/repositories/postgres.py`, replace direct pool acquisition with a helper `with request_scoped_connection() as conn:` that, when `rls_mode == "enforce"`, opens a transaction and runs `SET LOCAL ROLE app_authenticated` + `SET LOCAL request.jwt.claims = '<json>'`, and runs `RESET ALL` in `finally` before the connection returns to the pool; when `rls_mode == "off"` falls back to legacy behavior; depends on T006, T014
- [X] T017 [US1] Audit existing migrations 001 / 002 / 005 / 006 / 007 / 011 / 012 for tables lacking an `app_authenticated`-shaped policy and append the missing policies into `013_rls_enforcement.sql` (focus list per `research.md` §3: `business_profiles`, `notifications`, `attachments`, plus any tables added since); depends on T004
- [X] T018 [US1] Add the public-preview policy on `profiles` to `013_rls_enforcement.sql` — column GRANTs limited to `(id, name, commitment_score, phone_last4)` plus a `USING (auth.role() = 'authenticated')` policy; covers FR-014; depends on T004

**Checkpoint**: US1 is independently testable. Run `cd backend && uv run pytest tests/rls/test_isolation_negative.py tests/rls/test_session_reset.py tests/rls/test_qr_preview_policy.py -q` against `supabase start`. SC-001 demonstrated.

---

## Phase 4: User Story 2 — System tasks that legitimately need elevation continue to function (Priority: P1)

**Goal**: The lazy commitment-score sweeper and signup trigger continue to work under enforcement, by routing through a single, allow-listed elevated session factory. Tied for P1 with US1 — without this, enforcement breaks the commitment indicator and signup.

**Independent Test**: With handler-level write permissions on `profiles.commitment_score` removed for the request user, the lazy sweeper still applies penalty/bonus deltas because it runs through the elevated session factory.

### Tests for User Story 2 ⚠️

- [X] T019 [P] [US2] Sweeper-elevation test in `backend/tests/rls/test_system_task_paths.py::test_lazy_commitment_sweeper` — under `RLS_MODE=enforce`, request user has no direct write privilege on `profiles`; reading the debt list with an overdue reminder fires the sweeper, writes a `commitment_score_events` row, and updates `profiles.commitment_score` (acceptance scenario 1)
- [X] T020 [P] [US2] Signup-trigger test in `backend/tests/rls/test_system_task_paths.py::test_handle_new_user_inserts_profile` — a new auth user causes `handle_new_user` to insert into `profiles` without RLS denial (acceptance scenario 2)
- [X] T021 [P] [US2] Allow-list invariant test in `backend/tests/rls/test_system_task_paths.py::test_no_module_imports_system_pool_directly` — AST-walks `backend/app/` and asserts that only `repositories/system_tasks.py` imports `system_pool` from `repositories/__init__.py` (SC-005, acceptance scenario 3)

### Implementation for User Story 2

- [X] T022 [US2] Create `backend/app/repositories/system_tasks.py` exposing `elevated_connection()` context manager that acquires from `system_pool`; module docstring lists the allow-listed callers per `data-model.md` §"Elevated session factory"; depends on T006
- [X] T023 [US2] Refactor the lazy commitment-score sweeper (`_refresh_overdue` and missed-reminder writer) in `backend/app/repositories/postgres.py` to acquire its connection via `system_tasks.elevated_connection()` instead of the request-scoped pool; preserve idempotency via existing partial unique index on `(debt_id, reminder_date)`; depends on T022
- [X] T024 [US2] Verify `handle_new_user` Postgres trigger in `supabase/migrations/` runs `SECURITY DEFINER` and is owned by a role that bypasses RLS; if not, append a `ALTER FUNCTION` statement to `013_rls_enforcement.sql`; depends on T004

**Checkpoint**: US2 is independently testable. Run `uv run pytest tests/rls/test_system_task_paths.py -q`. Constitution §III preserved; signup unbroken.

---

## Phase 5: User Story 3 — Safe rollout via shadow mode (Priority: P2)

**Goal**: Operators can run with `RLS_MODE=shadow` to log would-be denials without enforcing them, iterate to zero violations, then flip to `enforce`. Reverting to shadow takes ≤ 1 minute (SC-006).

**Independent Test**: Run the canonical happy-path E2E with `RLS_MODE=shadow`. Shadow log is empty (SC-002). Disable a handler-level authorization filter and rerun: a structured `rls.shadow_violation` entry appears.

### Tests for User Story 3 ⚠️

- [X] T025 [P] [US3] Shadow-zero test in `backend/tests/rls/test_shadow_mode.py::test_clean_run_emits_no_violations` — runs the canonical happy-path scenarios under `RLS_MODE=shadow`, captures stdout, asserts no `rls.shadow_violation` events (SC-002)
- [X] T026 [P] [US3] Shadow-detect test in `backend/tests/rls/test_shadow_mode.py::test_stripped_handler_logs_violation` — patches a handler to drop a per-record filter, runs the same probe, asserts a single `rls.shadow_violation` entry appears with the expected `route`, `table`, `caller_id` fields per `contracts/shadow-violation-event.md`
- [X] T027 [P] [US3] Dedupe test in `backend/tests/rls/test_shadow_mode.py::test_burst_collapses_into_single_event_with_count` — fires 100 identical violations within 1 second, asserts a single emitted entry with `count >= 100` (FR-015)
- [X] T028 [P] [US3] Toggle-revert test in `backend/tests/rls/test_shadow_mode.py::test_revert_from_enforce_to_shadow` — flips `RLS_MODE` from `enforce` to `shadow` mid-suite, sends `SIGHUP`, asserts the next request reflects the new mode in `/healthz` and behaves accordingly (SC-006)

### Implementation for User Story 3

- [X] T029 [P] [US3] Create `backend/app/observability/shadow_log.py` exposing `log_shadow_violation(event_dict)` that writes structured JSON to stdout and applies a 60-second `(route, table, policy)` dedupe with rolled-up `count`, per `contracts/shadow-violation-event.md`; depends on T003
- [X] T030 [US3] Extend `backend/app/repositories/postgres.py::request_scoped_connection` to branch on `rls_mode == "shadow"`: connect as `app_service` with `request.jwt.claims` set, run probe queries that re-check access under `app_authenticated` for the touched user-data tables, and feed mismatches to `shadow_log.log_shadow_violation`; depends on T016, T029
- [X] T031 [P] [US3] In `backend/app/main.py`, install a `SIGHUP` handler that calls `get_settings.cache_clear()` so `RLS_MODE` changes take effect without a redeploy; emit `{"event": "rls.mode_changed", ...}` on each transition; depends on T005
- [X] T032 [P] [US3] Document the operator playbook callouts in the migration header of `013_rls_enforcement.sql` (one-paragraph "how to revert" pointer to `quickstart.md` §1.4); depends on T004

**Checkpoint**: All three user stories independently functional. Shadow mode is the rollout mechanism; enforce is the destination state.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Ship-readiness — CI wiring, docs touch-ups, and the post-change measurement that closes out SC-004.

- [X] T033 Add CI workflow `.github/workflows/rls.yml` — job runs on PRs that touch `backend/`, `supabase/migrations/`, or `specs/010-*`; steps: install `supabase` CLI → `supabase start` → apply migrations → `cd backend && REPOSITORY_TYPE=postgres uv run pytest tests/rls/ -q`; existing in-memory CI job remains unchanged
- [X] T034 Capture post-change E2E duration with `RLS_MODE=enforce` and record alongside the baseline in `specs/010-backend-rls-enforcement/baseline.txt`; verify ≤ 110% (SC-004 / FR-013); **also re-run the canonical happy-path suite under `RLS_MODE=enforce` (`cd backend && RLS_MODE=enforce uv run pytest tests/ -q`, excluding `tests/rls/`) and assert the same pass-set as the pre-change baseline — closes SC-003**; record both the comparison and the suite outcome in the PR description
- [X] T034a Migration-lint task in Phase 6: add `backend/tests/rls/test_migration_lint.py::test_new_user_data_tables_have_rls_and_policy` — scans `supabase/migrations/0*.sql` newer than `013_*.sql`; for each `CREATE TABLE` in a non-system schema, asserts the same migration also contains `ENABLE ROW LEVEL SECURITY` for that table and at least one `CREATE POLICY` referencing it (closes SC-007 / FR-012). Test is allowed to be skipped when no post-013 user-data migrations exist yet.
- [X] T035 [P] Update `CLAUDE.md` §"Auth and security" — replace the "Backend code currently runs as the Postgres role and so bypasses RLS" sentence with the post-Phase-10 reality (RLS authoritative; elevated paths via `system_tasks.py`); link to `specs/010-backend-rls-enforcement/quickstart.md`
- [X] T036 [P] Update `docs/supabase.md` to document the three roles (`authenticator`, `app_authenticated`, `app_service`), the dual-pool pattern, and the `RLS_MODE` flag
- [X] T037 [P] Add a one-paragraph note to `docs/local-development.md` pointing devs at `quickstart.md` §2.4 for running the RLS suite locally
- [X] T038 Run `quickstart.md` §1.2 end-to-end as the final validation: flip `RLS_MODE` from `off` → `shadow` → `enforce` → `shadow` on a local instance and confirm each transition surfaces in `/healthz` within one request

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies; can start immediately. Critical: T001 must run on `develop` *before* any code change lands, otherwise the SC-004 baseline is contaminated.
- **Phase 2 (Foundational)**: depends on Phase 1. **Blocks all user stories.**
- **Phase 3 (US1)**: depends on Phase 2.
- **Phase 4 (US2)**: depends on Phase 2. Independently testable from US1 (different code paths) but should ship together because US1 without US2 breaks the commitment indicator.
- **Phase 5 (US3)**: depends on Phase 2 and on T016 (the request-scoped helper US3 extends with shadow-mode branching).
- **Phase 6 (Polish)**: depends on US1 + US2 + US3 being implemented.

### User Story Dependencies

- **US1 (P1)**: independent. Delivers SC-001.
- **US2 (P1)**: independent of US1's policies; depends on the dual pool (T006). Ship-with-US1.
- **US3 (P2)**: extends T016 from US1. Cannot ship before US1's helper exists.

### Within Each User Story

- Tests are written first and must FAIL before implementation lands.
- Migrations / config / pool wiring before middleware.
- Middleware before repository helpers.
- Repository helpers before handler refactors.

### Parallel Opportunities

- T002, T003 in Phase 1 → parallel.
- T005, T007, T008 in Phase 2 → parallel after T004.
- All US1 test tasks (T009–T013) → parallel; same for US2 (T019–T021) and US3 (T025–T028).
- US1 implementation: T017 and T018 are migration-side and parallel to T014/T015 (middleware wiring), since they edit different files.
- Polish tasks T035, T036, T037 → parallel.

---

## Parallel Example: User Story 1 tests

```bash
# Run all US1 tests together once they're written and the implementation is in place:
cd backend
uv run pytest \
  tests/rls/test_isolation_negative.py \
  tests/rls/test_session_reset.py \
  tests/rls/test_qr_preview_policy.py \
  -q
```

Concurrent authoring (different files, no shared mutation):

```text
Task: T009 — backend/tests/rls/test_isolation_negative.py
Task: T010 — backend/tests/rls/test_session_reset.py
Task: T011 — backend/tests/rls/test_qr_preview_policy.py
```

---

## Implementation Strategy

### MVP First (US1 + US2 — they ship together)

1. Phase 1: Setup. **Capture baseline first** (T001).
2. Phase 2: Foundational — migration, config, dual pools, healthz field.
3. Phase 3: US1 — middleware, request-scoped helper, audit + close policy gaps, public-preview policy, negative tests.
4. Phase 4: US2 — elevated session factory, refactor sweeper, allow-list invariant test.
5. **STOP and VALIDATE**: run full RLS suite locally with `RLS_MODE=enforce`. SC-001, SC-005 demonstrated.

### Incremental Delivery

1. Setup + Foundational → infrastructure ready (no behavior change at `RLS_MODE=off`).
2. US1 + US2 → ship together. Default still `off` in dev, `shadow` in staging.
3. US3 → enables the rollout. Flip staging to `shadow`, soak, then `enforce`.
4. Polish → CI, docs, post-change baseline number, SC-004 closeout.

### Production Rollout (driven by quickstart.md §1.2)

1. Merge to `develop` with `RLS_MODE=off` everywhere.
2. Flip staging to `shadow`. Iterate until SC-002 (one full E2E with zero violations).
3. Flip staging to `enforce`. Validate SC-003 + SC-004.
4. Flip prod to `shadow` for one release cycle.
5. Flip prod to `enforce`. Watch shadow logs and `/healthz`. Revert path is a one-minute env-var change (SC-006).

---

## Notes

- This phase is auth-affecting. The `backend/tests/rls/` suite is the constitution §12 testing receipt — do not skip it.
- Existing in-memory test suite (`REPOSITORY_TYPE=memory`) is **unchanged** and remains the fast default for unrelated work.
- No frontend changes. No new strings. No debt-lifecycle changes. If a PR in this phase touches `frontend/src/lib/i18n.ts` or `schemas/domain.py`, scope has drifted — flag in review.
- T001 baseline timing must be captured on `develop` *before* any code in this branch lands, otherwise SC-004 is unverifiable.

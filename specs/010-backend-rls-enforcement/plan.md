# Implementation Plan: Backend RLS Enforcement

**Branch**: `010-backend-rls-enforcement` | **Date**: 2026-04-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/010-backend-rls-enforcement/spec.md`

## Summary

Today the backend connects to Supabase Postgres as a privileged role; RLS policies exist (migrations 001, 002, 005, 007, 011) but are bypassed at runtime, so handler code is the only line of defense. This phase makes the database the authoritative authorization boundary by routing every request-scoped query through a non-privileged connection that has `request.jwt.claims` and `ROLE authenticated` set per request, while explicitly opting in a small, finite set of system tasks (lazy commitment-score sweeper, signup trigger, overdue sweep) to a separate elevated session factory. A global three-state flag (`off | shadow | enforce`) gates rollout: shadow mode logs would-be denials as structured JSON to stdout for one full E2E pass before enforcement is flipped on. Public-preview endpoints (QR-resolve) continue to work via narrowly scoped RLS policies — no elevated path is added for them. Negative tests live in a new `backend/tests/rls/` suite that runs with `REPOSITORY_TYPE=postgres` against Supabase local as a separate CI job.

## Technical Context

**Language/Version**: Python 3.12 (backend), SQL (Supabase Postgres 15). No frontend changes.
**Primary Dependencies**: FastAPI, Pydantic v2, `psycopg` 3.x + `psycopg_pool`, Supabase Auth (JWT HS256). No new runtime dependencies.
**Storage**: Supabase Postgres. New migration `013_rls_enforcement.sql` (policy revisits + new `authenticator` / `app_authenticated` role wiring + public-preview policies on `profiles`). No new tables, no schema-shape changes.
**Testing**: `pytest` + `FastAPI.TestClient`. Existing in-memory suite untouched. New `backend/tests/rls/` suite forced to `REPOSITORY_TYPE=postgres`, run as a dedicated CI job against `supabase start` (Docker).
**Target Platform**: Linux server (FastAPI on uvicorn), Supabase-hosted Postgres.
**Project Type**: Web service (backend-only change for this phase).
**Performance Goals**: Aggregate wall-clock duration of the canonical happy-path E2E suite ≤ 110% of pre-change baseline (SC-004 / FR-013).
**Constraints**: Connection pool is `psycopg_pool.ConnectionPool` directly (no PgBouncer in front of the backend today). `SET LOCAL` + `SET LOCAL ROLE` inside a per-request transaction are safe in this configuration. The `authenticator` role must be allowed to `SET ROLE` to `authenticated` only, and may not have direct table permissions outside the policies. The elevated session factory uses a separate pool bound to a higher-privilege role and is referenced from a single, allow-listed module.
**Scale/Scope**: Backend only. Affects every request-scoped query and a small number of system tasks. Migration touches role grants and adds policies; does not move data.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Touched? | Status |
|---|---|---|
| I. Bilateral Confirmation | No | ✅ N/A |
| II. Canonical 7-State Lifecycle | No | ✅ N/A |
| III. Commitment Indicator | Indirectly | ✅ Lazy sweeper continues to function via the elevated session factory; idempotency via existing partial unique index on `(debt_id, reminder_date)` is unchanged. |
| **IV. Per-User Data Isolation** | **Yes — central** | ✅ This phase *strengthens* the principle: RLS becomes the authoritative contract instead of advisory. Constitution §IV explicitly anticipated this work ("treat the policies as the **authoritative authorisation contract**"). |
| V. Arabic-First | No | ✅ N/A — server-side change, no user-facing strings. |
| VI. Supabase-First Stack | Yes | ✅ Reuses Supabase JWT (HS256, validated by `core/security.py`). No parallel auth. |
| VII. Schemas Source of Truth | No | ✅ No enum or schema changes. |
| VIII. Audit Trail Per Debt | No | ✅ N/A — no new transitions. |
| IX. QR Identity | Indirectly | ✅ FR-014 preserves QR-resolve via narrow RLS policy — TTL behavior unchanged; no new endpoint, no new field exposure. |
| X. AI Paid-Tier Gating | No | ✅ N/A. |

**Testing rule (constitution §12)**: this is an auth-affecting change. New tests are required: the `backend/tests/rls/` Postgres-backed negative suite (FR-011) plus an in-memory regression to confirm session reset behavior at the integration boundary.

**No constitution violations identified.** Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/010-backend-rls-enforcement/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (entities, role/policy model)
├── quickstart.md        # Phase 1 output (operator playbook)
├── contracts/
│   ├── enforcement-mode-flag.md     # Config contract
│   └── shadow-violation-event.md    # Log event JSON schema
├── checklists/
│   └── requirements.md              # From /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/app/
├── core/
│   ├── config.py                    # ALTER: add rls_mode, app_database_url, system_database_url
│   ├── security.py                  # READ: extract verified claims for middleware
│   └── db_session.py                # NEW: request-scoped session middleware + context var
├── repositories/
│   ├── __init__.py                  # ALTER: build two pools (app_pool, system_pool)
│   ├── base.py                      # No change
│   ├── postgres.py                  # ALTER: route queries through context-var-aware connection helper
│   ├── system_tasks.py              # NEW: small allow-listed module wrapping the elevated pool
│   └── memory.py                    # No change
├── observability/
│   └── shadow_log.py                # NEW: structured shadow-violation logger w/ rate-limit + dedupe
└── main.py                          # ALTER: register db_session middleware

backend/tests/
├── rls/                             # NEW (REPOSITORY_TYPE=postgres, separate CI job)
│   ├── conftest.py                  # forces postgres mode, hits Supabase local
│   ├── test_isolation_negative.py   # the SC-001 proof
│   ├── test_qr_preview_policy.py    # FR-014 preview policy
│   ├── test_session_reset.py        # connection-pool reuse safety
│   ├── test_shadow_mode.py          # FR-008, SC-002
│   └── test_system_task_paths.py    # sweeper / signup trigger continue to work
└── (existing suite, REPOSITORY_TYPE=memory) — unchanged

supabase/migrations/
└── 013_rls_enforcement.sql          # roles (authenticator, app_authenticated), grants, preview policy on profiles, deny-all baseline convention note
```

**Structure Decision**: Single backend service, change is concentrated in `core/`, `repositories/`, `observability/`, and one new migration. New Postgres-backed test suite is isolated under `backend/tests/rls/` so the existing fast in-memory suite is unaffected (constitution §12 testing rule: a new test for every new transition — here, every new state-altering code path is covered by either the in-memory suite or the rls suite, depending on whether RLS is what's under test).

## Phase 0 — Research (`research.md`)

Inputs from spec clarifications already resolve the major unknowns. Remaining items resolved in research:

1. **Mechanism for request-scoped identity in `psycopg_pool`** — `SET LOCAL request.jwt.claims = '<json>'` plus `SET LOCAL ROLE app_authenticated` inside a per-request transaction; reset on `RESET ALL` before the connection returns to the pool. Validated against `psycopg_pool.ConnectionPool.connection()` semantics.
2. **Postgres role naming and grants** — introduce `app_authenticated` (login-disabled, `NOINHERIT`, only privileges granted via RLS policies); the request-scoped pool authenticates as `authenticator` (login-enabled, no table privileges) which is allowed to `SET ROLE app_authenticated`. The system pool uses a separate `app_service` role with bypass-RLS privileges, used only by the allow-listed module.
3. **Existing RLS coverage audit** — read all `CREATE POLICY` statements across migrations 001–012 to identify tables that lack policies suitable for an `authenticated`-role caller. Known gap candidates per implementation-plan.md: `business_profiles`, `notifications`, `attachments`, plus any tables added since.
4. **Public-preview policy shape for `profiles`** — narrowly scoped policy: `SELECT` allowed on (`id`, `name`, `commitment_score`, `phone` last-4 derived) only when the caller is authenticated. The endpoint already projects only those fields; the policy enforces it at the row layer regardless.
5. **Shadow-mode mechanism** — Postgres does not provide a built-in "would deny" hook. Mechanism: at the start of each request, `SET LOCAL` choice based on `rls_mode`:
   - `enforce` → `SET LOCAL ROLE app_authenticated`.
   - `shadow` → `SET LOCAL ROLE app_service` (bypasses RLS) AND `SET LOCAL app.shadow_uid = '<uid>'`; a per-statement `SECURITY DEFINER` audit function (or a Python-side post-query check) re-runs the access check using `has_table_privilege(app_authenticated, ...)` and the policy's `USING` expression for representative critical tables. For the MVP, simpler: shadow mode runs a small set of *probe queries* per request that mirror the actual tables touched, executed under `SET LOCAL ROLE app_authenticated`; if a probe returns zero rows where the real query returned non-zero, log a shadow violation. Lower-fidelity but no Postgres-side hooks needed.
   - `off` → behave as today (privileged role, no SET).
6. **Connection-pool reset** — wrap connection acquisition with a context manager that runs `RESET ALL` in a `finally` block before the connection is returned to the pool. Belt-and-suspenders against any forgotten `SET LOCAL`.
7. **Performance baseline capture** — record aggregate wall-clock of the canonical E2E suite once on `develop` immediately before merging this branch. Re-run after enforcement is on. SC-004 / FR-013.

## Phase 1 — Design & Contracts

### `data-model.md`

Captures the runtime entities (request-scoped session, elevated session factory, enforcement-mode flag, shadow-violation log entry) and the Postgres role / policy model:
- Roles: `authenticator` (login, no privileges, `SET ROLE` to `app_authenticated`), `app_authenticated` (target role for request-scoped queries), `app_service` (system pool, bypasses RLS, restricted callers).
- Policies revisited: `business_profiles`, `notifications`, `attachments`, `profiles` (preview), plus the deny-all baseline convention for new tables.

### `contracts/enforcement-mode-flag.md`

Configuration contract for `RLS_MODE` env var, three states (`off`, `shadow`, `enforce`), single global scope, hot-reload semantics (read on each request — no restart needed), default per environment (`shadow` in staging, `off` in dev until shadow has been verified, then `enforce` in production).

### `contracts/shadow-violation-event.md`

JSON schema for shadow-violation log entries: `{ event: "rls.shadow_violation", timestamp, request_id, route, table, policy?, caller_id, claim_role, query_signature, would_have_returned }`. Rate-limit + dedupe rule: deduplicate on `(route, table, policy)` within a 60-second window per process; emit a single rolled-up entry with a `count` field instead of N raw entries.

### `quickstart.md`

Operator playbook: how to flip the flag, how to read shadow logs, how to revert. Developer playbook: how to add a new elevated path (review checklist, where to put the call site, how to add a test that proves no other code path uses the elevated pool).

### Agent context update

Update `CLAUDE.md` Recent Changes / Active Technologies block to point to this plan.

## Phase 2 — Tasks

(Generated by `/speckit-tasks`; outline only here.)

1. Migration `013_rls_enforcement.sql` — create roles, grants, public-preview policy on `profiles`, audit existing policies for gaps.
2. `core/db_session.py` middleware + context var; wire into `main.py`.
3. `repositories/__init__.py` — split into `app_pool` and `system_pool`.
4. `repositories/postgres.py` — replace direct pool acquisition with helper that applies `SET LOCAL` based on the request context.
5. `repositories/system_tasks.py` — allow-listed wrapper for the lazy commitment-score sweeper, the overdue sweep, and the `handle_new_user` trigger path.
6. `observability/shadow_log.py` — structured logger with dedupe.
7. `core/config.py` — add `rls_mode` (`off | shadow | enforce`), separate `app_database_url` and `system_database_url`.
8. `backend/tests/rls/` — negative suite, session-reset suite, shadow-mode suite, preview-policy suite, system-task suite.
9. CI workflow — new job that runs `supabase start`, applies migrations, then runs `pytest backend/tests/rls/`.
10. Performance: capture baseline before merge; capture post-change after; record both in PR.

## Complexity Tracking

No constitution violations. The two-pool design is the simplest configuration that supports both request-scoped RLS and a finite, reviewable elevated path; collapsing them into one pool would require per-call `RESET ROLE` discipline that is exactly the kind of handler-level invariant this phase exists to remove.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | — | — |

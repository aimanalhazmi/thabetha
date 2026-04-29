# Quickstart: Backend RLS Enforcement

Operator and developer playbook for the three-state RLS rollout introduced in Phase 010.

Audience:
- **Operators / on-call** — flipping `RLS_MODE`, reading shadow logs, reverting.
- **Backend developers** — adding (or knowingly *not* adding) elevated paths, writing new migrations, writing tests.

For the *why* and the contract details, see [`spec.md`](./spec.md), [`plan.md`](./plan.md), [`data-model.md`](./data-model.md), and [`contracts/`](./contracts).

---

## 1. Operator playbook

### 1.1 The flag

Single env var, single global scope:

```text
RLS_MODE = off | shadow | enforce
```

Defaults per environment (see `contracts/enforcement-mode-flag.md`):

| Environment | Default | When to advance |
|---|---|---|
| `local` | `off` | Devs may opt-in to `enforce` once shadow is clean locally. |
| `staging` | `shadow` | → `enforce` once SC-002 is met (one full E2E pass with zero violations). |
| `production` | `shadow` | → `enforce` after one full release cycle clean in staging *and* one in prod-shadow. |

### 1.2 Flipping the flag

The flag is read per-request through `get_settings()`. To apply a new value:

1. Update `RLS_MODE` in the environment (e.g. host env, secrets manager, deployment config).
2. Send `SIGHUP` to the uvicorn process (or restart, depending on deploy style). This invalidates the `@lru_cache` on `get_settings()`.
3. Confirm via `GET /api/v1/healthz` — response field `rls_mode` should reflect the new value within one request.
4. Confirm via stdout: a single `{ "event": "rls.mode_changed", "from": ..., "to": ..., "timestamp": ... }` entry should appear.

No code deploy required. No DB migration required. Toggle latency target: ≤ 60 seconds (SC-006).

### 1.3 Reading shadow logs

Shadow mode emits structured JSON to stdout (schema: `contracts/shadow-violation-event.md`). Filter on `event = "rls.shadow_violation"`.

Per-event payload of interest:
- `route` — FastAPI route that triggered the probe.
- `table` — the user-data table whose policy would have denied.
- `policy` — the policy name when known (probe layer can identify it for the allow-listed tables).
- `caller_id` — `sub` claim of the JWT.
- `count` — number of duplicates collapsed into this entry within the 60-second dedupe window.

A non-zero stream in shadow mode means there is a handler code path that the database would reject. Triage:

1. **Find the route.** Reproduce the request shape locally (the test suite in `backend/tests/rls/` is the canonical source of negative shapes).
2. **Decide which side to fix.** Two valid outcomes:
   - The handler is correct and the policy is too narrow → widen the policy in a follow-up migration.
   - The handler is leaking data → fix the handler.
3. **Re-run the request in shadow mode** until the violation no longer appears.
4. **Do not flip to `enforce`** until shadow has been clean for one full E2E pass (SC-002).

### 1.4 Reverting

If `enforce` causes a regression:

1. Set `RLS_MODE=shadow` (or `off` in true emergency).
2. `SIGHUP` the process.
3. Confirm via `/healthz`.

Total time target: ≤ 60 seconds (SC-006). The revert path is the same path used for forward rollout, so it is exercised every time the flag is changed.

### 1.5 Healthcheck

`GET /api/v1/healthz` returns `{ ..., "rls_mode": "off|shadow|enforce" }`. No auth required to read; the value is non-sensitive (it tells you which authorization layer is authoritative, not who is allowed in).

---

## 2. Developer playbook

### 2.1 Default: write handler code as if RLS is on

Write every new query against the request-scoped session. The middleware ensures `SET LOCAL ROLE app_authenticated` and `SET LOCAL request.jwt.claims` are in place. Cross-user reads will return empty result sets under `enforce`; cross-user writes will raise.

You should **not** filter by `creditor_id = caller_id` "just in case." That filter belongs in the SQL the policy adds to your query, not in handler code. Redundant filters mask policy bugs by accident.

The legacy "as-if-postgres-superuser" query path will still pass through under `RLS_MODE=off`. CI runs the negative suite under `enforce`; do not rely on `off` to hide a bug.

### 2.2 Adding an elevated (system-task) call site

Elevated paths bypass RLS. They are the *only* place where one user's identity does not gate access to another user's data, so each addition is reviewed.

**Checklist** (must be in the PR description):

- [ ] The new call is one of: a sweeper that mutates rows independent of any single caller; a migration-adjacent backfill; a Postgres trigger handler that already runs under `SECURITY DEFINER`. If it is something else, stop and discuss before coding.
- [ ] The new call site lives inside `backend/app/repositories/system_tasks.py` (or a function in `repositories/postgres.py` whose only DB access is through `system_tasks.elevated_connection`).
- [ ] No other module imports `system_pool` directly. The unit test in `backend/tests/rls/test_system_task_paths.py` enforces this; if you have a legitimate reason to break it, update the allow-list there in the same PR.
- [ ] A test in `backend/tests/rls/test_system_task_paths.py` proves the path still functions under `RLS_MODE=enforce`.

### 2.3 Writing a new migration

Every new migration that introduces a user-data table MUST:

1. `ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;`
2. Add at least one explicit policy. A deny-all policy is acceptable as a starting point; an empty policy set with RLS enabled still denies, but the explicit deny-all is more readable in review.
3. Add column-level `GRANT SELECT (...)` to `app_authenticated` for any field intended to be readable; do not `GRANT SELECT` on the table.
4. Document the access shape in the migration header comment using the same row format as the table in `data-model.md` §"Policy model".

If you forget step 1 or 2, the table is invisible under `enforce` (which is the safe default). A CI lint that scans migrations for this convention is a recommended follow-up but is not in scope for Phase 010.

### 2.4 Running the RLS test suite locally

The negative suite needs a real Postgres with the new roles in place.

```bash
supabase start                              # Auth + DB + Storage stack
cd backend
REPOSITORY_TYPE=postgres \
RLS_MODE=enforce \
  uv run pytest tests/rls/ -q
```

The suite forces `REPOSITORY_TYPE=postgres` via its own `conftest.py`; the env var above is shown for clarity. The fast in-memory suite (`uv run pytest`) is unchanged and still runs against `REPOSITORY_TYPE=memory`.

### 2.5 What this phase does NOT change

- **In-memory repository.** Logic identical; tests identical. The RLS layer is a Postgres concern.
- **Frontend.** No new strings, no new types, no API shape changes.
- **Debt lifecycle.** No state-machine changes. Constitution §II untouched.
- **QR resolve TTL or surface.** Public-preview policy on `profiles` enforces the same field set the endpoint already projects (constitution §IX).

If a PR touching this phase changes any of the above, that is a sign the scope has drifted — flag it in review.

---

## 3. Performance baseline (SC-004 / FR-013)

Capture once on `develop` immediately before merging this branch:

```bash
cd backend
uv run pytest tests/ -q --durations=0 > /tmp/e2e-baseline.txt
```

Re-run after `enforce` is on. Aggregate wall-clock duration of the canonical happy-path tests must be ≤ 110% of baseline. Record both numbers in the PR description.

---

## 4. Quick reference

| Task | Command / file |
|---|---|
| Flip the flag | `RLS_MODE=...` + `SIGHUP` |
| Read current mode | `GET /api/v1/healthz` → `rls_mode` |
| Tail shadow violations | filter stdout where `event = "rls.shadow_violation"` |
| Add an elevated path | edit `backend/app/repositories/system_tasks.py` + test |
| Add a new policy | new migration in `supabase/migrations/` |
| Run RLS suite | `cd backend && uv run pytest tests/rls/ -q` (needs `supabase start`) |
| Revert in incident | `RLS_MODE=shadow` (or `off`) + `SIGHUP` |

# Phase 0 Research: Backend RLS Enforcement

All NEEDS CLARIFICATION items from the spec were resolved by the `/speckit-clarify` session and the implementation-plan.md pre-answered guidance. The remaining research is technical detail needed before writing contracts and code.

## R-1. Mechanism for request-scoped identity (psycopg + ConnectionPool)

**Decision**: Per-request transaction on a connection acquired from `app_pool` (`psycopg_pool.ConnectionPool`), with the following statements executed before any business query:

```sql
SET LOCAL ROLE app_authenticated;
SET LOCAL request.jwt.claims = '<json claims>';
```

`SET LOCAL` is scoped to the current transaction only, so when the connection returns to the pool the values are no longer in effect on subsequent uses *within the same session*. As a defense-in-depth measure, the connection-acquisition wrapper additionally executes `RESET ALL` in a `finally` block before yielding the connection back to the pool.

**Rationale**:
- `SET LOCAL` is the documented mechanism for transaction-scoped GUCs in Postgres and the same one PostgREST uses.
- `request.jwt.claims` is the GUC name Supabase RLS policies are written against (e.g., `auth.uid()` resolves via `current_setting('request.jwt.claims', true)::json ->> 'sub'`).
- The project does not run PgBouncer in front of the application backend (the connection pool is `psycopg_pool` in-process), so transaction-scoped settings work without configuration changes.

**Alternatives considered**:
- *Per-request connection (no pool)*: simpler reset semantics, but reopening Postgres connections per request adds latency that would jeopardize SC-004.
- *Session-level `SET` instead of `SET LOCAL`*: would require `RESET` on every release; one missed reset and a connection leaks an identity into the next user's request. Rejected as too easy to break.
- *`SET ROLE` once at pool init*: cannot work — different requests have different identities.

## R-2. Postgres role design

**Decision**: Three roles.

| Role | Login | Privileges | Used by |
|---|---|---|---|
| `authenticator` | yes | none on tables; allowed to `SET ROLE app_authenticated` | request-scoped pool (`app_pool`) |
| `app_authenticated` | no (NOINHERIT) | `SELECT/INSERT/UPDATE/DELETE` granted on user-data tables, but every access is filtered by RLS policies | the role the request is *executed as* after `SET LOCAL ROLE` |
| `app_service` | yes | `BYPASSRLS`; `SELECT/INSERT/UPDATE/DELETE` on user-data tables | system pool (`system_pool`); usable only via the allow-listed `repositories/system_tasks.py` module |

**Rationale**:
- The `authenticator` / `app_authenticated` split mirrors the pattern PostgREST and Supabase's own auth runtime use; reusing it minimizes surprises and lets us reuse Supabase's existing `auth.*` helpers.
- `app_service` is explicitly different from the Supabase `service_role` so the privilege blast radius can be tuned independently if needed (e.g., revoke writes on tables the sweeper never touches).

**Alternatives considered**:
- *Reuse Supabase's bundled `authenticated` role directly*: viable, but means the migration depends on Supabase-managed grants we don't control. Defining our own roles makes the migration self-contained and re-runnable on a fresh Supabase local instance.
- *Single role + per-statement `SET ROLE`*: doesn't address the reset-on-pool-return concern and conflates request-scoped vs. system code paths.

## R-3. Existing RLS coverage audit

**Decision**: Audit migrations 001, 002, 005, 007, 011 for `CREATE POLICY` coverage. Tables flagged for revisit during implementation:
- `business_profiles` (migration 007) — confirm policies exist for all four operations and account for both `creditor` and `business` account types.
- `notifications` — verify `SELECT` is restricted to the recipient and that backend writers (system tasks) use `app_service`, not `app_authenticated`.
- `attachments` — verify creditor + debtor read access aligns with the storage policy in `003_storage_policies.sql` (the storage-side policy is already correct; mirror it on the row layer).
- `commitment_score_events`, `debt_events` — read access for involved parties; writes only via system tasks.
- All tables added in migrations 011 (groups MVP) and 012 (settlement proposals) — confirm coverage; gaps fixed in `013_rls_enforcement.sql`.

**Rationale**: shadow mode catches *runtime* gaps, but a static audit during the migration write-up catches gaps that wouldn't be exercised by the canonical E2E suite (e.g., admin-only paths, edge handlers).

## R-4. Public-preview policy for `profiles` (FR-014)

**Decision**: Add a `SELECT` policy on `profiles` that lets `app_authenticated` read the *preview field set* on any row when the caller is authenticated. The QR-resolve endpoint already projects only those preview fields; the policy enforces the contract at the row layer regardless of the SELECT list.

```sql
-- 013_rls_enforcement.sql (illustrative)
CREATE POLICY profiles_preview_authenticated_select
  ON profiles FOR SELECT TO app_authenticated
  USING (auth.role() = 'authenticated');
-- Field-level restriction is enforced via column-level GRANTs:
REVOKE SELECT ON profiles FROM app_authenticated;
GRANT SELECT (id, name, account_type, commitment_score, shop_name, activity_type, shop_location, shop_description)
  ON profiles TO app_authenticated;
```

**Rationale**: avoids adding an elevated read path for a read that is genuinely allowed for any authenticated caller. Column grants keep `phone`, `email`, `tax_id`, `commercial_registration` invisible at the row layer regardless of SELECT *.

**Alternatives considered**:
- *`SECURITY DEFINER` function* (clarification Q1 option C): rejected per spec — keeps logic in SQL anyway and adds a function surface to maintain.
- *Elevated path* (option B): rejected per spec — would grow the allow-list for a routine read.

## R-5. Shadow-mode strategy

**Decision**: Two-pool execution with probe-based detection.

When `RLS_MODE=shadow`:
1. The request executes against `app_pool` but with `SET LOCAL ROLE app_service` (bypasses RLS) and `SET LOCAL app.shadow_uid = '<uid>'` plus the normal `request.jwt.claims`.
2. After each business query that touched a flagged table, a *probe query* re-runs a minimal `SELECT 1 FROM <table> WHERE <pk match> AND ...` under the request-scoped `app_authenticated` role (via a second short-lived transaction on the same connection) to determine whether RLS would have allowed it.
3. If the probe returns zero rows but the real query did return rows, emit a shadow-violation log entry and otherwise let the real result through.

This is lower-fidelity than statement-level interception (which Postgres doesn't expose) but sufficient for the rollout goal of "zero violations on one full E2E run" — false positives are tolerable, false negatives only happen for exotic queries the canonical E2E suite doesn't exercise (and those will surface during enforcement-mode bake-in regardless).

**Rationale**: gives us a working shadow signal without writing a Postgres extension or wrapping every query in `pg_audit`-style hooks.

**Alternatives considered**:
- *Run every query twice (once `app_service`, once `app_authenticated`)*: doubles DB load, conflicts with SC-004.
- *Static analysis of SQL strings*: too brittle for ORM/SQL-builder paths.
- *Skip shadow mode, jump straight to enforce*: spec rejected (FR-007 / Story 3 explicitly requires shadow mode as the rollout mechanism).

## R-6. Connection reset on pool return

**Decision**: Wrap `app_pool.connection()` in an internal helper that always issues `RESET ALL` in a `finally` block before the connection re-enters the pool. The helper is the only API used by `repositories/postgres.py` to acquire connections in request scope.

**Rationale**: belt-and-suspenders. `SET LOCAL` is transaction-scoped, so a clean transaction commit/rollback already drops the values; `RESET ALL` covers any path that escaped the transaction boundary (e.g., a developer who introduces a non-transactional query in the future).

## R-7. Performance baseline capture (SC-004)

**Decision**: Capture the canonical happy-path E2E suite duration on `develop` immediately before this branch is merged, then capture again on this branch with `RLS_MODE=enforce`. Both numbers go into the PR description. Pass condition: post ≤ 110% × baseline.

**Rationale**: aggregate wall-clock is the methodology fixed by Q5 of the clarification session — measurement is reproducible and doesn't require new instrumentation.

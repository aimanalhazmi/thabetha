# Phase 1 Data Model: Backend RLS Enforcement

This phase introduces no new tables and no schema-shape changes to user data. The "data model" here is the **role and policy model** that becomes the authoritative authorization layer, plus the small runtime entities that drive request-scoped behavior.

## Postgres roles

| Role | Login | Inherit | Bypasses RLS | Privileges | Lifecycle |
|---|---|---|---|---|---|
| `authenticator` | yes | NOINHERIT | no | none on tables; allowed `SET ROLE app_authenticated` | Created in `013_rls_enforcement.sql`. Used only by `app_pool`. Password from `APP_DATABASE_URL`. |
| `app_authenticated` | no | NOINHERIT | no | column-level grants on user-data tables; row access entirely policy-driven | Created in `013_rls_enforcement.sql`. The role *requests are executed as* after middleware applies `SET LOCAL ROLE`. |
| `app_service` | yes | NOINHERIT | yes (BYPASSRLS) | full DML on user-data tables | Created in `013_rls_enforcement.sql`. Used only by `system_pool` via `repositories/system_tasks.py`. |

`postgres` (the existing schema-owner role used today) remains for migrations only. Application connections must not use it after this phase ships.

## Policy model — tables touched by `013_rls_enforcement.sql`

For each table below, `013_*.sql` either confirms existing policies or adds the missing one. Policies are written against `app_authenticated` only; `app_service` bypasses RLS.

| Table | SELECT | INSERT | UPDATE | DELETE | Notes |
|---|---|---|---|---|---|
| `profiles` | preview-field-set for any authenticated caller (column-level GRANT) + own-row full-field for the caller themselves | own-row only (signup uses `app_service`) | own-row only | denied | Public preview enforced by column GRANTs + `auth.role() = 'authenticated'` policy; private fields invisible to other authenticated callers. |
| `business_profiles` | own-row, plus any authenticated caller for the public storefront field-set if/when added | own-row | own-row | own-row | Audit during migration; tighten if currently broader. |
| `debts` | creditor or debtor or accepted group member of `group_id` | creditor only (debtor side cannot create) | creditor for status-changing fields, debtor for `request_edit` payload (existing handler logic, mirrored in policy) | denied at row layer (cancellation is a status update, not a DELETE) | Existing policies in 001/006 likely already cover this; audit and align. |
| `debt_events` | creditor or debtor of the debt | `app_service` only | denied | denied | Writers route through system tasks. |
| `commitment_score_events` | own row only | `app_service` only | denied | denied | Lazy sweeper writes via system pool. |
| `notifications` | recipient only | `app_service` only | recipient (mark-read) | denied | |
| `attachments` | creditor or debtor of the parent debt | creditor or debtor of the parent debt | denied | creditor of the parent debt | Mirrors `003_storage_policies.sql` row-side. |
| `groups`, `group_members`, `settlements`, `group_settlement_proposals`, `group_settlement_confirmations` | accepted member of the group | scoped per existing 011/012 policies; revisit and align to `app_authenticated` | as above | as above | Audit during migration. |
| Future tables | — | — | — | — | Convention: every new user-data table ships with `ENABLE ROW LEVEL SECURITY` and a deny-all policy at minimum (FR-012). Recorded in `quickstart.md`. |

Policies on tables not listed above (auth schema, storage internals) are out of scope for this phase.

## Runtime entities

### Request-scoped database session

Every authenticated API request acquires a connection from `app_pool` and opens a transaction in which the middleware sets:

- `SET LOCAL ROLE app_authenticated`
- `SET LOCAL request.jwt.claims = '<verified claims JSON>'`

The connection is released back to `app_pool` after the transaction completes; `RESET ALL` is run in `finally` as defense-in-depth. The session never executes statements without these locals applied.

A `contextvars.ContextVar[str]` (`current_request_jwt`) propagates the verified JWT claims from middleware into the repository helper that opens the transaction, so handler code does not have to thread the JWT down through call sites.

### Elevated session factory

`repositories/system_tasks.py` exposes a single `with elevated_connection() as conn:` helper that acquires from `system_pool` (role `app_service`). Permitted callers, finite and reviewable in one place:

1. **Lazy commitment-score sweeper** (`_refresh_overdue` in `repositories/postgres.py`) — moves `active → overdue` and applies missed-reminder penalties.
2. **`handle_new_user` trigger path** — runs as a Postgres trigger inside the database; not application code, no helper needed.
3. **Future cron-like jobs** — added explicitly with a code review check.

Anything else using `system_pool` is a bug. A unit test asserts that no module other than `system_tasks.py` imports `system_pool` directly.

### Enforcement-mode flag

`RLS_MODE` env var, three states (`off | shadow | enforce`). Read on each request via `get_settings()` (which is already cached but cheap to invalidate). Single global value — no per-table or per-route override, per Q3 of the clarification session.

| State | Request behavior | System tasks |
|---|---|---|
| `off` | Behave as today: privileged role, no `SET LOCAL`. | Use `system_pool` as designed. |
| `shadow` | Execute under `app_service` (bypass RLS) plus `request.jwt.claims`; run probe queries; log violations to stdout. | Use `system_pool` as designed. |
| `enforce` | Execute under `app_authenticated`; rely on RLS. | Use `system_pool` as designed. |

### Shadow-violation log entry

JSON object emitted to stdout by `observability/shadow_log.py`. Schema in `contracts/shadow-violation-event.md`. Rate-limit + dedupe rule: deduplicate on the tuple `(route, table, policy_name?)` within a 60-second window per process; emit a single rolled-up entry with a `count` field rather than N raw entries.

## State transitions

This phase introduces no debt-lifecycle transitions and no user-data state changes. The only "state machine" added is the `RLS_MODE` flag (off → shadow → enforce, with the operator able to revert at any time).

## Validation rules

- A request must not reach the repository layer without `current_request_jwt` set; the middleware rejects unauthenticated requests at the router boundary as it does today, and the helper additionally raises if it sees no claims.
- The probe query in shadow mode runs only on tables on a small allow-list (the user-data tables above); never on `auth.*` or `storage.*`.
- New migrations after this phase MUST `ENABLE ROW LEVEL SECURITY` on any new user-data table and add at least one policy. CI lint rule (housekeeping follow-up) is recommended but not in scope here.

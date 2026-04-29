# Feature Specification: Backend RLS Enforcement (stop running as Postgres role)

**Feature Branch**: `010-backend-rls-enforcement`
**Created**: 2026-04-29
**Status**: Draft
**Input**: User description: "Phase 10 — Backend stops running as Postgres role"

## Clarifications

### Session 2026-04-29

- Q: Should public-preview endpoints (QR-resolve and similar) work via a narrowly scoped RLS policy, an entry on the elevated session allow-list, or a `SECURITY DEFINER` function? → A: Narrowly scoped RLS policy — endpoint stays on the request-scoped session; new policy expresses the public-preview field-set constraint in SQL.
- Q: Where do the RLS negative tests live and how do they run in CI? → A: New `backend/tests/rls/` suite forced to `REPOSITORY_TYPE=postgres`, executed as a dedicated CI job against Supabase local (Docker). Existing in-memory test suite is untouched.
- Q: What is the granularity of the enforcement-mode flag (off / shadow / enforce)? → A: Single global flag, applied uniformly to all request-scoped queries. No per-table or per-route overrides.
- Q: Where do shadow-violation entries land and how is "zero violations" verified? → A: Structured JSON to stdout/stderr captured by the existing app log pipeline. No dedicated table or separate retention policy. SC-002 is verified by asserting no shadow-violation entries appear during the E2E run's log window.
- Q: How is the SC-004 latency budget measured? → A: Aggregate wall-clock duration of the canonical E2E suite, pre-change vs post-change. SC-004 passes if post-change duration is ≤ 110% of the pre-change baseline.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Database enforces per-user data isolation independently of handler logic (Priority: P1)

A user issues an authenticated API request that reaches a backend handler. Even if that handler forgets to filter results by the caller's identity, the database itself must refuse to return rows belonging to other users. Today, the backend connects with a privileged role that bypasses Row-Level Security (RLS), so a single missing authorization check in handler code leaks cross-user data. After this change, the database is the authoritative authorization boundary: the backend executes queries under a request-scoped identity that triggers existing RLS policies, and any leak attempt fails at the database layer.

**Why this priority**: This is the core hardening goal of the phase and a constitution §4 requirement. Without it, every router file is a single point of failure; with it, defense-in-depth is restored. Stories 2 and 3 only matter if Story 1 is delivered.

**Independent Test**: A negative test deliberately strips the per-record authorization check from one handler (e.g., the debt-detail handler), then issues a request from User A for User B's resource. The response must contain no leaked data — either an empty result, 404, or 403. The test passes purely on RLS, with handler-level filtering removed.

**Acceptance Scenarios**:

1. **Given** User A is authenticated and User B owns a debt that is not shared with A, **When** A calls a handler whose authorization filter has been removed, **Then** the response contains no rows belonging to B.
2. **Given** User A is authenticated as creditor on debt D, **When** A reads debt D through the normal handler, **Then** A receives D's full payload with the same latency budget as before the change (within 10%).
3. **Given** an unauthenticated request reaches a user-scoped endpoint, **When** the request is processed, **Then** RLS denies access regardless of handler-level checks.
4. **Given** User A and User B are both accepted members of group G with a shared debt, **When** A reads the group debts endpoint, **Then** A sees the group-tagged debt that B is party to (group privacy relaxation continues to work under RLS).

---

### User Story 2 - System tasks that legitimately need elevation continue to function (Priority: P1)

A small set of internal jobs cannot run as a regular user — most importantly the lazy commitment-score sweeper that updates `profiles.commitment_score` on debt-list reads, and any background-style triggers (e.g., `handle_new_user`). These jobs need a documented escape hatch that runs under a privileged identity, isolated from request-scoped traffic. Operators must be able to tell at a glance which code paths run elevated and why.

**Why this priority**: Without this, flipping RLS on breaks the commitment-indicator feature and signup. Tied for P1 with Story 1 because they ship together — one without the other is a regression.

**Independent Test**: The lazy sweeper runs against a fixture where the request user lacks rights to update `profiles.commitment_score` directly; the sweeper still applies the penalty/bonus deltas because it executes through the elevated session factory.

**Acceptance Scenarios**:

1. **Given** a debt has an unpaid reminder date in the past, **When** any user reads their debt list and the lazy sweeper fires, **Then** the corresponding `commitment_score_events` row is written and `profiles.commitment_score` is decremented, even though the request user has no direct write permission on `profiles`.
2. **Given** a new user signs up, **When** the auth trigger inserts a `profiles` row, **Then** the row is created without RLS denying the insert.
3. **Given** a developer reviews the codebase, **When** they look for elevated code paths, **Then** every elevated call site is reachable from a single, documented session factory and the list of allowed elevated operations is finite and reviewable.

---

### User Story 3 - Safe rollout via shadow mode before enforcement (Priority: P2)

Before flipping RLS on for real, operators run the system in a "shadow" mode where every query that *would* be denied under RLS is logged but still allowed. Engineers iterate on policy gaps using the shadow log until one full end-to-end run produces zero shadow violations; only then is enforcement turned on.

**Why this priority**: De-risks the rollout. Without this, the team flips a switch and discovers gaps in production. Lower priority than 1 and 2 because shadow mode is the rollout *mechanism*, not the destination state.

**Independent Test**: Run the canonical happy-path E2E (Phase 4 demo script) with shadow mode active. The shadow log must be empty. Disable handler-level authorization in one handler and rerun: shadow log records the denial that would have occurred.

**Acceptance Scenarios**:

1. **Given** shadow mode is enabled, **When** a request executes a query that would be denied by an RLS policy, **Then** the query still returns its rows but a structured shadow-violation entry is logged with enough context to identify the offending policy and route.
2. **Given** the team has cleared all shadow violations, **When** enforcement is enabled, **Then** the same E2E suite passes with no behavioral changes.
3. **Given** enforcement is enabled, **When** an unanticipated denial occurs in production, **Then** the operator can flip a single configuration value to revert to shadow mode without redeploying code.

---

### Edge Cases

- A request arrives with a valid token whose claims have been revoked (user deleted): RLS evaluation must treat the caller as unauthenticated and deny, rather than match stale rows by claim values.
- Connection pooling reuse: a request that completes must not leak its scoped identity to the next request reusing the same physical connection. The scoped identity must be reset before the connection returns to the pool.
- A handler that legitimately needs to read across users (e.g., the QR-resolve preview that returns a public-ish profile snippet) must continue to work — either via a narrowly scoped RLS policy, a documented elevated path, or by querying only fields exposed by such a policy.
- Mixed-mode period: while shadow mode is active, log volume could spike if a hot-path handler is missing a policy. The shadow logger must rate-limit or deduplicate so it cannot become a denial-of-service vector against the logging pipeline.
- A database migration that adds a new table: the table must default to RLS-enabled with a deny-all policy so a forgotten policy fails closed, not open.
- Connection-pool transaction-pooling mode may strip session-scoped settings between statements; the chosen scoping mechanism must work under the pooler configuration the project uses, or the path must opt into a session-pooled connection.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The backend MUST execute every request-scoped database query under a non-privileged identity that is subject to existing RLS policies, derived from the authenticated caller's verified token claims.
- **FR-002**: The backend MUST set the request-scoped identity transparently via shared infrastructure (middleware or equivalent), so individual route handlers cannot accidentally bypass it by writing a query the normal way.
- **FR-003**: The backend MUST reset the request-scoped identity at the end of each request so connection reuse cannot leak one user's scope into another's request.
- **FR-004**: The backend MUST provide a separate, clearly named elevated session factory for system tasks (lazy commitment-score sweeper, signup trigger, future cron-like jobs) that explicitly opt in to bypassing RLS.
- **FR-005**: The set of code paths permitted to use the elevated session factory MUST be finite, documented in code, and reviewable in one place.
- **FR-006**: Unauthenticated requests reaching a user-scoped query MUST be denied at the database layer regardless of handler-level checks.
- **FR-007**: The system MUST support a shadow mode in which RLS denials are logged but not enforced, controlled by configuration that can be toggled without redeploying code.
- **FR-008**: When shadow mode is active, every query that would be denied MUST produce a structured JSON log entry written to stdout/stderr (captured by the existing application log pipeline), containing at minimum the affected table, the policy name (if known), the route or task that issued the query, and the caller identity. No dedicated database table is created for these entries; standard application log retention applies.
- **FR-009**: When enforcement mode is active, denials MUST surface to the API caller as the same not-found or forbidden responses already used by handler-level checks, so client-visible behavior does not change for legitimate access patterns.
- **FR-010**: Existing RLS policies MUST be revisited and gaps closed before enforcement is enabled, so that no current legitimate access pattern is broken when the switch is flipped.
- **FR-011**: A negative test suite MUST prove enforcement: at least one test removes a handler-level authorization filter and asserts that cross-user data still cannot be retrieved. The suite MUST live under `backend/tests/rls/`, MUST run with `REPOSITORY_TYPE=postgres` against a Supabase local instance, and MUST execute as its own CI job, separate from the existing in-memory test suite.
- **FR-012**: New tables introduced by future migrations MUST default to RLS-enabled with a deny-all baseline policy, so forgotten policies fail closed.
- **FR-013**: Aggregate wall-clock duration of the canonical happy-path E2E suite under enforcement MUST remain within 110% of the pre-change baseline duration captured on the same machine and dataset immediately before this work begins.
- **FR-014**: The QR-resolve and any other "public preview" endpoints MUST continue to work via a narrowly scoped RLS policy that lets the request-scoped session read only the public-preview field set under the same conditions the endpoint already enforces (e.g., valid, unexpired QR token; authenticated caller). The endpoint MUST stay on the request-scoped session — no elevated path — and MUST NOT expose any field outside its current contract.
- **FR-015**: The shadow-violation logger MUST be resilient against high-volume bursts (rate-limit or dedupe) so that a missing policy on a hot path cannot disable the logging pipeline.

### Key Entities *(include if feature involves data)*

- **Request-scoped database identity**: The non-privileged identity (and associated claims) under which a single API request's queries execute. Bound to one request, reset before connection reuse.
- **Elevated session factory**: A separate, explicitly opted-into mechanism for issuing queries that legitimately need to bypass RLS (e.g., lazy commitment-score sweeper, signup trigger). Its allow-list is small, finite, and reviewed.
- **Shadow-violation log entry**: A structured record produced when RLS would deny a query in shadow mode. Includes table, policy (if identifiable), route or task name, and caller identity. Used to drive the rollout to zero violations before enforcement.
- **Enforcement-mode flag**: A single global configuration value with three states (off / shadow / enforce) that controls runtime behavior uniformly across all request-scoped queries. Toggleable without redeploying code. No per-table or per-route overrides — incremental rollout is achieved through the shadow-mode iteration loop, not through partial enforcement.
- **RLS baseline policy for new tables**: A repository convention that every new user-data table ships with RLS enabled and a deny-all default, so policy authors must opt access in rather than out.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A handler whose per-record authorization filter has been deliberately removed in tests returns zero leaked rows on cross-user requests, demonstrated by automated tests that exist on every CI run.
- **SC-002**: One full canonical E2E run produces zero shadow-mode violation entries in the application log output before enforcement is enabled, verifiable by scanning the run's log window for the structured shadow-violation event type.
- **SC-003**: After enforcement is enabled, the canonical E2E suite passes with no behavioral changes visible to API callers.
- **SC-004**: Aggregate wall-clock duration of the canonical happy-path E2E suite under enforcement is ≤ 110% of the pre-change baseline duration captured on the same machine and dataset immediately before this work begins.
- **SC-005**: 100% of identified system-task code paths that need elevation route through the documented elevated session factory; zero direct uses of a privileged connection remain elsewhere in request-scoped code.
- **SC-006**: Operators can revert from enforcement to shadow mode in under one minute by toggling configuration, without a code deploy.
- **SC-007**: Every user-data table introduced after this phase ships with RLS enabled and a deny-all baseline policy by default.

## Assumptions

- The deployment uses Supabase Postgres with RLS already enabled on user-data tables (per migrations 001 and 002); this phase changes how the backend connects, not whether the policies exist.
- The verified caller identity comes from a Supabase-issued JWT validated by existing backend security code (`core/security.py`); this phase reuses that validation rather than reimplementing it.
- Connection pooling is provided by `psycopg_pool.ConnectionPool` directly inside the FastAPI process; there is no PgBouncer between the backend and Supabase Postgres in the current deployment. `SET LOCAL` + `SET LOCAL ROLE` inside a per-request transaction is therefore safe. If a future deployment introduces a pooler in transaction-pooling mode, the chosen identity-scoping mechanism must be re-evaluated and the affected paths must opt into a session-pooled connection.
- The lazy commitment-score sweeper, the `handle_new_user` trigger, and any pre-existing cron-like sweepers are the known elevated paths today. New elevated paths added during this work will be enumerated explicitly in the implementation plan.
- The in-memory repository (`REPOSITORY_TYPE=memory`) used by tests is not affected by this change. RLS-related tests live in `backend/tests/rls/`, run with `REPOSITORY_TYPE=postgres` against Supabase local, and execute as a separate CI job — the existing in-memory suite remains the fast default for unrelated tests.
- The latency comparison is aggregate wall-clock duration of the canonical happy-path E2E suite, captured on the same machine and dataset, immediately before this work begins (baseline) and after enforcement is enabled (post-change). The "within 10%" budget means post-change duration ≤ 110% of baseline.
- Public-preview endpoints (e.g., QR-resolve) already restrict the fields they return; this phase preserves that contract and does not widen exposure.
- The shadow-mode logging sink reuses the existing application logging infrastructure; no new log storage system is introduced by this phase.

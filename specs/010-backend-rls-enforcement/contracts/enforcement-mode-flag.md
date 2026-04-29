# Contract: Enforcement-Mode Flag (`RLS_MODE`)

## Identity

- **Name**: `RLS_MODE`
- **Type**: environment variable, string
- **Allowed values**: `off`, `shadow`, `enforce`
- **Default per environment**:
  - Local development (`APP_ENV=local`): `off` until shadow has been verified once locally; then developers may opt-in by setting `RLS_MODE=enforce`.
  - Staging (`APP_ENV=staging`): `shadow` initially; flip to `enforce` once SC-002 is met.
  - Production (`APP_ENV=production`): `shadow` for one full release cycle; `enforce` thereafter.
- **Tests**: the `backend/tests/rls/` suite pins the value explicitly per test (e.g., a fixture sets `enforce` for negative isolation tests, `shadow` for shadow-log tests).

## Semantics

| Value | Request-scoped query path | System task path | Visible API behavior |
|---|---|---|---|
| `off` | Connection runs as the legacy privileged role. No `SET LOCAL` applied. | Uses `system_pool`. | No change vs. pre-Phase-10. |
| `shadow` | Connection runs as `app_service` (bypass RLS) with `request.jwt.claims` set. Probe queries re-run access under `app_authenticated` and log violations. | Uses `system_pool`. | Identical to `off` from the API caller's perspective; observable difference is only in logs. |
| `enforce` | Connection runs as `app_authenticated` with `request.jwt.claims` set. RLS gates every read/write. | Uses `system_pool`. | Existing legitimate access patterns: identical responses. Cross-user access from a stripped handler: returns empty / 404. |

## Toggle requirements

- The flag MUST take effect on the **next request** after the env var is changed and the process is signaled (or restarted, depending on deployment style). No code deploy required.
- Operators MUST be able to revert from `enforce` to `shadow` (or `off`) within one minute by changing the env var and signaling the process (SC-006).
- The flag is read per-request via `get_settings()`. Calls to `get_settings()` are cached by `@lru_cache`; the cache is invalidated on `SIGHUP` (handler added in `main.py`).

## Failure modes

- **Unrecognized value**: app refuses to start with a startup-time error naming the env var and the allowed set.
- **`enforce` without `app_authenticated` role present in the database**: app refuses to start (sanity-check query during pool warm-up).
- **`shadow` without `app_service` role present**: app refuses to start.

## Observability

- On startup and on every `SIGHUP`, the app emits one structured log entry: `{ event: "rls.mode_changed", from, to, timestamp }`.
- The current value is exposed via `GET /api/v1/healthz` (already exists) under a new field `rls_mode`. No auth required to read; value is non-sensitive.

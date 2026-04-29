# Contract: Shadow Violation Event

Structured log entry emitted to **stdout** when `RLS_MODE=shadow` and a probe query indicates that the request would have been denied under `enforce`.

## Event shape

```json
{
  "event": "rls.shadow_violation",
  "timestamp": "2026-04-29T14:03:22.117Z",
  "request_id": "8e7d4f0a-...-c1",
  "route": "GET /api/v1/debts/{id}",
  "method": "GET",
  "table": "debts",
  "policy": "debts_party_select",
  "caller_id": "5f2c...-77",
  "claim_role": "authenticated",
  "query_signature": "select:debts:by_id",
  "would_have_returned_rows": 1,
  "count": 1
}
```

### Field semantics

| Field | Required | Type | Description |
|---|---|---|---|
| `event` | yes | string (literal `"rls.shadow_violation"`) | Discriminator for log filtering. |
| `timestamp` | yes | ISO 8601 string (UTC, ms precision) | When the probe detected the would-be denial. |
| `request_id` | yes | string | Per-request UUID. Already set by existing request-id middleware. |
| `route` | yes | string | FastAPI route template (not the raw URL — avoids logging IDs unintentionally as part of the route). |
| `method` | yes | string | HTTP method. |
| `table` | yes | string | Postgres table the violation was detected on. |
| `policy` | no | string | Policy name when identifiable; omitted if the probe couldn't attribute the denial to a specific policy. |
| `caller_id` | yes | string | The caller's user id from `request.jwt.claims.sub`. |
| `claim_role` | yes | string | The `role` claim from the JWT (e.g., `authenticated`, `anon`). |
| `query_signature` | yes | string | A short stable identifier of the source query (e.g., `select:debts:by_id`). Generated at the call site, not derived from raw SQL. |
| `would_have_returned_rows` | yes | integer | Number of rows the real (bypass-RLS) query returned but the probe denied. |
| `count` | yes | integer (≥1) | Dedupe count: how many violations this entry represents within the dedupe window. `1` for non-deduplicated entries. |

## Dedupe + rate-limit

- **Dedupe key**: tuple `(route, table, policy)` (with `policy` defaulting to the empty string when missing).
- **Window**: 60 seconds, per-process.
- Within a window, the first violation matching a key is emitted immediately; subsequent matches increment a counter. When the window closes (or the process is shutting down), a single rolled-up entry is emitted with the final `count`.
- This protects the log pipeline from a hot-path policy gap turning into a denial-of-service against logging (FR-015).

## Consumption

- **CI / E2E pipeline**: the canonical happy-path E2E run greps the captured log for `"event":"rls.shadow_violation"`. SC-002 passes iff the count is zero.
- **Operators**: same grep against staging/prod log aggregator. The dashboard is left to whatever the existing log infrastructure provides; no new dashboard is in scope.

## Non-goals

- Long-term storage / queryability — explicitly out of scope per Q4 of the clarification session.
- Per-statement source-line attribution — `query_signature` plus `route` is sufficient for "find the gap and add the policy".

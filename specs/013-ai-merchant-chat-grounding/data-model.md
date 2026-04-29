# Phase 1 Data Model — AI Merchant-Chat Grounding

**Branch**: `013-ai-merchant-chat-grounding` · **Date**: 2026-04-30

This feature introduces **no new persisted entities**. The only durable state it touches is the existing `ai_usage` row keyed by `(user_id, feature, usage_date)`, with a new feature value `merchant_chat`.

The entities below are **request/response shapes** and **in-process value objects** that flow through the orchestrator on each call.

---

## Persisted state (existing — no schema change)

### `ai_usage`

Already defined by Phase 12. We add a new permitted value of the `feature` column at the application layer; no DB migration is required because the column is `text` and tests already cover insertion of arbitrary feature strings.

| Field | Type | Notes |
|---|---|---|
| `user_id` | uuid | Caller. |
| `feature` | text | New value: `"merchant_chat"`. |
| `usage_date` | date | Local date in caller's timezone (matches existing pattern). |
| `count` | int | Incremented after each successful merchant-chat turn. |

Quota check: `count >= settings.ai_merchant_chat_daily_limit` → 429.

---

## Request / response shapes (extended)

### `MerchantChatRequest` (extended in `backend/app/schemas/domain.py`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `message` | str (min_length=1) | yes | The current user turn. |
| `history` | list[`ChatTurn`] | no, default `[]` | Prior turns supplied by the client. The orchestrator trims to the last 10 entries; anything beyond is silently dropped. |
| `locale` | `"ar"` \| `"en"` | no, default `"ar"` | Hint for the assistant's reply language; assistant ultimately mirrors the language of `message`. |
| `timezone` | str (IANA) | no, default `"Asia/Riyadh"` | Used by the time-resolver. Validated against the `zoneinfo` registry; invalid values fall back to the default with a warning logged. |

### `ChatTurn`

| Field | Type | Notes |
|---|---|---|
| `role` | `"user"` \| `"assistant"` | |
| `content` | str | Assistant turns include only the visible answer text (no tool traces). |

### `MerchantChatOut` (extended)

| Field | Type | Notes |
|---|---|---|
| `answer` | str | The assistant's reply, in the caller's chosen language (FR-010). |
| `facts` | dict[str, Any] | **Kept** for backward-compatibility with the existing handler / tests. Populated from `repo.merchant_facts(user.id)` — same as today. |
| `tool_trace` | list[`ToolTraceEntry`] \| None | Optional, only included when `APP_ENV != production`, for debugging. |

### `ToolTraceEntry`

| Field | Type | Notes |
|---|---|---|
| `tool` | str | One of: `list_debts`, `get_debt`, `get_dashboard_summary`, `get_commitment_history`. |
| `outcome` | `"ok"` \| `"error"` \| `"empty"` | |
| `duration_ms` | int | |

Note: `tool_trace` never includes arguments or returned row contents (FR-009).

---

## Tool catalogue (in-process; not over the wire)

Each tool is a Python function in `backend/app/services/ai/merchant_chat/tools.py`. The Anthropic SDK exposes them via `tools=[...]`. All tools take the caller's `user_id` implicitly (closed over at orchestrator construction) — the model never supplies it.

### `list_debts(filter)`

Input fields the model may set:

| Field | Type | Notes |
|---|---|---|
| `role` | `"creditor"` \| `"debtor"` \| `"any"` | Default `"any"`. |
| `status` | list[DebtStatus] | Empty = all statuses. |
| `counterparty_name_query` | str \| None | Substring match (case-insensitive). |
| `from_date` | date \| None | Inclusive; in caller tz. |
| `to_date` | date \| None | Exclusive upper bound. |
| `min_amount` / `max_amount` | Decimal \| None | |

Output:

| Field | Type | Notes |
|---|---|---|
| `rows` | list[`DebtRow`] | At most 20 (FR-005a). |
| `total_count` | int | Exact count of all matching rows for the caller. |
| `total_sum` | Decimal | Exact sum of `amount` across all matching rows. |
| `truncated` | bool | True iff `total_count > len(rows)`. |

### `DebtRow`

| Field | Type |
|---|---|
| `id` | uuid |
| `creditor_name` | str |
| `debtor_name` | str |
| `amount` | Decimal |
| `currency` | str (3-char ISO) |
| `status` | DebtStatus |
| `created_at` | datetime |
| `due_date` | date \| None |
| `paid_at` | datetime \| None |

Implementation must call `repo.list_debts_for_user(user_id, ...)` (already exists or will be added wrapping existing list endpoints) — never a service-role query.

### `get_debt(debt_id)`

Returns a single `DebtRow` (or `None` if not found / not authorised). Backed by `repo.get_authorized_debt(user_id, debt_id)`.

### `get_dashboard_summary()`

Returns the same payload `repo.merchant_facts(user_id)` already produces:

| Field | Type |
|---|---|
| `outstanding_count` | int |
| `outstanding_sum` | Decimal |
| `overdue_count` | int |
| `overdue_sum` | Decimal |
| `paid_last_30d_count` | int |
| `paid_last_30d_sum` | Decimal |
| `alerts` | list[str] |

### `get_commitment_history(counterparty_id?)`

Returns the **caller's own** commitment-score events plus, optionally, the score history of a counterparty the caller has ever transacted with (gated by repo). Output:

| Field | Type | Notes |
|---|---|---|
| `current_score` | int | 0–100. Of the caller (or the named counterparty if provided and authorised). |
| `events` | list[`CommitmentEvent`] | Newest first; cap 20 (FR-005a). |
| `total_events` | int | Exact count. |

### `CommitmentEvent`

| Field | Type | Notes |
|---|---|---|
| `delta` | int | E.g. +3, −2, −4. |
| `kind` | str | E.g. `paid_before_due`, `missed_reminder`, `late_payment`, `overdue_sweep`. |
| `at` | datetime | |
| `debt_id` | uuid \| None | |

---

## Time-resolver value objects

### `ResolvedRange`

| Field | Type | Notes |
|---|---|---|
| `start` | datetime (tz-aware) | Inclusive. |
| `end` | datetime (tz-aware) | Exclusive. |
| `phrase` | str | E.g. `"last month"`, `"this week"`. |
| `human` | str | Pre-formatted human label, e.g. `"March 2026"`. Used inside the model prompt's "current context" block. |

The resolver is pure-functional and takes `(now: datetime, tz: ZoneInfo, phrase: str)`; it covers `today`, `yesterday`, `this week`, `last week`, `this month`, `last month`, `this year`, `last 7 days`, `last 30 days`. Unknown phrases return `None` and the model must answer without a date filter or ask.

---

## Validation rules

- `MerchantChatRequest.message`: 1 ≤ len ≤ 4000 chars; reject longer (HTTP 422).
- `MerchantChatRequest.history`: server-side trim to last 10; reject single turn > 4000 chars (HTTP 422).
- `MerchantChatRequest.timezone`: must parse via `zoneinfo.ZoneInfo`; otherwise default to `Asia/Riyadh` and log a warning. Do not 422 — better UX to answer than to error.
- Tool inputs are validated with Pydantic before being forwarded to the repository; invalid inputs return a structured tool error to the model so it can recover (`{"error": "invalid_filter", "message": "..."}`), not a 500 to the user.

---

## State transitions

None. The chat is read-only. No `debt_events` rows are written, no debt status changes.

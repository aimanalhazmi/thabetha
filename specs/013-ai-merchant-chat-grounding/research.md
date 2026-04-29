# Phase 0 Research — AI Merchant-Chat Grounding

**Branch**: `013-ai-merchant-chat-grounding` · **Date**: 2026-04-30

The Technical Context in `plan.md` had a small set of choice points that needed evidence-based resolution. Each section below is one decision in the canonical Decision / Rationale / Alternatives format.

---

## R1. Grounding strategy: tool-use vs. RAG

- **Decision**: Tool-use. The model is given a fixed catalogue of caller-scoped tools (`list_debts`, `get_debt`, `get_dashboard_summary`, `get_commitment_history`) and chooses which to call to answer each question.
- **Rationale**:
  - The ledger is fully structured already (Postgres rows). Embedding rows into a vector store would re-encode information we already have in normalised form, with no win.
  - Tool-use inherits per-user isolation for free: tools call `repo.<method>(user.id, ...)`, so a model "hallucinating" another user's identifier still cannot retrieve their data — the repository contract refuses.
  - Tool traces are auditable: we log tool name + outcome (FR-009) without leaking arguments or row contents.
  - Numeric fidelity (SC-001) is the SC that matters most. Tool-use gives the model literal numbers to repeat back instead of approximate text.
- **Alternatives**:
  - **RAG over `debt_events` text** — rejected. Answers would be paraphrased rather than exact, breaking SC-001. Also harder to scope to caller (would need filtering inside the vector store).
  - **One mega-tool returning the whole ledger** — rejected. Bigger context, worse precision, and large ledgers exceed token budgets.

## R2. LLM provider

- **Decision**: Anthropic Claude Sonnet 4.6 (`claude-sonnet-4-6`) for tool-use. Behind a `MerchantChatProvider` interface so a `mock` implementation drives tests.
- **Rationale**:
  - Sonnet 4.6 is the current cost/quality sweet spot for non-vision tool-use. Opus 4.7 is overqualified for "look up two ledger rows and respond"; Haiku 4.5 occasionally under-explains in Arabic.
  - Claude has strong native Arabic generation, and the implementation plan flags Anthropic vision elsewhere in Block 3 — keeping providers consistent simplifies dependency footprint (`anthropic` SDK already arrives with Phase 11 receipt extraction).
  - Provider abstraction is a one-file delta and matches the existing `WhatsAppProvider` and `get_transcription_provider()` pattern.
- **Alternatives**:
  - **OpenAI gpt-4o** — rejected for now. We already standardise on Anthropic for receipt extraction in Phase 11; mixing providers doubles secrets / billing surface for hackathon-scale value.
  - **Locally hosted model** — rejected. Out of scope for a paid tier and quality not competitive with Sonnet on Arabic tool-use.

## R3. Conversation history management

- **Decision**: Stateless backend; client owns history; per-request payload includes the trailing 10 turns.
- **Rationale**:
  - Pre-answered in spec; matches the implementation plan's directive ("Maintained per-call by the client (stateless on backend). Last 10 turns only.").
  - No new persistence, no GDPR/PII surface beyond the existing per-request log.
  - Trivially supports the "clear chat" UX (just drop the local array).
- **Alternatives**:
  - **Server-side session with TTL** — rejected. Adds a table, a sweeper, and an export-on-account-deletion concern, with no user-facing benefit at this scale.

## R4. Quota & gating reuse

- **Decision**: Reuse `_require_ai_enabled(user, repo)` for tier gating and `ensure_ai_quota_available(repo, user.id, feature="merchant_chat")` for daily quota. Add a new feature key `merchant_chat`. Default daily limit 50, configurable via new `ai_merchant_chat_daily_limit` setting.
- **Rationale**:
  - The infrastructure already exists from Phases 11–12 (`backend/app/services/ai/limits.py`, `ai_usage` table). Generalising `limits.py` to take a feature key is a one-line change; the table already keys by `(user_id, feature, usage_date)`.
  - Same numeric default (50/day) keeps user-facing copy and ops dashboards consistent.
  - 403 vs. 429 paths get a single source of truth.
- **Alternatives**:
  - **Token-based quota** — rejected. Harder to communicate to users ("you have 47 tokens left") and not actually cheaper for our scale.

## R5. Tool result-row cap (FR-005a)

- **Decision**: List-style tools cap at **20 rows**, ordered by `amount DESC, created_at DESC`. The tool always returns `total_count` and `total_sum` exactly; if `total_count > 20`, the response includes `truncated: true` and the assistant must say "showing top 20 of {total_count}".
- **Rationale**:
  - 20 is a reasonable upper bound for a chat answer the user reads on a phone screen.
  - Aggregate count + sum stay exact, preserving SC-001 even when the row list is abridged.
  - Sorting by amount surfaces the most consequential debts first, matching what a creditor cares about ("who owes me the most" → top-N is the useful slice).
- **Alternatives**:
  - **No cap** — rejected. Risk of token blow-ups on noisy ledgers.
  - **Pagination cursor** — rejected. Chat UX doesn't naturally page; aggregates suffice.

## R6. Time-window resolution (FR-013)

- **Decision**: Resolve relative phrases ("last month", "this week", "today", "this year", "last 7 days") in the caller's local timezone using the Gregorian calendar. The orchestrator does this resolution **before** invoking the model, then injects the absolute (start, end) range as part of the prompt's "current context" block, so the model passes the same range to tools rather than guessing.
- **Rationale**:
  - Determinism: SC-001 (100% numeric fidelity) is impossible if "last month" can drift between UTC and local time.
  - Caller's local tz matches how merchants reason about cash-flow periods.
  - Pre-resolving server-side prevents the model from doing date arithmetic, which is its weakest skill.
- **Alternatives**:
  - **Ask the model to resolve dates** — rejected. Worse accuracy, especially across DST/Hijri-adjacent edge cases.
  - **Server resolves only when asked** — rejected. Fragile; better to always inject "now (caller tz): 2026-04-30 14:32 +03:00" so the model never has to guess.

## R7. Streaming

- **Decision**: Non-streaming for this phase. The endpoint returns the final answer plus a tool-call trace.
- **Rationale**: Pre-answered in spec. Adds frontend complexity (SSE wiring, partial-answer rendering) for a feature whose typical answer is 1–3 sentences. Reconsider after telemetry if median latency drifts past 5 s.
- **Alternatives**: SSE / chunked responses — deferred to a follow-up phase if needed.

## R8. Logging & observability

- **Decision**: Log per-turn:
  - `merchant_chat.start { user_id_hash, message_lang, history_len }`
  - `merchant_chat.tool { user_id_hash, tool: "list_debts", outcome: "ok"|"error", duration_ms }` — one line per tool invocation, no args, no row contents
  - `merchant_chat.end { user_id_hash, tool_count, total_duration_ms, answer_lang }`
- **Rationale**: Satisfies FR-009 without leaking ledger contents. `user_id_hash` (HMAC of user_id with a per-deploy salt) lets us join across logs without exposing raw IDs.
- **Alternatives**:
  - **Log full prompts** — rejected for privacy.
  - **No logging** — rejected; we need tool-failure visibility.

## R9. Provider failure handling

- **Decision**: A provider error (network, 5xx from Claude, malformed tool-use) returns HTTP 503 with `{"code": "ai_provider_unavailable", "message": "..."}` and **does not consume quota**. Frontend shows a translated transient-error message.
- **Rationale**: Matches the spec's edge case ("Network/model failure mid-turn → … quota is not consumed for failed turns"). Quota is incremented only after a successful final answer is produced.
- **Alternatives**:
  - **Increment quota up front** — rejected; charging a user for a failed turn is a support ticket waiting to happen.

---

## Open items (deferred to plan/tasks)

- Exact prompt text for the system message (how to phrase "you may only use these tools; never invent data; respond in the caller's language") — drafted in `tasks.md`.
- Whether to expose `tool_trace` in the public API response — kept internal for now (debug-only when `APP_ENV != production`); the public `MerchantChatOut` shape stays `{answer, facts}` plus the new optional `tool_trace`.

All NEEDS CLARIFICATION from the Technical Context are now resolved.

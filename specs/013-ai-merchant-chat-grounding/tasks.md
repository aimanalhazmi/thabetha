# Tasks — AI Merchant-Chat Grounding

**Branch**: `013-ai-merchant-chat-grounding` · **Date**: 2026-04-30
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

User stories from spec.md (priority-ordered):

- **US1 (P1)**: Grounded ledger Q&A for the caller
- **US2 (P1)**: Cross-user data isolation
- **US3 (P2)**: Multi-turn conversation continuity
- **US4 (P2)**: Daily quota and tier gating

Tests are required per constitution §12 ("every new state transition or auth-affecting change ships with a `FastAPI.TestClient` test"). The merchant-chat endpoint is auth-affecting (gating + isolation), so tests are mandatory.

---

## Phase 1: Setup

- [~] T001 Deferred — `anthropic` SDK is **lazy-imported** inside `anthropic_provider.py` so `mock` (default) runs without the dep. Add to `pyproject.toml` only when switching `MERCHANT_CHAT_PROVIDER=anthropic` in production
- [X] T002 Add new settings to `backend/app/core/config.py`: `ai_merchant_chat_daily_limit: int = 50`, `merchant_chat_provider: Literal["anthropic", "mock", "stub"] = "mock"`, `anthropic_api_key: str | None = None`, `merchant_chat_model: str = "claude-sonnet-4-6"`, `merchant_chat_log_salt: str = "dev-salt"`
- [X] T003 Document the new env vars in `backend/.env.example` and root `.env.example` (`ANTHROPIC_API_KEY`, `MERCHANT_CHAT_PROVIDER`, `MERCHANT_CHAT_MODEL`, `AI_MERCHANT_CHAT_DAILY_LIMIT`, `MERCHANT_CHAT_LOG_SALT`)

---

## Phase 2: Foundational (blocking)

These tasks unblock every user story below. Complete them before starting Phase 3.

- [X] T010 Extend Pydantic schemas in `backend/app/schemas/domain.py`: add `ChatTurn`, extend `MerchantChatRequest` with `history: list[ChatTurn] = []`, `locale: Literal["ar", "en"] = "ar"`, `timezone: str = "Asia/Riyadh"`, `message: str = Field(min_length=1, max_length=4000)`; extend `MerchantChatOut` with `tool_trace: list[ToolTraceEntry] | None = None`; add `ToolTraceEntry`. Keep existing fields (`answer`, `facts`) for backward compatibility.
- [X] T011 [P] Mirror the new schema shapes in `frontend/src/lib/types.ts` (manual mirror, per constitution §VII)
- [X] T012 [P] Generalise `backend/app/services/ai/limits.py`: change `ensure_ai_quota_available` to look up the daily limit by `feature` (use `getattr(settings, f"ai_{feature}_daily_limit", settings.ai_voice_draft_daily_limit)`), add module-level `MERCHANT_CHAT_FEATURE = "merchant_chat"` constant, and ensure `record_ai_usage` accepts the same feature key
- [X] T013 [P] Create the new package `backend/app/services/ai/merchant_chat/` with empty `__init__.py`
- [X] T014 Create `backend/app/services/ai/merchant_chat/provider.py` defining `MerchantChatProvider` ABC, `ProviderMessage`, `ToolSpec`, `ToolCall`, `ToolResult`, `ProviderResponse` dataclasses (or Pydantic models). Include the `chat(...)` method that takes system prompt, message history, available tools, and returns either a final answer or a list of tool calls
- [X] T015 Create `backend/app/services/ai/merchant_chat/time_resolver.py` implementing `resolve(now: datetime, tz: ZoneInfo, phrase: str) -> ResolvedRange | None` for: `today`, `yesterday`, `this week`, `last week`, `this month`, `last month`, `this year`, `last 7 days`, `last 30 days` (FR-013, both AR and EN phrasing)
- [X] T016 Create `backend/app/services/ai/merchant_chat/tools.py` exposing four tool factories that close over `(repo, user_id)`:  `make_list_debts`, `make_get_debt`, `make_get_dashboard_summary`, `make_get_commitment_history`. Each must call only the caller-scoped repo methods (e.g. `repo.list_debts_for_user(user_id, ...)`, `repo.get_authorized_debt(user_id, debt_id)`, `repo.merchant_facts(user_id)`, `repo.get_commitment_history(user_id, counterparty_id=None)`). Each list-style tool enforces the 20-row cap and returns `{rows, total_count, total_sum, truncated}` (FR-005a). Add a small helper `hash_user_id(user_id: str) -> str` using HMAC-SHA256 with `settings.merchant_chat_log_salt`, returning the first 8 hex chars
- [X] T017 Add any missing repository methods discovered while writing T016. At minimum verify: `list_debts_for_user`, `get_authorized_debt`, `get_commitment_history`. If a method is missing on `Repository`, add the abstract method to `backend/app/repositories/base.py` and concrete implementations in both `repositories/memory.py` and `repositories/postgres.py`. Constitution §VII: change `base.py` first, then both implementations
- [X] T018 Create `backend/app/services/ai/merchant_chat/mock_provider.py` implementing `MerchantChatProvider`. Scripted tool-use keyed on keywords per the `quickstart.md` table (owes me / paid / overdue / commitment / no-match). Always returns the final natural-language answer in the requested locale
- [X] T019 Create `backend/app/services/ai/merchant_chat/anthropic_provider.py` implementing `MerchantChatProvider` using the `anthropic` SDK with `tools=[...]`, model `settings.merchant_chat_model`, max 4 tool-use round-trips, `max_tokens=1024`, `temperature=0.2`. Wrap network errors and raise `MerchantChatProviderError`
- [X] T020 Create `backend/app/services/ai/merchant_chat/orchestrator.py` exposing `run_merchant_chat(repo, user, payload) -> MerchantChatOut`. Steps: build system prompt (loaded from a constant — see T021), pre-resolve any time phrases in the user message + recent history into a "current context" block including `now (caller tz)`, build the tool catalogue via `tools.make_*`, select provider via `settings.merchant_chat_provider`, drive the tool-use loop (max 4 hops), build the answer + `tool_trace`, log per `merchant_chat.start|tool|end` lines (no args, no row contents), and call `record_ai_usage(repo, user.id, MERCHANT_CHAT_FEATURE)` only on success. Return `MerchantChatOut(answer=..., facts=repo.merchant_facts(user.id), tool_trace=...)`. Tool_trace is suppressed when `settings.app_env == "production"`
- [X] T021 Create `backend/app/services/ai/merchant_chat/system_prompt.py` exporting `SYSTEM_PROMPT` constant: a clear instruction set covering "answer only from tool results", "if no relevant data, say 'I don't have that information'", "use the term 'commitment indicator' / 'مؤشر الالتزام', never 'credit score'", "respond in the language of the most recent user message", "when a list is abridged, say 'showing top N of M'", "never reveal data about parties the caller is not associated with"
- [X] T022 Wire the new orchestrator into `backend/app/api/ai.py`: replace the body of the existing `merchant_chat` handler so it delegates to `orchestrator.run_merchant_chat(repo, user, payload)` after `_require_ai_enabled` and `ensure_ai_quota_available(..., feature=MERCHANT_CHAT_FEATURE)`. Keep the existing function signature and response model. On `MerchantChatProviderError`, raise `HTTPException(503, detail={"code": "ai_provider_unavailable", "message": "..."})` and **do not** call `record_ai_usage`

---

## Phase 3: User Story 1 — Grounded ledger Q&A (P1)

**Story goal**: A paid-tier creditor asks the three demo prompts and receives answers grounded in their seeded ledger, with exact figures.

**Independent test**: Seed a known ledger; send the three demo prompts via the FastAPI test client with `MERCHANT_CHAT_PROVIDER=mock`; assert top-debtor name + amount, paid-last-month dated answer (or "I don't have that information"), and overdue exposure number all match the seed.

- [X] T030 [P] [US1] Write `backend/tests/ai/test_merchant_chat_tools.py` exercising each of the four tools against `InMemoryRepository`: `list_debts` filter combinations, `get_debt` for caller-owned vs. unrelated debt id (returns None), `get_dashboard_summary` shape, `get_commitment_history` shape and event ordering
- [X] T031 [P] [US1] Write `backend/tests/ai/test_merchant_chat_time_resolver.py`: cover `last month` on a date in early/mid/late April 2026 → `2026-03-01..2026-04-01` in `Asia/Riyadh`; `today`, `yesterday`, `this week` (Sunday-anchored, regional convention); unknown phrase returns `None`
- [X] T032 [P] [US1] Write `backend/tests/ai/test_merchant_chat_grounding.py::test_demo_prompts`: with mock provider, three prompts ("who owes me the most?", "did Ahmed pay me last month?", "what's my overdue exposure?") return answers containing the exact seeded amounts and names
- [X] T033 [US1] Write `backend/tests/ai/test_merchant_chat_grounding.py::test_top_n_abridgement`: seed 25 active debts, ask "list my receivables" → response mentions "top 20 of 25" and the `tool_trace` shows `truncated=true` (assert via the dev-mode trace; production mode suppresses it)
- [X] T034 [US1] Write `backend/tests/ai/test_merchant_chat_grounding.py::test_no_data_returns_unavailable`: with no relevant ledger rows, prompt yields an answer containing the localized "I don't have that information" form (or its AR equivalent)
- [X] T035 [US1] Add demo seed augmentation in `backend/app/services/demo_data.py` (or the relevant seed module) ensuring the demo merchant has: 3 active debts (debtors A=500, B=1200, C=300 SAR), one paid debt with debtor "Ahmed" dated in the previous local-tz month, and 2 overdue debts totalling 800 SAR — matches spec acceptance scenarios. Only seeded when `SEED_DEMO_DATA=true`

---

## Phase 4: User Story 2 — Cross-user data isolation (P1)

**Story goal**: A caller cannot retrieve, infer, or have the assistant fabricate data about another user's ledger.

**Independent test**: Two users A and B with disjoint ledgers; authenticated as A, ask probes about B's data; assert no values from B's ledger appear in any response and the assistant explicitly declines.

- [X] T040 [P] [US2] Write `backend/tests/ai/test_merchant_chat_isolation.py::test_unrelated_user_id_returns_no_data`: caller A asks `get_debt` for a debt id that belongs only to B → tool returns `None`; assistant responds with the unavailable-information form
- [X] T041 [P] [US2] Write `backend/tests/ai/test_merchant_chat_isolation.py::test_counterparty_query_does_not_leak`: caller A asks "What does B owe to anyone?" → no values from B's ledger appear in the answer (assert by string match against B's seeded amounts and debtor names)
- [X] T042 [US2] Write `backend/tests/ai/test_merchant_chat_isolation.py::test_adversarial_probe_set`: 20 prompts that try to extract another user's data via various phrasings (debtor name, raw uuid, "all debts in the system", etc.) — all must return either a refusal or no-data response, and `tool_trace` outcomes must all be `empty` or `error` (never `ok` with leaked rows). Maps to SC-002
- [X] T043 [US2] Verify in `tools.py` (T016) and orchestrator (T020) that no tool path uses a service-role connection or any unscoped repo method. Add an assertion-comment noting the audit, and a focused unit test `test_merchant_chat_tools.py::test_tools_only_use_scoped_repo_methods` that monkey-patches `repo` to fail on any method ending in `_admin` or starting with `system_`

---

## Phase 5: User Story 3 — Multi-turn continuity (P2)

**Story goal**: Follow-up questions referencing prior turns ("and which is the oldest?") resolve correctly using the trailing 10 turns of client-supplied history.

**Independent test**: Send a 2-turn exchange; assert turn 2 references the prior result correctly. Send 12 turns of history; assert only the trailing 10 reach the provider.

- [X] T050 [P] [US3] Write `backend/tests/ai/test_merchant_chat_grounding.py::test_history_trim_to_last_10`: post a request with 15 history turns; assert the orchestrator's pre-provider message list includes only the trailing 10 (assertable via a mock-provider spy that records what it was given)
- [X] T051 [P] [US3] Write `backend/tests/ai/test_merchant_chat_grounding.py::test_followup_resolves_with_history`: turn 1 is "list my active debts", turn 2 is "and which is the oldest?" → mock provider answers with the earliest-by-`created_at` debt name from the seeded ledger
- [X] T052 [US3] In the mock provider (T018), implement a minimal "follow-up" branch that re-issues `list_debts(role=creditor, status=[active])` and picks the row with the smallest `created_at`, so the tests above pass deterministically

---

## Phase 6: User Story 4 — Tier gating + daily quota (P2)

**Story goal**: Free-tier callers receive 403; over-quota callers receive 429 with `Retry-After`; provider errors return 503 without consuming quota.

**Independent test**: Toggle `ai_enabled=false` → 403. Force `ai_usage.count` to the daily cap → 429 with translated copy. Force provider failure → 503 and `ai_usage.count` unchanged.

- [X] T060 [P] [US4] Write `backend/tests/ai/test_merchant_chat_quota.py::test_disabled_returns_403`: caller has `ai_enabled=false`; endpoint returns 403 with body `detail.code == "ai_not_enabled"`
- [X] T061 [P] [US4] Write `backend/tests/ai/test_merchant_chat_quota.py::test_quota_exhausted_returns_429`: pre-fill `ai_usage` at the cap; next call returns 429 with `Retry-After` header and `detail.code == "ai_daily_limit_reached"`
- [X] T062 [P] [US4] Write `backend/tests/ai/test_merchant_chat_quota.py::test_provider_error_returns_503_without_consuming_quota`: configure mock provider to raise `MerchantChatProviderError`; endpoint returns 503; `repo.get_ai_usage_count(user_id, "merchant_chat", today)` is unchanged
- [X] T063 [US4] Write `backend/tests/ai/test_merchant_chat_quota.py::test_successful_call_increments_quota_once`: one successful call → count goes from 0 to 1; a second successful call → count goes to 2

---

## Phase 7: Frontend wiring

These tasks light up the existing AI page surface. They depend on Phase 2 backend schemas being merged.

- [X] T070 [US1] Add new keys to `frontend/src/lib/i18n.ts` for both AR and EN: `chat_placeholder`, `chat_send`, `chat_clear`, `chat_no_data`, `chat_disabled`, `chat_quota_exceeded`, `chat_error_generic`, `chat_provider_unavailable`, `chat_showing_top_n_of_m`, `chat_history_trimmed`, `chat_locale_hint`
- [X] T071 [P] [US1] Add `postMerchantChat(message: string, history: ChatTurn[], locale: Locale, timezone: string)` in `frontend/src/lib/api.ts`, returning the typed `MerchantChatOut`
- [X] T072 [P] [US3] Create `frontend/src/components/ai/MerchantChatPanel.tsx`: input, scrollable transcript, send button, "clear chat" affordance, client-side trim of history to the last 10 turns before each call, locale derived from `AuthContext`, timezone derived from `Intl.DateTimeFormat().resolvedOptions().timeZone`
- [X] T073 [US1] Update `frontend/src/pages/AIPage.tsx` to render `MerchantChatPanel` for users where `ai_enabled` is true; render the existing voice-draft surface alongside (do not replace it). Show a translated disabled-state card when `ai_enabled` is false
- [X] T074 [US4] In `MerchantChatPanel`, surface `chat_quota_exceeded` (with `Retry-After`-derived hint) on 429, `chat_disabled` on 403, `chat_provider_unavailable` on 503, `chat_error_generic` for everything else. Errors must not append a user-visible turn to the transcript so retries don't pile up

---

## Phase 8: Polish & cross-cutting

- [X] T080 Update `claude-handoff/use-cases.md` row UC10 to mark merchant-chat grounding as ✅ (was 🟡 / placeholder)
- [X] T081 Update `claude-handoff/api-endpoints.md` to reflect the extended `MerchantChatRequest` and `MerchantChatOut` shapes plus the new 503 response
- [X] T082 Update `claude-handoff/project-status.md` — move "Phase 13 — Merchant-chat grounding" out of "In progress" / "Planned" into "Shipped"
- [X] T083 Run the full backend test suite: `cd backend && uv run pytest tests/ai/ -v` — all merchant-chat tests pass with `REPOSITORY_TYPE=memory` and `MERCHANT_CHAT_PROVIDER=mock`
- [X] T084 Run `cd backend && uv run ruff check --fix .` and `cd frontend && npm run typecheck` — both clean
- [~] T085 Manual demo walk — **deferred to user**. Runs against the live stack (`supabase start` + `uvicorn` + `npm run dev`). Smoke commands and observability format documented in `quickstart.md` §6.
- [X] T086 Update `specs/013-ai-merchant-chat-grounding/checklists/requirements.md` final pass — confirm all 16 boxes still check

---

## Dependencies

```text
Phase 1 (Setup) ─────────────────────────► Phase 2 (Foundational)
                                               │
                                               ├──► Phase 3 (US1 — Grounded Q&A)
                                               │       │
                                               │       └──► Phase 7 (Frontend US1 tasks)
                                               │
                                               ├──► Phase 4 (US2 — Isolation)         [parallel with US1, US3, US4]
                                               │
                                               ├──► Phase 5 (US3 — Multi-turn)        [parallel with US1, US2, US4]
                                               │       │
                                               │       └──► Phase 7 (Frontend US3 tasks)
                                               │
                                               └──► Phase 6 (US4 — Gating + quota)    [parallel with US1, US2, US3]
                                                       │
                                                       └──► Phase 7 (Frontend US4 tasks)

Phase 7 (Frontend) ──► Phase 8 (Polish)
```

US1, US2, US3, US4 are independent of each other once Phase 2 is complete — they touch overlapping files (`tools.py`, `orchestrator.py`) but each has its own tests and acceptance criteria. Implement in P1-priority order if a single contributor is on the work; parallelise across contributors otherwise.

## Parallel execution examples

- **Within Phase 2**: T011 (frontend types), T012 (limits.py), T013 (new package skeleton) can run in parallel after T010 lands
- **Within Phase 3 (US1)**: T030, T031, T032 are `[P]` — three different test files, all read-only against the foundational code
- **Within Phase 4 (US2)**: T040, T041 are `[P]` — same file but different test functions; can be authored independently then merged
- **Within Phase 6 (US4)**: T060, T061, T062 are `[P]` — independent test functions covering disjoint failure modes
- **Phases 3, 4, 5, 6** can run in parallel across contributors once Phase 2 is merged
- **Phase 7** frontend tasks T071, T072 are `[P]`; T073/T074 sequence after them

## Implementation strategy (recommended order)

1. **MVP slice (US1 + US2)**: Phases 1 → 2 → 3 → 4. After this, the demo prompts work and isolation is provably safe — this alone closes the spec's two P1 stories.
2. **Tier hardening (US4)**: Phase 6. Adds 403 / 429 / 503 paths so we can ship to paid users.
3. **UX polish (US3)**: Phase 5. Multi-turn continuity is nice-to-have for the demo.
4. **Frontend wiring**: Phase 7. Can begin after T010/T011 land, in parallel with backend work.
5. **Polish**: Phase 8.

## Format validation

All tasks above use the strict format: `- [ ] [TaskID] [P?] [Story?] Description with file path`.

- Setup phase (T001–T003): no story label ✅
- Foundational phase (T010–T022): no story label ✅
- US1 phase (T030–T035): all carry `[US1]` ✅
- US2 phase (T040–T043): all carry `[US2]` ✅
- US3 phase (T050–T052): all carry `[US3]` ✅
- US4 phase (T060–T063): all carry `[US4]` ✅
- Frontend phase (T070–T074): carries appropriate `[USx]` labels per task scope ✅
- Polish phase (T080–T086): no story label ✅
- Every task includes a concrete file path or shell command ✅

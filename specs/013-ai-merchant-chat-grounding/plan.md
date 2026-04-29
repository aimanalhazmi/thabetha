# Implementation Plan: AI Merchant-Chat Grounding

**Branch**: `013-ai-merchant-chat-grounding` | **Date**: 2026-04-30 | **Spec**: [./spec.md](./spec.md)
**Input**: Feature specification from `/specs/013-ai-merchant-chat-grounding/spec.md`

## Summary

Replace the keyword-matching stub at `POST /api/v1/ai/merchant-chat` with a real, tool-using LLM loop that answers caller questions about their own ledger. The model is given a small, fixed set of grounding tools — `list_debts`, `get_debt`, `get_dashboard_summary`, `get_commitment_history` — each of which executes through the existing `Repository` scoped to the authenticated caller. Cross-user isolation is therefore inherited from the existing repository contract (creditor / debtor / accepted-group-member only) rather than re-implemented in the AI layer. Anthropic Claude (vision-capable Sonnet) is the provider, behind a `MerchantChatProvider` interface so a `mock` provider drives tests under `REPOSITORY_TYPE=memory`. Quota and gating reuse the existing `_require_ai_enabled` and `ensure_ai_quota_available` helpers under a new feature key `merchant_chat`. The endpoint stays request/response (non-streaming) for this phase. Conversation history is supplied by the client per call (last 10 turns) and never persisted server-side.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, `anthropic` Python SDK (new), `@supabase/supabase-js`, React 19 + Vite. The `anthropic` SDK is the only new runtime dependency.
**Storage**: No new persisted entities. Existing `ai_usage` table is reused via the new feature key `merchant_chat`. Conversation history is client-owned and stateless on the backend.
**Testing**: `pytest` with `FastAPI.TestClient`; `REPOSITORY_TYPE=memory` forced in `tests/conftest.py`. Mock provider implements `MerchantChatProvider` for deterministic tool-use traces. Frontend smoke test optional.
**Target Platform**: Linux server (FastAPI + uvicorn), local Supabase Docker stack for end-to-end. Frontend is a SPA served by the same FastAPI app.
**Project Type**: Web application (FastAPI backend + React/Vite SPA).
**Performance Goals**: P90 ≤ 5 s end-to-end on local Supabase for the three demo prompts (per SC-004). Tool round-trips dominate; aim for ≤ 2 tool hops per typical question.
**Constraints**: Hard-gated on `profile.ai_enabled` (constitution §X). Per-user daily quota via the existing `ai_usage` table; default cap **50/day** matches the existing voice-draft limit (configurable via new `ai_merchant_chat_daily_limit` setting). Caller-scoped data only — no service-role queries, no global lookups. Tool result-row cap **20** (configurable); aggregate count + sum always exact (FR-005a).
**Scale/Scope**: Hackathon scale: ≤ 100 active paid-tier merchants, ≤ 50 chat calls per merchant per day. Tool calls hit the existing repository, which already serves dashboard reads at the same scale.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Bilateral Confirmation | ✅ N/A | Read-only feature; no state transitions. |
| II. Canonical 7-State Lifecycle | ✅ N/A | No transitions added; tools surface existing states. |
| III. Commitment Indicator | ✅ Pass | `get_commitment_history` returns the caller's own history; never global; assistant uses the term "commitment indicator / مؤشر الالتزام", never "credit score". |
| IV. Per-User Data Isolation | ✅ Pass — load-bearing | Every grounding tool calls `repo.<scoped method>(user.id, ...)`. The model has no other path to data. Cross-user probe is the primary acceptance test (Story 2). |
| V. Arabic-First | ✅ Pass | Every new user-visible string lands in `frontend/src/lib/i18n.ts` for AR + EN. Assistant replies in the language of the most recent caller question (FR-010). |
| VI. Supabase-First Stack | ✅ Pass | No new auth, no new buckets. Reuses existing JWT validation + repository. |
| VII. Schemas Source of Truth | ✅ Pass | `MerchantChatRequest` / `MerchantChatOut` updated in `backend/app/schemas/domain.py`; mirrored in `frontend/src/lib/types.ts`. |
| VIII. Audit Trail | ✅ N/A | Read-only; no `debt_events` row written. Tool invocations logged to stdout for observability (FR-009 — name + outcome only, no args, no contents). |
| IX. QR Identity | ✅ N/A | No QR involvement. |
| X. AI Paid-Tier Gating | ✅ Pass — load-bearing | Reuses `_require_ai_enabled`. New feature key `merchant_chat` for quota. 403 / 429 paths covered by tests. |

**Gate result**: PASS. No violations to justify in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/013-ai-merchant-chat-grounding/
├── plan.md              # This file
├── spec.md              # Feature spec (already written)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (mostly request/response shapes; no new persisted entities)
├── quickstart.md        # Phase 1 output — how to demo + how to run tests
├── contracts/
│   └── merchant-chat.openapi.yaml   # Phase 1 output — endpoint contract
├── checklists/
│   └── requirements.md              # /speckit-specify output
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   └── ai.py                                 # MODIFY: replace merchant_chat handler with provider-driven loop
│   ├── core/
│   │   └── config.py                             # MODIFY: add ai_merchant_chat_daily_limit, anthropic_api_key, merchant_chat_provider
│   ├── schemas/
│   │   └── domain.py                             # MODIFY: extend MerchantChatRequest (history + locale + tz), MerchantChatOut (answer + tool_trace)
│   └── services/
│       └── ai/
│           ├── limits.py                         # MODIFY: add MERCHANT_CHAT_FEATURE constant, generalise daily-limit lookup
│           └── merchant_chat/                    # NEW
│               ├── __init__.py
│               ├── provider.py                   # MerchantChatProvider interface + Message/ToolCall/ToolResult dataclasses
│               ├── anthropic_provider.py         # Claude Sonnet implementation, tool-use loop
│               ├── mock_provider.py              # Scripted tool-use for tests
│               ├── tools.py                      # Caller-scoped tool functions (list_debts, get_debt, get_dashboard_summary, get_commitment_history) — wraps repo
│               ├── time_resolver.py              # Resolve "last month" / "this week" → concrete (start, end) in caller's tz (FR-013)
│               └── orchestrator.py               # Drives: build prompt → call provider → execute requested tools → return final answer
└── tests/
    └── ai/
        ├── test_merchant_chat_grounding.py       # Demo prompts + Story 1 happy path (mock provider)
        ├── test_merchant_chat_isolation.py       # Cross-user leakage probe (Story 2)
        ├── test_merchant_chat_quota.py           # 403 + 429 paths (Story 4)
        ├── test_merchant_chat_tools.py           # Tool functions in isolation against InMemoryRepository
        └── test_merchant_chat_time_resolver.py   # Calendar-month, this-week, today resolution (FR-013)

frontend/
├── src/
│   ├── pages/
│   │   └── AIPage.tsx                            # MODIFY: chat surface — input, transcript, last-10-turn window, locale-aware
│   ├── components/
│   │   └── ai/
│   │       └── MerchantChatPanel.tsx             # NEW: reusable chat panel, handles client-side history trimming
│   ├── lib/
│   │   ├── api.ts                                # MODIFY: postMerchantChat(message, history)
│   │   ├── i18n.ts                               # MODIFY: new keys (chat_placeholder, chat_send, chat_no_data, chat_disabled, chat_quota_exceeded, chat_error_generic, chat_showing_top_n_of_m)
│   │   └── types.ts                              # MODIFY: mirror MerchantChatRequest / MerchantChatOut
│   └── pages/
│       └── AIPage.tsx                            # (listed above)
```

**Structure Decision**: Web-application layout (Option 2). The new code is contained inside the existing `backend/app/services/ai/` and `frontend/src/pages|components/ai/` trees — consistent with the Phase 11/12 AI features already in the repo.

## Complexity Tracking

> No constitution violations. Complexity Tracking intentionally empty.

The only "new" architectural piece is the `MerchantChatProvider` interface, which mirrors the `WhatsAppProvider` and `transcribe.get_transcription_provider()` patterns already established in the codebase — no new abstraction style is being introduced.

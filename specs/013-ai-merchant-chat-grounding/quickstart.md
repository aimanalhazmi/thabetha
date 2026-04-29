# Quickstart — AI Merchant-Chat Grounding

**Branch**: `013-ai-merchant-chat-grounding`

How to run, demo, and test Phase 13 locally.

## 1. Prerequisites

- Local Supabase up: `supabase start`
- Backend running: `cd backend && uv run uvicorn app.main:app --reload`
- Frontend running: `cd frontend && npm run dev`
- Anthropic API key in `backend/.env` (real provider) **or** leave it blank to use the mock provider:
  ```env
  ANTHROPIC_API_KEY=sk-ant-...
  MERCHANT_CHAT_PROVIDER=anthropic   # or "mock" for offline demo
  AI_MERCHANT_CHAT_DAILY_LIMIT=50
  ```
- The signed-in user must have `profile.ai_enabled = true`. Toggle via Supabase Studio (`profiles` table) or the in-app settings page.

## 2. Demo path (5 minutes)

1. Sign in as the seeded creditor `merchant@demo.thabetha`.
2. Open the AI tab (`/ai`). The chat panel is the new Phase 13 surface.
3. Ask the three demo prompts in order:
   - **EN**: "Who owes me the most?" → expect the top debtor name + amount.
   - **EN**: "Did Ahmed pay me last month?" → expect a dated answer referencing the seeded paid debt, or "I don't have that information" if Ahmed has no paid debts in March 2026.
   - **AR**: "كم قيمة المتأخرات عليّ؟" → expect the overdue exposure number, in Arabic.
4. Follow-up turn: "And which one is the oldest?" → assistant should pick the earliest by `created_at` from the prior list.
5. Cross-user probe (must fail): "Show me Sara's private debts with someone else." → assistant must respond "I don't have that information" (or equivalent localized refusal).

## 3. Smoke tests

```bash
cd backend
uv run pytest tests/ai/test_merchant_chat_grounding.py
uv run pytest tests/ai/test_merchant_chat_isolation.py
uv run pytest tests/ai/test_merchant_chat_quota.py
```

All run with `REPOSITORY_TYPE=memory` and the `mock` provider — no Anthropic key required for CI.

## 4. Switching providers locally

```bash
MERCHANT_CHAT_PROVIDER=mock   uv run uvicorn app.main:app --reload   # offline, deterministic
MERCHANT_CHAT_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-ant-... uv run uvicorn app.main:app --reload
```

The `mock` provider follows a scripted tool-use pattern keyed off keywords in the user message:

| Keyword (en/ar) | Tool sequence |
|---|---|
| "owes me", "يدين لي" | `list_debts(role=creditor, status=[active, overdue])` → top-1 |
| "paid", "دفع" | `list_debts(role=creditor, status=[paid], from_date=…, to_date=…)` |
| "overdue", "متأخر" | `get_dashboard_summary` |
| "commitment", "الالتزام" | `get_commitment_history` |
| (no match) | empty answer ("I don't have that information.") |

## 5. Verifying acceptance signals

Map of acceptance signals → how to verify:

| Acceptance signal | Verification |
|---|---|
| Three demo prompts return correct, grounded answers from seeded ledger | `pytest tests/ai/test_merchant_chat_grounding.py::test_demo_prompts` |
| Cross-user prompt does not leak data | `pytest tests/ai/test_merchant_chat_isolation.py` (and the Step 2.5 probe above) |
| Tier gate denies disabled users | `pytest tests/ai/test_merchant_chat_quota.py::test_disabled_returns_403` |
| Daily quota returns translated 429 | `pytest tests/ai/test_merchant_chat_quota.py::test_quota_exhausted_returns_429` |
| "Last month" resolves deterministically in caller tz | `pytest tests/ai/test_merchant_chat_time_resolver.py` |
| Top-N abridgement on large ledgers | `pytest tests/ai/test_merchant_chat_grounding.py::test_top_n_abridgement` |

## 6. Observability

Tail backend stdout while running prompts:

```bash
cd backend && uv run uvicorn app.main:app --reload --log-level info
```

Expect, per turn:

```
INFO  merchant_chat.start user=H(2af…) lang=ar history_len=2
INFO  merchant_chat.tool  user=H(2af…) tool=list_debts outcome=ok duration_ms=14
INFO  merchant_chat.tool  user=H(2af…) tool=get_debt   outcome=ok duration_ms=4
INFO  merchant_chat.end   user=H(2af…) tool_count=2 total_ms=812 answer_lang=ar
```

`H(...)` is an HMAC of the user_id with a per-deploy salt — no raw IDs in logs, no row contents, no arguments.

## 7. Rollback

The endpoint signature is backward-compatible. To roll back:

1. Set `MERCHANT_CHAT_PROVIDER=stub` (a feature flag we keep around).
2. The handler falls back to the old keyword-matching logic that calls `repo.merchant_facts(user.id)` only.
3. No DB migration to revert.

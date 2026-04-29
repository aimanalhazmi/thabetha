# Project Status — Claude Handoff Reference

Last updated: 2026-04-30 (branch `013-ai-merchant-chat-grounding`)

## Shipped Features

| Feature | Branch | Notes |
|---|---|---|
| Core debt lifecycle (UC1–UC8) | `develop` | Bilateral confirm, 7-state machine, commitment indicator, reminders, QR, dashboard. |
| Group formation & surface (UC9 part 1) | `008-groups-mvp-surface` | Group CRUD, invite/accept/leave, member management, group-tagged debts. |
| Group auto-netting (UC9 part 2) | `009-groups-auto-netting` | Minimum-edge settlement proposals, atomic settle, mixed-currency guard, expiry sweep, rejection path. See `specs/009-groups-auto-netting/`. |
| AI voice debt draft (Phase 12) | `012-ai-voice-debt-draft` | Audio + transcript → `DebtCreate` draft via Whisper-style provider. Mock provider for CI. |
| AI merchant-chat grounding (Phase 13) | `013-ai-merchant-chat-grounding` | Tool-using LLM (`list_debts`, `get_debt`, `get_dashboard_summary`, `get_commitment_history`) scoped to caller's ledger. Mock + lazy-loaded Anthropic providers. Stateless conversation history (last 10 turns). 20-row top-N cap with exact aggregates. Server-side time-phrase resolution in caller tz. 25 tests on `tests/ai/`. See `specs/013-ai-merchant-chat-grounding/`. |

## Post-MVP Backlog

| Feature | Notes |
|---|---|
| AI voice/chat tier (UC10) | Gated on `profile.ai_enabled`. Voice draft (Phase 12) and merchant-chat grounding (Phase 13) are shipped on their respective branches; receipt extraction (Phase 11) still pending. |
| WhatsApp real provider | Currently `WHATSAPP_PROVIDER=mock`. |
| Postgres parity for settlement endpoints | `postgres.py` stubs raise `NotImplementedError` — in-memory is canonical for CI. |

## Known Stubs / TODOs

- `backend/app/repositories/postgres.py`: Six settlement methods raise `NotImplementedError("... Postgres parity pending (T015)")`. The in-memory path handles all CI tests.
- `backend/app/services/whatsapp/templates.py`: Group and settlement notifications are in-app-only; no WhatsApp templates needed for MVP.

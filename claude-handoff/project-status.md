# Project Status — Claude Handoff Reference

Last updated: 2026-04-29 (branch `009-groups-auto-netting`)

## Shipped Features

| Feature | Branch | Notes |
|---|---|---|
| Core debt lifecycle (UC1–UC8) | `develop` | Bilateral confirm, 7-state machine, commitment indicator, reminders, QR, dashboard. |
| Group formation & surface (UC9 part 1) | `008-groups-mvp-surface` | Group CRUD, invite/accept/leave, member management, group-tagged debts. |
| Group auto-netting (UC9 part 2) | `009-groups-auto-netting` | Minimum-edge settlement proposals, atomic settle, mixed-currency guard, expiry sweep, rejection path. See `specs/009-groups-auto-netting/`. |

## Post-MVP Backlog

| Feature | Notes |
|---|---|
| AI voice/chat tier (UC10) | Gated on `profile.ai_enabled`. Stubs exist in backend. |
| WhatsApp real provider | Currently `WHATSAPP_PROVIDER=mock`. |
| Postgres parity for settlement endpoints | `postgres.py` stubs raise `NotImplementedError` — in-memory is canonical for CI. |

## Known Stubs / TODOs

- `backend/app/repositories/postgres.py`: Six settlement methods raise `NotImplementedError("... Postgres parity pending (T015)")`. The in-memory path handles all CI tests.
- `backend/app/services/whatsapp/templates.py`: Group and settlement notifications are in-app-only; no WhatsApp templates needed for MVP.

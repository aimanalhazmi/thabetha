# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Thabetha

A web-based debt confirmation and settlement system for local merchants and customers. Debts require bilateral confirmation — a creditor creates a debt, the debtor must accept/reject before it becomes "active". Features include QR identity tokens, trust scoring, groups, WhatsApp notifications, and AI stubs (voice draft, merchant chatbot).

## Development Commands

### Backend (FastAPI + Python 3.12, managed with `uv`)

```bash
cd backend
uv sync                                      # install dependencies
uv run uvicorn app.main:app --reload         # dev server on :8000
uv run pytest                                # run all tests
uv run pytest tests/test_debt_lifecycle.py   # single test file
uv run pytest -k test_name                   # single test by name
uv run ruff check .                          # lint
uv run mypy .                                # type check
```

### Frontend (React 19 + Vite + TypeScript)

```bash
cd frontend
npm install
npm run dev          # dev server with HMR on :5173
npm run build        # tsc + vite build
npm run typecheck    # tsc --noEmit
```

### Full-stack Docker

```bash
docker compose up --build   # builds frontend, serves API + static on :8000
```

## Architecture

### Backend (`backend/app/`)

**App factory**: `main.py` — `create_app()` builds the FastAPI instance, mounts API routers under `/api/v1`, optionally seeds demo data, and serves the built frontend as a SPA fallback.

**Routers** (`api/`): One file per domain — `debts.py`, `profiles.py`, `qr.py`, `dashboards.py`, `notifications.py`, `groups.py`, `ai.py`, `health.py`. All routers are aggregated in `api/router.py`.

**Repository pattern**: Routers depend on the repository via `Depends(get_repository)`. Currently there are two persistence layers:
- `repositories/memory.py` — `InMemoryRepository`, a thread-safe in-memory store used for local dev, CI, and demos. This is the active default.
- `db/database.py` — SQLite schema and connection helper (being introduced). Defines the full relational schema with WAL mode and foreign keys.

The production target is Supabase (Postgres + Auth + Storage + RLS). The Supabase migration lives at `supabase/migrations/001_initial_schema.sql`.

**Schemas**: All Pydantic models (requests, responses, enums) live in `schemas/domain.py`.

**Config**: `core/config.py` — `pydantic-settings` with `.env` file support. Key property: `is_production` (true when `APP_ENV=production`).

### Auth model

`core/security.py` provides the `get_current_user` FastAPI dependency:
- **Non-production**: accepts demo headers (`x-demo-user-id`, `x-demo-name`, `x-demo-phone`) — no JWT needed
- **Production**: requires `Authorization: Bearer <supabase-jwt>`, validated against `SUPABASE_JWT_SECRET`

### Frontend (`frontend/src/`)

- `App.tsx` — React Router with all routes
- `lib/api.ts` — all backend API calls
- `lib/types.ts` — TypeScript types mirroring backend schemas
- `lib/i18n.ts` — Arabic/English translations; Arabic-first, RTL/LTR support

### Testing patterns

Tests use `FastAPI.TestClient` via a `client` fixture. The `reset_repository` fixture (autouse) clears the in-memory repo between tests. Use `auth_headers(user_id, name, phone)` from `conftest.py` to build demo auth headers for requests.

## Key environment variables

| Variable | Purpose |
|---|---|
| `APP_ENV` | `local` / `staging` / `production` — gates demo-header auth |
| `SEED_DEMO_DATA` | Seeds in-memory demo users/debts when `true` |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` | Supabase connection |
| `OPENAI_API_KEY` | AI voice/chat stubs |
| `WHATSAPP_PROVIDER` | `mock` / `twilio` / `meta` |

Demo users when `SEED_DEMO_DATA=true`: `merchant-1` (Baqala Al Noor), `customer-1` (Ahmed), `friend-1` (Sara).

## Linting config

Backend uses Ruff (`line-length=150`, target `py312`) with Pyflakes, pycodestyle, isort, pep8-naming, pyupgrade, and flake8-bugbear rules. `E501` (long lines) is ignored.

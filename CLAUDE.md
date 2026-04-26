# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Thabetha

A web-based debt confirmation and settlement system for local merchants and customers. Debts require bilateral confirmation — a creditor creates a debt, the debtor must accept/reject before it becomes "active". Features include QR identity tokens, trust scoring, groups, notifications, and AI stubs (voice draft, merchant chatbot).

## Product Concept & Use Cases

Replaces the paper "debt notebook" used in Arab local markets. Digitizes informal credit between shops and customers (and between friends/family) with bilateral confirmation, reminders, and a trust score.

**Actors**
- **Creditor**: shop/business (grocer, barber, café, restaurant) or individual lender.
- **Debtor**: customer, friend, relative, neighbor.

**Debt lifecycle**: `pending_confirmation` → `active` → (`overdue` if past due) → `paid`. State only advances via bilateral action.

**Core use cases**
- **UC1 — Sign up / profile**: name, phone (WhatsApp), password, user type required; email + tax/CR number optional. Business accounts add a sub-profile: shop name, activity type, location, description.
- **UC2 — Create debt** (creditor): amount, currency, debtor name, description, due date required; invoice photo, voice note, notes optional. AI-subscribed creditors can dictate; AI extracts fields and asks for confirmation.
- **UC3 — Bilateral confirm**: debtor receives request and may **accept / reject / request edit**. Debt is binding only after accept.
- **UC4 — QR identification**: every user has a rotating, time-limited QR + ID. Creditor scans debtor's QR to open profile, see trust score, and attach the new debt to the right person.
- **UC5 — Payment**: debtor taps "paid" → creditor confirms receipt → state = `paid` → trust score updated.
- **UC6 — Notifications**: in-app + WhatsApp on create, confirm, due-soon, overdue, closed. Debtor can disable WhatsApp per-merchant in settings.
- **UC7 — Trust score**: starts 50/100. ↑ on on-time/early payment and repeated compliance; ↓ on lateness/ignored debts. Visible only in the bilateral context between two parties — never public.
- **UC8 — Dashboards**:
  - Debtor: total owed, due-soon, overdue, per-creditor list, own trust score.
  - Creditor: total receivable, debtor count, active/overdue/paid breakdowns, top-compliant customers, overdue alerts, simple stats. AI-subscribed creditors get a chatbot for summaries / stats / recommendations.
- **UC9 — Groups (friends/family, optional)**: shared multi-party group with **no internal privacy** — members see each other's debts so they can settle on each other's behalf. System auto-nets cross-debts (e.g. B pays A's barber bill, system offsets A↔B).
- **UC10 — AI (creditor-only, paid tier)**: voice → debt fields extraction; chatbot for ledger summaries, stats, and recommendations. Future: behavior analysis, payment-likelihood prediction, fraud detection, repayment-plan suggestions.

**Non-functional must-haves**
- Bilingual AR/EN with runtime RTL/LTR toggle (Arabic-first).
- Encrypted passwords; strict per-user data isolation — a user only sees their own debts (plus group debts if enrolled). No public debtor list.
- Full audit trail per debt: created-at + by, confirmed-at + by, paid-at + by, current state.
- Simple, fast UX usable by non-technical shop owners.

## Development Commands

### Backend (FastAPI + Python 3.12, managed with `uv`)

```bash
cd backend
uv sync                                      # install dependencies
uv run uvicorn app.main:app --reload         # dev server on :8000
uv run pytest                                # run all tests (uses in-memory repo)
uv run pytest tests/test_debt_lifecycle.py   # single test file
uv run pytest -k test_name                   # single test by name
uv run ruff check .                          # lint
uv run ruff check --fix .                    # lint + auto-fix
```

### Frontend (React 19 + Vite + TypeScript)

```bash
cd frontend
npm install
npm run dev          # dev server with HMR on :5173
npm run build        # tsc + vite build
npm run typecheck    # tsc --noEmit
```

### Full-stack Docker (preferred for full-stack dev)

```bash
docker compose up --build   # starts Postgres + GoTrue (auth) + app on :8000
```

This spins up three services: `db` (Postgres 16), `auth` (GoTrue/supabase), `web` (FastAPI + built frontend). No manual DB setup needed — migrations run automatically at startup.

## Architecture

### Backend (`backend/app/`)

**App factory**: `main.py` — `create_app()` builds the FastAPI instance, mounts API routers under `/api/v1`, runs Postgres migrations at startup (when `REPOSITORY_TYPE=postgres`), optionally seeds demo data (in-memory only), and serves the built frontend as a SPA fallback.

**Routers** (`api/`): One file per domain — `debts.py`, `profiles.py`, `qr.py`, `dashboards.py`, `notifications.py`, `groups.py`, `ai.py`, `auth.py`, `health.py`. All aggregated in `api/router.py`.

**Repository pattern**: All routers depend on `Repository` (the ABC from `repositories/base.py`) via `Depends(get_repository)`. The factory in `repositories/__init__.py` selects the implementation based on `REPOSITORY_TYPE`:
- `repositories/memory.py` — `InMemoryRepository`: thread-safe in-memory store; used for tests and local dev without Docker
- `repositories/postgres.py` — `PostgresRepository`: full SQL implementation using `psycopg` v3 + `psycopg-pool`; used when running via Docker

**Auth backend** (`api/auth.py`): Proxies sign-up/sign-in to GoTrue via `httpx`. The frontend only talks to FastAPI — never directly to GoTrue.
- `POST /api/v1/auth/signup` → GoTrue `/signup` + creates profile row
- `POST /api/v1/auth/signin` → GoTrue `/token?grant_type=password`
- `POST /api/v1/auth/refresh` → GoTrue `/token?grant_type=refresh_token`

**Migrations** (`db/migrate.py`): `apply_migrations()` reads `supabase/migrations/*.sql` in order and tracks applied files in a `schema_migrations` table. Called at app startup when using Postgres.

**Schemas**: All Pydantic models (requests, responses, enums) in `schemas/domain.py`.

**Config** (`core/config.py`): `pydantic-settings` with `.env` support.

### Auth model

`core/security.py` → `get_current_user` FastAPI dependency:
- **Non-production** (`APP_ENV != production`): accepts demo headers (`x-demo-user-id`, `x-demo-name`, `x-demo-phone`) — no JWT needed. Used in tests.
- **Production / Docker**: requires `Authorization: Bearer <JWT>` validated against `SUPABASE_JWT_SECRET`.

### Frontend (`frontend/src/`)

- `App.tsx` — `AuthProvider` + `BrowserRouter`; two route groups: `/` (AuthPage) and `/*` (AppShell with Layout + page routes)
- `contexts/AuthContext.tsx` — JWT state; restores session from localStorage on mount; provides `signIn`, `signUp`, `signOut`, `user`, `isAuthenticated`
- `lib/auth.ts` — raw sign-up/sign-in functions; token storage in localStorage (`auth_token`, `refresh_token`, `auth_user`, `auth_expires_at`)
- `lib/api.ts` — `apiRequest<T>()` reads token from localStorage, sets `Authorization: Bearer`
- `lib/types.ts` — TypeScript types mirroring backend schemas
- `lib/i18n.ts` — Arabic/English translations; Arabic-first, RTL/LTR via `document.dir`
- `components/Layout.tsx` — sidebar with `NavLink` routing, user info, language toggle, sign-out; also exports `Stat`, `Panel`, `Input` sub-components
- `components/ProtectedRoute.tsx` — redirects to `/` if not authenticated
- `pages/` — one file per route: `AuthPage`, `DashboardPage`, `DebtsPage`, `ProfilePage`, `QRPage`, `GroupsPage`, `AIPage`, `NotificationsPage`

### Testing patterns

Tests use `FastAPI.TestClient` via a `client` fixture. `conftest.py` forces `REPOSITORY_TYPE=memory` so tests never touch Postgres. The `reset_repository` fixture (autouse) clears state between tests. Use `auth_headers(user_id, name, phone)` to build demo auth headers.

## Key environment variables

| Variable | Purpose |
|---|---|
| `REPOSITORY_TYPE` | `memory` (default) or `postgres` |
| `DATABASE_URL` | Postgres connection string (required when `REPOSITORY_TYPE=postgres`) |
| `GOTRUE_URL` | GoTrue service URL, e.g. `http://auth:9999` (required for auth proxy) |
| `SUPABASE_JWT_SECRET` | JWT secret; must match GoTrue's `GOTRUE_JWT_SECRET` |
| `APP_ENV` | `local` / `staging` / `production` — gates demo-header auth |
| `SEED_DEMO_DATA` | Seeds demo users/debts on startup (in-memory only) |
| `OPENAI_API_KEY` | AI voice/chat stubs |

## Linting config

Backend uses Ruff (`line-length=150`, target `py312`): Pyflakes, pycodestyle, isort, pep8-naming, pyupgrade, flake8-bugbear. `E501` ignored.

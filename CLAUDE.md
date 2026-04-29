# CLAUDE.md

Guidance for Claude Code working in this repository. Product and lifecycle details live in [`docs/`](./docs/) — this file is intentionally short and dev-focused.

## Project summary

**Thabetha / ثبتها** — a bilingual (Arabic-first, English) web app that turns the paper "debt notebook" used in Arab local markets into a bilaterally-confirmed debt ledger. Stack: React/Vite frontend, FastAPI backend, **Supabase** for Auth + Postgres + Storage.

Full product context: [`docs/product-requirements.md`](./docs/product-requirements.md) (and [`docs/product-requirements-ar.md`](./docs/product-requirements-ar.md)).

## Core product rules

- **Bilateral confirmation is the differentiator.** A debt is binding only after the debtor accepts. A debt is `paid` only after the creditor confirms receipt.
- **Use the canonical 7-state debt lifecycle.** See [`docs/debt-lifecycle.md`](./docs/debt-lifecycle.md). The string identifiers in code, DB, and UI must match exactly.
- **Use the term "commitment indicator / مؤشر الالتزام"**, never "credit score" / "trust score". The indicator is internal to Thabetha and visible only in bilateral context.
- **Per-user data isolation.** A user only ever sees debts where they are creditor, debtor, or accepted group member. Postgres RLS is the authoritative boundary; API handlers should follow the same shape.
- **Arabic-first.** New strings must land in `frontend/src/lib/i18n.ts` for both languages.
- **Debtor cannot reject.** The only debtor pushback on a `pending_confirmation` debt is `request_edit`. The creditor then approves (debt updates → `pending_confirmation` for re-acceptance) or rejects (original terms stand → `pending_confirmation`). The `rejected` status no longer exists.
- **Commitment indicator (`profiles.commitment_score`, 0–100, default 50) is automatic.** On creditor-confirmed payment: `+3` if paid before `due_date`, `+1` if on `due_date`, otherwise `−2 × 2^N` where N is the count of already-applied missed-reminder events for that debt. Each creditor-configured reminder date that passes unpaid fires its own `−2 × 2^N` penalty exactly once via the lazy sweeper that already runs on debt-list / dashboard reads. Events are recorded in `commitment_score_events` (with `reminder_date` for idempotency); score is clamped 0–100.
- **Creditor configures reminders per debt** (`debts.reminder_dates date[]`) at creation time — UI offers presets (`on due`, `+1d`, `+3d`, `+7d`, `+14d`) plus custom dates.

## Actors

- **Creditor** — shop / freelancer / individual lender. Creates debts, scans QR, confirms payments.
- **Debtor** — customer / friend / family. Accepts / rejects / requests-edit, marks debts paid, shows QR.
- **Both** — shows the union of nav items.

Page → actor mapping: [`docs/pages-and-use-cases.md`](./docs/pages-and-use-cases.md).

## MVP boundaries

[`docs/mvp-scope.md`](./docs/mvp-scope.md). The hackathon target is UC1–UC8 minus the AI tier. Group debt (UC9) is post-MVP — endpoints exist but are not surfaced in MVP nav. AI (UC10) is paid-tier and gated on `profile.ai_enabled`.

## Supabase-first technical direction

- **Auth**: Supabase Auth via `@supabase/supabase-js` on the frontend; backend validates `SUPABASE_JWT_SECRET` (HS256). The `/api/v1/auth/*` proxy is a thin convenience wrapper around the same Supabase Auth REST endpoints.
- **DB**: Supabase Postgres. Migrations in `supabase/migrations/` are auto-applied at backend startup when `REPOSITORY_TYPE=postgres`, or via `supabase db reset` locally.
- **Storage**: two private buckets — `receipts` and `voice-notes` — gated by RLS in `003_storage_policies.sql`.
- **Local stack**: `supabase start` (Docker) for the full Auth+DB+Storage+Studio stack. See [`docs/local-development.md`](./docs/local-development.md).
- **In-memory repository** (`REPOSITORY_TYPE=memory`) is for tests and quick local debugging without Docker. Tests force this mode via `tests/conftest.py`.

## Repository structure

```
backend/app/
  api/        # FastAPI routers (one file per domain)
  core/       # config, security (JWT validation)
  db/         # migration runner
  repositories/
    base.py     # Repository ABC
    memory.py   # InMemoryRepository (tests, demo)
    postgres.py # PostgresRepository (Supabase-backed)
  schemas/    # Pydantic models (single source of truth for enums)
  main.py
backend/tests/
frontend/src/
  pages/      # one file per route (role-aware)
  components/ # Layout, ProtectedRoute, primitives
  lib/        # api, auth, supabaseClient, i18n, types
  contexts/   # AuthContext
supabase/
  migrations/ # 001..NNN, applied in order
  config.toml # Supabase CLI config
docs/         # Product & developer documentation (canonical)
```

## Development commands

### Backend (FastAPI + Python 3.12, `uv`)

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload   # :8000
uv run pytest                          # in-memory repo
uv run ruff check --fix .
```

### Frontend (React 19 + Vite + TypeScript)

```bash
cd frontend
npm install
npm run dev          # :5173
npm run build        # tsc + vite build
npm run typecheck
```

### Supabase (local)

```bash
supabase start         # Auth + DB + Storage + Studio (Docker)
supabase db reset      # apply migrations + seed
supabase status -o env # print URLs / keys
```

## Local development summary

Quick path: `supabase start` → `cp .env.example .env` (and `backend/`, `frontend/`) → `cd backend && uv run uvicorn app.main:app --reload` → `cd frontend && npm run dev`. Sign up at `http://127.0.0.1:5173`, confirm via Inbucket (`http://127.0.0.1:55324`).

Full instructions, troubleshooting: [`docs/local-development.md`](./docs/local-development.md).

## Architecture notes

- **App factory** (`main.py::create_app`) builds the FastAPI app, mounts routers under `/api/v1`, applies Postgres migrations when `REPOSITORY_TYPE=postgres`, and serves the built frontend as a SPA fallback.
- **Repository pattern**. Routers depend on `Repository` (ABC) via `Depends(get_repository)`. The factory in `repositories/__init__.py` selects memory or postgres from `REPOSITORY_TYPE`. Both implementations must stay in sync — change `base.py` first, then both implementations, then routers.
- **Schemas** (`schemas/domain.py`) are the single source of truth for enums (`DebtStatus`, `AccountType`, `NotificationType`, `AttachmentType`, `GroupMemberStatus`). Frontend `lib/types.ts` mirrors these manually.
- **Frontend auth** uses `@supabase/supabase-js`; the JWT goes into `Authorization: Bearer` for backend calls (`lib/api.ts`).

## Auth and security

- Backend validates JWTs in `core/security.py::get_current_user`. In `APP_ENV != production` it also accepts `x-demo-*` headers for tests and quick debugging.
- Postgres RLS is enabled on all user-data tables and is authoritative when `RLS_MODE=enforce`. Request-scoped queries use the non-privileged `app_authenticated` path; elevated work is allow-listed through `backend/app/repositories/system_tasks.py`. Rollout details live in [`specs/010-backend-rls-enforcement/quickstart.md`](./specs/010-backend-rls-enforcement/quickstart.md).
- QR tokens are random UUIDs with a TTL (default 10 min); they resolve to a profile preview, never to credentials.
- Storage objects are private; serve via signed URLs only.

## Storage

- Bucket `receipts` — invoice photos, scanned bills. Path: `<debt_id>/<uuid>-<filename>`.
- Bucket `voice-notes` — optional voice memos. Same path convention.
- RLS in `003_storage_policies.sql` allows read/write only when the caller is creditor or debtor of the debt encoded in the first path segment.

## Testing

Tests use `FastAPI.TestClient` via the `client` fixture. `conftest.py` forces `REPOSITORY_TYPE=memory` and provides `auth_headers(user_id, ...)` for demo auth. The `reset_repository` autouse fixture clears state between tests. Add a test for any new state transition.

## Coding conventions

- Backend: Ruff (`line-length=150`, `py312`), Pyflakes, pycodestyle, isort, pep8-naming, pyupgrade, flake8-bugbear. `E501` ignored.
- Frontend: TypeScript strict, components in `pages/` (one per route) and `components/` (reusable). New strings → `lib/i18n.ts` (Arabic + English).
- New columns / enum values → migration file under `supabase/migrations/`. Don't edit `001_*.sql` retroactively.

## Detailed docs

- [`docs/product-requirements.md`](./docs/product-requirements.md) — problem, solution, actors, features.
- [`docs/product-requirements-ar.md`](./docs/product-requirements-ar.md) — Arabic mirror.
- [`docs/pages-and-use-cases.md`](./docs/pages-and-use-cases.md) — actor → page → UC mapping.
- [`docs/debt-lifecycle.md`](./docs/debt-lifecycle.md) — canonical 7-state machine.
- [`docs/mvp-scope.md`](./docs/mvp-scope.md) — MoSCoW.
- [`docs/roadmap.md`](./docs/roadmap.md) — hackathon, post-MVP, future.
- [`docs/user-flows.md`](./docs/user-flows.md) — creditor / debtor / shared flows.
- [`docs/local-development.md`](./docs/local-development.md) — exact local setup.
- [`docs/supabase.md`](./docs/supabase.md) — Auth, DB, Storage, RLS, CLI workflow.

## Key environment variables

| Variable | Purpose |
|---|---|
| `APP_ENV` | `local` / `staging` / `production` — gates demo-header auth. |
| `REPOSITORY_TYPE` | `memory` (default; tests) or `postgres`. |
| `DATABASE_URL` | Postgres connection string when `REPOSITORY_TYPE=postgres`. |
| `SUPABASE_URL` | Supabase API URL (local: `http://127.0.0.1:55321`). |
| `SUPABASE_ANON_KEY` | Public anon key for the frontend / proxy. |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role key (backend admin operations only). |
| `SUPABASE_JWT_SECRET` | HS256 secret used to validate access tokens. |
| `SUPABASE_STORAGE_BUCKET` | Default bucket for legacy attachment paths. |
| `SEED_DEMO_DATA` | In-memory only — seeds demo users / debts at boot. |
| `OPENAI_API_KEY` | Optional; AI voice / chat stubs. |
| `WHATSAPP_PROVIDER` | `mock` (default). Real provider config is post-MVP. |

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at `specs/013-ai-merchant-chat-grounding/plan.md`.
<!-- SPECKIT END -->

## Active Technologies
- Python 3.12 (backend), TypeScript 5.x strict (frontend), SQL (Supabase Postgres 15). + FastAPI, Pydantic v2, `@supabase/supabase-js`, React 19 + Vite + React Router. No new dependencies. (008-groups-mvp-surface)
- Supabase Postgres. New audit table `group_events` and one new column on `profiles` (`groups_enabled`); enum widening for `group_members.status`; new partial-unique live-row index; `groups.updated_at` column. (008-groups-mvp-surface)

## Recent Changes
- 008-groups-mvp-surface: Added Python 3.12 (backend), TypeScript 5.x strict (frontend), SQL (Supabase Postgres 15). + FastAPI, Pydantic v2, `@supabase/supabase-js`, React 19 + Vite + React Router. No new dependencies.

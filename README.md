# Thabetha / ثبتها

A bilingual (Arabic-first) web app that turns the paper "debt notebook" used in Arab local markets into a **bilaterally-confirmed** debt ledger. Every debt is created by a creditor and only becomes binding when the debtor explicitly accepts. Both parties see the same record, the same audit trail, and the same status.

## What's in the box

| Layer | Stack |
|---|---|
| Frontend | React 19, Vite, TypeScript, AR/EN i18n, RTL/LTR |
| Backend | FastAPI, Python 3.12, `uv`, repository pattern |
| Auth | Supabase Auth (`@supabase/supabase-js`) |
| Database | Supabase Postgres + RLS |
| Storage | Supabase Storage (`receipts`, `voice-notes` buckets) |
| Local dev | Supabase CLI (Docker) |

Product details: [`docs/product-requirements.md`](./docs/product-requirements.md). Lifecycle: [`docs/debt-lifecycle.md`](./docs/debt-lifecycle.md). Pages by actor: [`docs/pages-and-use-cases.md`](./docs/pages-and-use-cases.md). MVP scope: [`docs/mvp-scope.md`](./docs/mvp-scope.md). **How to demo**: [`docs/demo-script.md`](./docs/demo-script.md).

## Local setup (TL;DR)

```bash
# 1. Boot Supabase (Auth + Postgres + Storage + Studio)
supabase start
supabase db reset                 # apply migrations + seed

# 2. Configure env
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# paste anon/service/jwt keys from `supabase status -o env`

# 3. Backend
cd backend && uv sync && uv run uvicorn app.main:app --reload

# 4. Frontend (new shell)
cd frontend && npm install && npm run dev
```

Open http://127.0.0.1:5173, sign up, confirm via Inbucket (http://127.0.0.1:55324). Full walk-through: [`docs/local-development.md`](./docs/local-development.md).

## Tests

```bash
cd backend && uv run pytest          # in-memory repo, no DB needed
cd frontend && npm run typecheck && npm run build
```

## Production-style Docker smoke

The root `Dockerfile` builds the React/Vite website and copies `frontend/dist`
into the FastAPI image, so one container serves both `/api/v1/*` and the SPA
fallback on `:8000`.

```bash
supabase start
cp .env.example .env                 # set VITE_SUPABASE_ANON_KEY from supabase status -o env
docker compose up --build web
```

Open http://127.0.0.1:8000.

## Repository layout

- `backend/app/` — FastAPI app, repositories (memory + postgres), schemas, security.
- `backend/tests/` — pytest suite.
- `frontend/src/` — pages, components, i18n, Supabase client.
- `supabase/migrations/` — SQL migrations applied in order.
- `docs/` — canonical product and developer docs.
- `CLAUDE.md` — guidance for Claude Code working in this repo.

## Contributing

When you add a debt status, currency, page, or UC — update the matching doc in `docs/`, the canonical enum in `backend/app/schemas/domain.py`, and the i18n strings in `frontend/src/lib/i18n.ts`. Don't edit `supabase/migrations/001_*.sql` retroactively; create a new migration file.

# Thabetha Backend

FastAPI backend for Thabetha, built with Python 3.12 and managed with `uv`. Implements the repository pattern against both an in-memory store (tests, local debug) and Supabase Postgres (local and production).

## Environment Secrets

Copy the example file and fill in the values before running:

```powershell
copy .env.example .env
```

| Variable | Purpose |
|---|---|
| `APP_ENV` | `local`, `staging`, or `production`. Gates demo-header auth. |
| `REPOSITORY_TYPE` | `memory` (default, no DB needed) or `postgres`. |
| `DATABASE_URL` | Postgres connection string when `REPOSITORY_TYPE=postgres`. |
| `SUPABASE_URL` | Supabase project URL. |
| `SUPABASE_ANON_KEY` | Supabase public anon key. |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role key for privileged server-side operations. |
| `SUPABASE_JWT_SECRET` | HS256 secret used to validate Supabase access tokens. |
| `SEED_DEMO_DATA` | Seeds demo users and debts at boot when `true` (in-memory only). |
| `OPENAI_API_KEY` | Enables AI voice and chat features. |
| `WHATSAPP_PROVIDER` | `mock` (default), `twilio`, or `meta`. |

Obtain Supabase values from `supabase status -o env` when running the local stack.

## Setup

```powershell
uv sync
uv run uvicorn app.main:app --reload
```

The API starts on `http://127.0.0.1:8000`. Interactive docs are at `http://127.0.0.1:8000/docs`.

## Quality Checks

```powershell
uv run pytest              # runs against the in-memory repository, no DB required
uv run ruff check --fix .  # lint and auto-fix
```

## Module Layout

```
app/
  api/            FastAPI routers, one file per domain
  core/           Settings, JWT validation, auth dependencies
  db/             Supabase client boundary and migration runner
  repositories/   Repository ABC, in-memory impl, Postgres impl
  schemas/        Pydantic request/response models; canonical enums
  services/       Business logic helpers (demo seed, notifications)
  observability/  Logging and tracing utilities
  main.py         App factory; mounts routers, runs migrations
tests/            pytest suite; all tests use the in-memory repository
```

## Repository Pattern

Routers depend on the `Repository` abstract base class via `Depends(get_repository)`. The factory in `repositories/__init__.py` selects the implementation based on `REPOSITORY_TYPE`. Both implementations must stay in sync: change `base.py` first, then both `memory.py` and `postgres.py`, then the affected routers.

## Authentication

In production, the backend validates Supabase JWTs in `core/security.py`. The token is read from the `Authorization: Bearer` header.

In `APP_ENV=local`, requests may use demo headers as a convenience for testing without a full auth flow:

```
x-demo-user-id: merchant-1
x-demo-name: Baqala Al Noor
x-demo-phone: +966500000001
```

These headers are ignored in `production`.

## Migrations

SQL migrations live in `supabase/migrations/` and are applied in filename order. When `REPOSITORY_TYPE=postgres`, they run automatically at startup. They can also be applied manually:

```powershell
supabase db reset
```

Do not edit existing migration files retroactively. Add a new numbered file for each schema change.

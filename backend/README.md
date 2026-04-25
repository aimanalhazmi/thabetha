# Thabetha Backend

FastAPI backend for the Thabetha modular monolith. Dependencies are managed with `uv`.

## Setup

```bash
uv sync
uv run uvicorn app.main:app --reload
```

## Quality Checks

```bash
uv run ruff check .
uv run pytest
```

## Environment

Copy `.env.example` to `.env` and fill values as needed.

| Variable | Purpose |
|---|---|
| `APP_ENV` | `local`, `staging`, or `production` |
| `SEED_DEMO_DATA` | Seeds in-memory demo data when `true` |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon key for client-compatible calls |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-side service role key |
| `SUPABASE_JWT_SECRET` | JWT verification secret for Supabase Auth tokens |
| `OPENAI_API_KEY` | Enables future real speech/chat integration |
| `WHATSAPP_PROVIDER` | `mock`, `twilio`, or `meta` adapter target |

## Local Auth

In `APP_ENV=local`, API requests can use demo headers instead of a Supabase JWT:

```text
x-demo-user-id: merchant-1
x-demo-name: Baqala Al Noor
x-demo-phone: +966500000001
```

In production, use `Authorization: Bearer <supabase-jwt>` and configure `SUPABASE_JWT_SECRET`.

## Module Layout

| Path | Responsibility |
|---|---|
| `app/api` | FastAPI routers |
| `app/core` | Settings and auth dependencies |
| `app/db` | Supabase client boundary |
| `app/repositories` | Persistence abstraction; local in-memory repository |
| `app/schemas` | Pydantic request/response contracts |
| `app/services` | Business helpers such as demo seed data |
| `tests` | Backend API and policy tests |


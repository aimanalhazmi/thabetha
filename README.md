# Thabetha

Thabetha is a bilingual fintech web application for managing informal debts and settlement workflows between local merchants, freelancers, service providers, individuals, and customers. It supports bilateral debt confirmation, QR-based identification, reminders, commitment indicators, group settlement flows, and AI-assisted merchant workflows.

## Core Features

- User authentication and profiles
- Creditor and debtor workflows
- Bilateral debt confirmation
- QR-based user identification
- Notifications and reminders
- Commitment indicator
- Groups and settlement workflows
- AI-assisted debt drafting and merchant chat
- Supabase-backed local development
- Docker-based full-stack run option

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, TypeScript, AR/EN i18n, RTL/LTR |
| Backend | FastAPI, Python 3.12, uv |
| Auth | Supabase Auth |
| Database | Supabase Postgres with RLS |
| Storage | Supabase Storage |
| Infrastructure | Docker Compose |
| Testing / Linting | pytest, Ruff, TypeScript strict, ESLint |

## Repository Structure

```
backend/          FastAPI app, repositories, schemas, tests
frontend/         React/Vite SPA, pages, components, i18n
supabase/         SQL migrations, seed data, CLI config
docs/             Product and developer documentation
docker-compose.yml  Full-stack container configuration
```

## Environment Secrets

The repository includes example environment files. Before running the app, copy each example file to a real local secrets file and fill in the values. These files contain credentials and must never be committed to version control.

```powershell
copy .env.example .env
copy backend\.env.example backend\.env
copy frontend\.env.example frontend\.env
```

After copying, populate the Supabase keys from the output of:

```powershell
supabase status -o env
```

### Variable Reference

Variables are split across three files. The root `.env` is consumed by Docker and repo-level tooling. `backend/.env` is read by the FastAPI process. `frontend/.env` is read by Vite at build/dev time.

#### Application

| Variable | File | Default | Description |
|---|---|---|---|
| `APP_ENV` | backend, root | `local` | Runtime environment. `local` enables demo-header auth; `production` disables it. |
| `REPOSITORY_TYPE` | backend | `memory` | `memory` (no DB, used in tests) or `postgres` (Supabase Postgres). |
| `SEED_DEMO_DATA` | backend | `false` | Seeds demo users and debts at boot. In-memory mode only. |

#### Supabase

| Variable | File | Description |
|---|---|---|
| `SUPABASE_URL` | backend, root | Supabase API URL. Local default: `http://127.0.0.1:55321`. |
| `SUPABASE_ANON_KEY` | backend, root | Public anon key. Safe to expose to the browser. |
| `SUPABASE_SERVICE_ROLE_KEY` | backend, root | Privileged server-side key. Never expose to the browser. |
| `SUPABASE_JWT_SECRET` | backend, root | HS256 secret used to validate Supabase access tokens. |
| `DATABASE_URL` | backend, root | Postgres connection string. Used when `REPOSITORY_TYPE=postgres`. |
| `VITE_SUPABASE_URL` | frontend | Supabase URL exposed to the browser via Vite. |
| `VITE_SUPABASE_ANON_KEY` | frontend | Supabase anon key exposed to the browser via Vite. |
| `VITE_API_BASE_URL` | frontend | Optional. API base URL. Defaults to `/api/v1` through the Vite proxy. |

#### Storage

| Variable | File | Default | Description |
|---|---|---|---|
| `SUPABASE_STORAGE_BUCKET_RECEIPTS` | backend, root | `receipts` | Bucket name for debt receipt uploads. |
| `SUPABASE_STORAGE_BUCKET_VOICE_NOTES` | backend, root | `voice-notes` | Bucket name for optional voice memos. |

#### AI and Integrations (optional)

| Variable | File | Description |
|---|---|---|
| `OPENAI_API_KEY` | backend | API key for OpenAI-compatible speech transcription. |
| `OPENAI_BASE_URL` | backend | Base URL for any OpenAI-compatible `/v1` endpoint (e.g. LM Studio, GWDG). |
| `OPENAI_TRANSCRIPTION_MODEL` | backend | Model used for speech-to-text. Example: `whisper-large-v2`. |
| `AI_TRANSCRIPTION_PROVIDER` | backend | `openai` or `mock`. |
| `CHAT_AI_BASE_URL` | backend | Base URL for the chat AI provider used in debt extraction. |
| `CHAT_AI_API_KEY` | backend | API key for the chat AI provider. Falls back to `OPENAI_API_KEY` if unset. |
| `CHAT_AI_EXTRACTION_MODEL` | backend | Model used for debt extraction from voice. |
| `AI_EXTRACTION_PROVIDER` | backend | `llm` (real model) or `regex` (rule-based fallback). |
| `MERCHANT_CHAT_PROVIDER` | backend | `chat_ai`, `anthropic`, `mock`, or `stub`. |
| `CHAT_AI_MERCHANT_CHAT_MODEL` | backend | Chat AI model used when `MERCHANT_CHAT_PROVIDER=chat_ai`. |
| `MERCHANT_CHAT_MODEL` | backend | Anthropic model used when `MERCHANT_CHAT_PROVIDER=anthropic`. |
| `ANTHROPIC_API_KEY` | backend | API key for the Anthropic provider. |
| `AI_MERCHANT_CHAT_DAILY_LIMIT` | backend | Max AI chat requests per user per day. Default: `50`. |
| `MERCHANT_CHAT_LOG_SALT` | backend | Salt used when hashing merchant chat logs. Change in production. |

#### WhatsApp

| Variable | File | Default | Description |
|---|---|---|---|
| `WHATSAPP_PROVIDER` | backend, root | `mock` | `mock`, `twilio`, or `meta`. |

#### Payment Gateway

| Variable | File | Default | Description |
|---|---|---|---|
| `PAYMENT_PROVIDER` | root | `mock` | `mock` or `tap`. |
| `TAP_SECRET_KEY` | root | — | Tap Payments secret key. |
| `TAP_WEBHOOK_SECRET` | root | — | Tap Payments webhook verification secret. |
| `TAP_FEE_PERCENT` | root | `2.75` | Processing fee percentage applied to settlements. |
| `PAYMENT_REDIRECT_BASE_URL` | root | `http://localhost:5173` | Base URL for post-payment redirect. |

## Local Setup

**Prerequisites:** Docker Desktop, Supabase CLI, Node.js, uv (Python package manager).

```powershell
# 1. Start Supabase (Auth + Postgres + Storage + Studio)
supabase start
supabase db reset

# 2. Configure environment secrets (see above)

# 3. Start the backend
cd backend
uv sync
uv run uvicorn app.main:app --reload

# 4. Start the frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Sign up and confirm your email via Inbucket at `http://127.0.0.1:55324`.

Full setup guide: [`docs/local-development.md`](./docs/local-development.md).

## Tests

```powershell
# Backend (in-memory repo, no database required)
cd backend
uv run pytest

# Frontend
cd frontend
npm run typecheck
npm run build
npm run test
```

## Docker Smoke Test

The root `Dockerfile` builds the React/Vite site and embeds `frontend/dist` into the FastAPI image, so a single container serves both `/api/v1/*` and the SPA on port 8000.

```powershell
supabase start
docker compose up --build web
```

Open `http://127.0.0.1:8000`.

## Key Documentation

- [`docs/product-requirements.md`](./docs/product-requirements.md) — problem, actors, features
- [`docs/debt-lifecycle.md`](./docs/debt-lifecycle.md) — canonical 7-state machine
- [`docs/pages-and-use-cases.md`](./docs/pages-and-use-cases.md) — actor to page mapping
- [`docs/mvp-scope.md`](./docs/mvp-scope.md) — MVP boundaries
- [`docs/local-development.md`](./docs/local-development.md) — full local setup walkthrough

## Contributing

When adding a debt status, enum value, page, or use case:

1. Update the matching document in `docs/`.
2. Update the canonical enum in `backend/app/schemas/domain.py`.
3. Add both Arabic and English strings to `frontend/src/lib/i18n.ts`.
4. Create a new migration file under `supabase/migrations/` — do not edit existing migration files retroactively.

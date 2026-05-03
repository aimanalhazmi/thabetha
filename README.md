# Thabetha · ثبتها

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Backend](https://img.shields.io/badge/backend-FastAPI%20%7C%20Python%203.12-009688.svg)](./backend)
[![Frontend](https://img.shields.io/badge/frontend-React%2019%20%7C%20Vite%20%7C%20TS-646CFF.svg)](./frontend)
[![Database](https://img.shields.io/badge/database-Supabase%20Postgres%20%2B%20RLS-3ECF8E.svg)](./supabase)

Thabetha is a bilingual (Arabic, English) fintech web application that turns the paper "debt notebook" used in local Arab markets into a **bilaterally-confirmed** digital ledger. It serves merchants, freelancers, service providers, and individuals who exchange informal credit and need a trustworthy, lightweight way to record, confirm, and settle debts.

> **Why "bilateral"?** A debt is binding only after the debtor accepts. A debt is `paid` only after the creditor confirms receipt. This single rule eliminates most of the disputes that plague paper ledgers and one-sided debt-tracking apps.

> **Built at [SalamHack 2026](https://salamhack.com/)** (27 April – 1 May 2026) by team Thabetha.

---

## Table of Contents

- [Core Features](#core-features)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
  - [Option A — Docker (recommended for first-time setup)](#option-a--docker-recommended-for-first-time-setup)
  - [Option B — Run backend and frontend in separate terminals](#option-b--run-backend-and-frontend-in-separate-terminals)
- [Environment Variables](#environment-variables)
- [Testing](#testing)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Authors](#authors)
- [License](#license)

---

## Core Features

- 🔐 Supabase Auth (email + password) with per-user data isolation enforced by Postgres RLS
- 🤝 Bilateral debt confirmation across a canonical 7-state lifecycle
- 📱 QR-based user identification for in-person debt creation
- 🔔 Reminders and notifications, with creditor-configurable due-date reminder dates
- 📊 Automatic commitment indicator (0–100) updated on payment events
- 👥 Group debts and netting / settlement workflows
- 🤖 Optional AI tier — voice-to-debt drafting and merchant chat (paid feature, gated)
- 🐳 Docker Compose for a one-command full-stack run, plus native dev mode

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, TypeScript (strict), AR/EN i18n with RTL/LTR |
| Backend | FastAPI, Python 3.12, Pydantic v2, [`uv`](https://docs.astral.sh/uv/) |
| Auth | Supabase Auth (`@supabase/supabase-js`, HS256 JWTs) |
| Database | Supabase Postgres with Row-Level Security |
| Storage | Supabase Storage (private buckets, signed URLs) |
| Infrastructure | Docker, Docker Compose, Supabase CLI |
| Quality | pytest, Ruff, TypeScript strict, ESLint, Vitest |

## Repository Structure

```
backend/             FastAPI app, repositories (memory + postgres), schemas, tests
frontend/            React/Vite SPA, pages, components, i18n
supabase/            SQL migrations, seed data, CLI config
scripts/             Operational helpers (e.g. dummy data)
Dockerfile           Multi-stage build: bundles frontend dist into the FastAPI image
docker-compose.yml   Single-container `web` service on :8000
LICENSE              MIT license
```

---

## Quick Start

**Prerequisites for both options:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) and the [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started).

```bash
# 1. Clone and enter the repo
git clone <repo-url> thabetha && cd thabetha

# 2. Create local secrets files from the templates
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 3. Boot Supabase (Auth + Postgres + Storage + Studio + Inbucket)
supabase start
supabase db reset       # applies migrations in supabase/migrations/ + seed.sql

# 4. Paste the printed keys into your .env files
supabase status -o env  # prints SUPABASE_ANON_KEY, SUPABASE_JWT_SECRET, etc.
```

After this, choose **one** of the two run modes below.

> **Note:** Tests do not need Supabase running — the test suite forces the in-memory repository (`REPOSITORY_TYPE=memory`). Skip steps 3–4 if you only intend to run tests.

### Option A — Docker (recommended for first-time setup)

A single container builds the React/Vite frontend and embeds `frontend/dist` into the FastAPI image. The result serves both `/api/v1/*` and the SPA on port `8000`.

```bash
docker compose up --build web
```

Open <http://127.0.0.1:8000>, sign up, and confirm your email through Inbucket at <http://127.0.0.1:55324>.

This is the fastest path to a working stack — no Node.js, no `uv`, no per-process terminal management. The container talks to the Supabase stack you started in step 3 above via `host.docker.internal`.

### Option B — Run backend and frontend in separate terminals

Use this mode for active development: hot-reload on both sides, faster iteration, full access to logs. **Open two terminals**, one for each process — the frontend dev server proxies `/api/*` to the backend, so both must be running concurrently.

**Additional prerequisites:** [Python 3.12](https://www.python.org/), [`uv`](https://docs.astral.sh/uv/), [Node.js 20 LTS](https://nodejs.org/).

**Terminal 1 — Backend (FastAPI on :8000):**

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

**Terminal 2 — Frontend (Vite dev server on :5173):**

```bash
cd frontend
npm install
npm run dev
```

Open <http://127.0.0.1:5173>, sign up, and confirm your email through Inbucket at <http://127.0.0.1:55324>.

For the full setup walkthrough, troubleshooting, and the round-trip verification flow, see [`docs/local-development.md`](./docs/local-development.md).

---

## Environment Variables

Variables are split across three files:

- `.env` — repo-root, consumed by Docker Compose and tooling that walks the root.
- `backend/.env` — read by the FastAPI process.
- `frontend/.env` — read by Vite at build/dev time. Only `VITE_*` variables are exposed to the browser.

### Application

| Variable | Files | Default | Description |
|---|---|---|---|
| `APP_ENV` | backend, root | `local` | Runtime environment. `local` enables demo-header auth; `production` disables it. |
| `REPOSITORY_TYPE` | backend | `memory` | `memory` (no DB, used in tests) or `postgres` (Supabase Postgres). |
| `SEED_DEMO_DATA` | backend | `false` | Seeds demo users and debts at boot. In-memory mode only. |
| `RLS_MODE` | backend | `enforce` | RLS enforcement mode for Postgres-backed runs. See `specs/010-backend-rls-enforcement/`. |

### Supabase

| Variable | Files | Description |
|---|---|---|
| `SUPABASE_URL` | backend, root | Supabase API URL. Local default: `http://127.0.0.1:55321`. |
| `SUPABASE_ANON_KEY` | backend, root | Public anon key. Safe to expose to the browser. |
| `SUPABASE_SERVICE_ROLE_KEY` | backend, root | Privileged server-side key. **Never** expose to the browser. |
| `SUPABASE_JWT_SECRET` | backend, root | HS256 secret used to validate Supabase access tokens. |
| `DATABASE_URL` | backend, root | Postgres connection string. Used when `REPOSITORY_TYPE=postgres`. |
| `VITE_SUPABASE_URL` | frontend | Supabase URL exposed to the browser. |
| `VITE_SUPABASE_ANON_KEY` | frontend | Supabase anon key exposed to the browser. |
| `VITE_API_BASE_URL` | frontend | Optional. API base URL. Defaults to `/api/v1` via the Vite proxy. |

### Storage

| Variable | Files | Default | Description |
|---|---|---|---|
| `SUPABASE_STORAGE_BUCKET_RECEIPTS` | backend, root | `receipts` | Bucket name for debt receipt uploads. |
| `SUPABASE_STORAGE_BUCKET_VOICE_NOTES` | backend, root | `voice-notes` | Bucket name for optional voice memos. |

### AI and integrations (optional)

| Variable | Files | Description |
|---|---|---|
| `OPENAI_API_KEY` | backend | API key for any OpenAI-compatible speech transcription endpoint. |
| `OPENAI_BASE_URL` | backend | Base URL for the OpenAI-compatible `/v1` endpoint (e.g. LM Studio, GWDG SAIA). |
| `OPENAI_TRANSCRIPTION_MODEL` | backend | Speech-to-text model (e.g. `whisper-large-v2`). |
| `AI_TRANSCRIPTION_PROVIDER` | backend | `openai` or `mock`. |
| `CHAT_AI_BASE_URL` | backend | Base URL for the chat AI provider used in debt extraction. |
| `CHAT_AI_API_KEY` | backend | API key for the chat AI provider. Falls back to `OPENAI_API_KEY` if unset. |
| `CHAT_AI_EXTRACTION_MODEL` | backend | Model used for debt extraction from voice. |
| `AI_EXTRACTION_PROVIDER` | backend | `llm` or `regex`. |
| `MERCHANT_CHAT_PROVIDER` | backend | `chat_ai`, `anthropic`, `mock`, or `stub`. |
| `CHAT_AI_MERCHANT_CHAT_MODEL` | backend | Chat AI model used when `MERCHANT_CHAT_PROVIDER=chat_ai`. |
| `MERCHANT_CHAT_MODEL` | backend | Anthropic model used when `MERCHANT_CHAT_PROVIDER=anthropic`. |
| `ANTHROPIC_API_KEY` | backend | API key for the Anthropic provider. |
| `AI_MERCHANT_CHAT_DAILY_LIMIT` | backend | Max AI chat requests per user per day (default: `50`). |
| `MERCHANT_CHAT_LOG_SALT` | backend | Salt used when hashing merchant chat logs. **Change in production.** |

### WhatsApp and payments

| Variable | Files | Default | Description |
|---|---|---|---|
| `WHATSAPP_PROVIDER` | backend, root | `mock` | `mock`, `twilio`, or `meta`. |
| `PAYMENT_PROVIDER` | root | `mock` | `mock` or `tap`. |
| `TAP_SECRET_KEY` | root | — | Tap Payments secret key. |
| `TAP_WEBHOOK_SECRET` | root | — | Tap Payments webhook verification secret. |
| `TAP_FEE_PERCENT` | root | `2.75` | Processing fee percentage applied to settlements. |
| `PAYMENT_REDIRECT_BASE_URL` | root | `http://localhost:5173` | Post-payment redirect base URL. |

> Never commit `.env` files. The repository's `.env.example` files are safe templates.

---

## Testing

```bash
# Backend (in-memory repository, no database required)
cd backend
uv run pytest
uv run ruff check --fix .

# Frontend
cd frontend
npm run typecheck
npm run test
npm run build
```

For the Postgres-backed RLS test suite, see [`specs/010-backend-rls-enforcement/quickstart.md`](./specs/010-backend-rls-enforcement/quickstart.md).

---

## Documentation

The canonical product and engineering docs live in [`docs/`](./docs/):

- [`docs/product-requirements.md`](./docs/product-requirements.md) — problem, actors, and feature catalog (English)
- [`docs/product-requirements-ar.md`](./docs/product-requirements-ar.md) — Arabic mirror
- [`docs/debt-lifecycle.md`](./docs/debt-lifecycle.md) — canonical 7-state machine
- [`docs/pages-and-use-cases.md`](./docs/pages-and-use-cases.md) — actor → page → use-case mapping
- [`docs/mvp-scope.md`](./docs/mvp-scope.md) — MoSCoW boundaries for the MVP
- [`docs/user-flows.md`](./docs/user-flows.md) — creditor / debtor / shared user flows
- [`docs/roadmap.md`](./docs/roadmap.md) — hackathon, post-MVP, and future work
- [`docs/local-development.md`](./docs/local-development.md) — full local setup walkthrough
- [`docs/supabase.md`](./docs/supabase.md) — Auth, DB, Storage, RLS, CLI workflow
- [`docs/demo-script.md`](./docs/demo-script.md) — narrated walk-through for demos

---

## Contributing

When adding a debt status, enum value, page, or use case:

1. Update the matching document in [`docs/`](./docs/).
2. Update the canonical enum in [`backend/app/schemas/domain.py`](./backend/app/schemas/domain.py).
3. Add both Arabic and English strings to [`frontend/src/lib/i18n.ts`](./frontend/src/lib/i18n.ts).
4. Create a new migration file under [`supabase/migrations/`](./supabase/migrations/) — never edit existing migrations retroactively.
5. Add a test for any new state transition.

Code style: Ruff (`line-length=150`, `py312`) for the backend; TypeScript strict + ESLint for the frontend.

---

## Authors

Thabetha (ثبتها) was built during [**SalamHack 2026**](https://salamhack.com/) (27 April – 1 May 2026) by:

- **Aiman Al-Hazmi**
- **Abdullah Al-Hakimi**
- **Mohamed Assaleh**
- **Ruba Mogalli**

---

## License

This project is licensed under the MIT License — see the [LICENSE](./LICENSE) file for details.

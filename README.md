# Thabetha

Thabetha is a web-based debt confirmation and settlement system for local merchants, customers, friends, and families. It replaces informal paper/WhatsApp debt records with bilateral confirmation, QR identity, reminders, trust scoring, groups, and optional AI-assisted entry.

## Architecture

| Layer | Implementation |
|---|---|
| Frontend | React, TypeScript, Vite, Arabic/English i18n, RTL/LTR support |
| Backend | FastAPI modular monolith, Python 3.12, `uv` dependency management |
| Auth/Data target | Supabase Auth, Postgres, Storage, RLS |
| Local/demo mode | In-memory repository with demo headers and optional seed data |
| Delivery | One Docker container serving API and built frontend |
| CI/CD | GitHub Actions checks backend/frontend/Docker and publishes GHCR on `main` |

## Local Development

Backend:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Production-style container:

```bash
docker compose up --build
```

The app is available at `http://localhost:8000` in Docker mode. The API health endpoint is `http://localhost:8000/api/v1/health`.

## Demo Users

| User | ID | Purpose |
|---|---|---|
| Baqala Al Noor | `merchant-1` | Creditor/shop owner |
| Ahmed | `customer-1` | Debtor/customer |
| Sara | `friend-1` | Group member |

Local mode accepts demo headers from the frontend:

```text
x-demo-user-id: merchant-1
x-demo-name: Baqala Al Noor
x-demo-phone: +966500000001
```

## Main Features

| Feature | Status |
|---|---|
| Supabase-ready auth/JWT boundary | Implemented |
| Profiles and business profile | Implemented |
| Rotating QR token flow | Implemented |
| Debt create/accept/reject/change-request | Implemented |
| Payment request/creditor confirmation | Implemented |
| Debtor and creditor dashboards | Implemented |
| Trust score and audit events | Implemented |
| In-app notifications and WhatsApp preference model | Implemented |
| Invoice/voice attachment endpoint | Implemented |
| Groups and settlement records | Implemented |
| AI voice draft and merchant chatbot stubs | Implemented |
| Docker and GitHub Actions | Implemented |

## Documentation

| Document | Purpose |
|---|---|
| [`backend/README.md`](./backend/README.md) | Backend setup and API notes |
| [`frontend/README.md`](./frontend/README.md) | Frontend setup and structure |
| [`docs/API_ENDPOINTS.md`](./docs/API_ENDPOINTS.md) | API endpoint map |
| [`docs/Database-Schema-Documentation.md`](./docs/Database-Schema-Documentation.md) | Supabase schema overview |
| [`supabase/migrations/001_initial_schema.sql`](./supabase/migrations/001_initial_schema.sql) | Initial database migration |


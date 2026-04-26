# Local Development

End-to-end setup for **Thabetha / ثبتها** on a developer laptop. Stack: Supabase CLI (Auth + Postgres + Storage + Studio) + FastAPI backend + Vite/React frontend.

## Requirements

| Tool | Version |
|---|---|
| [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started) | ≥ 1.200 |
| Docker Desktop | running (the Supabase CLI uses it) |
| Python | 3.12 |
| [`uv`](https://docs.astral.sh/uv/) | latest |
| Node.js | 20 LTS |

## Environment variables

Copy the examples and edit if you change ports:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

The defaults match the Supabase CLI's local ports (API `55321`, DB `55322`, Studio `55323`).

## 1. Start Supabase

```bash
supabase start
```

This boots Postgres, GoTrue (Supabase Auth), Storage, Realtime, Inbucket (mail catcher), and Studio in Docker. On first run it prints the anon key, service role key, and the local JWT secret — paste them into the `.env` files. After that you can run:

```bash
supabase status -o env
```

to print the same values without restarting.

Supabase Studio is at http://127.0.0.1:55323. Inbucket (sees signup confirmation emails) is at http://127.0.0.1:55324.

## 2. Apply migrations and seed

```bash
supabase db reset
```

This wipes the local database and re-applies every file in `supabase/migrations/` (currently `001_initial_schema.sql`, `002_commitment_and_lifecycle.sql`, `003_storage_policies.sql`) followed by `supabase/seed.sql`.

The backend can also apply migrations on its own startup if you set `REPOSITORY_TYPE=postgres` — that path is intended for the Docker build, not day-to-day dev.

## 3. Start the backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Listens on http://127.0.0.1:8000. With `APP_ENV=local` and `REPOSITORY_TYPE=memory` (the default), the backend uses an in-memory store and accepts demo headers for tests — useful when you don't need persistence. Set `REPOSITORY_TYPE=postgres` and `DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55322/postgres` to talk to the local Supabase Postgres.

Health check: `curl http://127.0.0.1:8000/api/v1/health`.

## 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Listens on http://127.0.0.1:5173. The frontend talks to Supabase Auth directly (via `@supabase/supabase-js`) and to the FastAPI backend for everything else.

## 5. Verify the round-trip

1. Open http://127.0.0.1:5173, click **Sign up**, create an account.
2. Confirm the email link from Inbucket (http://127.0.0.1:55324) — local Supabase does not send real email.
3. Sign in. The app should show the dashboard appropriate to your `account_type`.
4. Create a debt as a creditor; sign in as the debtor (different browser profile or incognito) and accept it.
5. Walk through `mark-paid` (debtor) → `confirm-payment` (creditor); the debt should land in `paid` and the debtor's commitment indicator update.

## Common gotchas

- **Port collisions**: change ports in `supabase/config.toml` if `55321`/`55322`/`55323` are taken. Update the matching `.env` values too.
- **`SUPABASE_JWT_SECRET` mismatch**: the backend rejects valid Supabase tokens if its secret doesn't match the value the CLI prints. Re-paste from `supabase status -o env`.
- **CORS errors from the frontend hitting Supabase**: the CLI ships permissive defaults; if you customised `auth.additional_redirect_urls` in `config.toml`, add `http://127.0.0.1:5173`.
- **`supabase db reset` fails with FK errors**: usually means the seed file references a profile id that no longer exists in `auth.users`. Sign up first, then re-seed; or comment the seed out (the default).
- **Tests don't touch Postgres**: `tests/conftest.py` forces `REPOSITORY_TYPE=memory`. To run integration tests against a real DB, override the env var manually.

## Useful commands

```bash
# Backend
cd backend
uv run pytest              # tests
uv run ruff check --fix .  # lint

# Frontend
cd frontend
npm run typecheck
npm run build

# Supabase
supabase stop --no-backup  # stop and discard volumes
supabase db diff           # see schema drift
```

# Supabase

How **Thabetha / ثبتها** uses Supabase: Auth, Postgres, Storage, and the local CLI workflow.

## Why Supabase

The product needs (a) email-password auth with email confirmation, (b) a Postgres with row-level security so a single API key cannot leak another user's debts, and (c) cheap private file storage for receipts and voice notes. Supabase bundles all three with a one-command local stack.

## Auth strategy

- The frontend signs up / signs in / refreshes via `@supabase/supabase-js`. Tokens live in browser storage managed by the SDK; we never roll our own.
- The backend treats every request as bearer-authenticated. `app/core/security.py::get_current_user` validates the JWT against `SUPABASE_JWT_SECRET` (HS256) and pulls the user id, email, phone, and `user_metadata.name` out of the claims.
- A thin proxy at `/api/v1/auth/*` exists for environments where the frontend cannot reach Supabase directly (e.g., reverse-proxy-only deploys). It forwards to the same Supabase Auth REST endpoints under the hood.
- In `APP_ENV != production` the backend additionally accepts demo headers (`x-demo-user-id`, `x-demo-name`, `x-demo-phone`) — used by `pytest` and quick local debugging only.

### Sign-up metadata

We pass `name`, `phone`, `account_type`, optional `tax_id`, and optional `commercial_registration` as `data` on signup. The Postgres trigger `handle_new_user()` (in `001_initial_schema.sql`, refreshed in `002_commitment_and_lifecycle.sql`) auto-creates a matching `public.profiles` row with `account_type = 'debtor'` if no value was supplied.

## Database strategy

Single `public` schema. Tables (see migrations for full DDL):

| Table | Purpose |
|---|---|
| `profiles` | One row per `auth.users` user; mirrors metadata + `commitment_score`. |
| `business_profiles` | Optional creditor sub-profile (shop name, activity, location). |
| `qr_tokens` | Rotating short-lived tokens used by the QR flow. |
| `debts` | The core entity. Status is the canonical 8-state enum from [`debt-lifecycle.md`](./debt-lifecycle.md). |
| `debt_events` | Append-only audit trail. Every state transition writes a row. |
| `payment_confirmations` | Pairs with a debt at the `payment_pending_confirmation` step. |
| `attachments` | Pointers to Storage objects (receipts, voice notes). |
| `notifications` | In-app notification feed; `whatsapp_attempted` records mock send-outs. |
| `commitment_score_events` | Append-only ledger of `commitment_score` deltas with reason. |
| `groups`, `group_members`, `group_settlements` | Post-MVP group debt; left in place behind a feature flag. |

The schema is owned by SQL migrations under `supabase/migrations/`. Apply with `supabase db reset` locally. The backend can also auto-apply at startup (`app/db/migrate.py`) when `REPOSITORY_TYPE=postgres`.

## Storage

Two private buckets, created by `002_commitment_and_lifecycle.sql`:

| Bucket | Path convention | Used for |
|---|---|---|
| `receipts` | `<debt_id>/<uuid>-<filename>` | Invoice photos, scanned bills. |
| `voice-notes` | `<debt_id>/<uuid>-<filename>` | Optional voice memos attached by either party. |

Both buckets are non-public. Read/write is gated by `003_storage_policies.sql`, which enforces that the caller is creditor or debtor of the debt encoded in the first path segment. Backend code reads/writes via signed URLs — never returns object bytes.

## Row-Level Security

RLS is enabled on every user-data table from `001_initial_schema.sql`. The shape is:

- **Profiles**: a user reads/updates only their own row, with one extra read-policy that lets a creditor read a debtor's profile (and vice-versa) when they share at least one debt.
- **Debts**: read/update gated to creditor or debtor of the row; insert gated to creditor.
- **Debt events / payment confirmations / attachments**: read access mirrors the parent debt's parties.
- **Commitment score events**: a user reads only their own deltas. Renamed in `002_*.sql` from the legacy `trust_score_events` table.
- **Groups**: visible to owner and accepted members.

Backend rollout is controlled by `RLS_MODE=off|shadow|enforce`.

| Role | Used by | Purpose |
|---|---|---|
| `authenticator` | request pool login | Has no direct table grants; can assume `app_authenticated`. |
| `app_authenticated` | request-scoped queries | Runs normal API reads/writes with `request.jwt.claims` set so policies decide row access. |
| `app_service` | system pool | Bypasses RLS for allow-listed system work such as the lazy commitment-score sweeper and signup trigger. |

`backend/app/repositories/__init__.py` creates two pools when RLS is active: `app_pool` for request work and `system_pool` for elevated work. Application code must not import `system_pool` directly; use `backend/app/repositories/system_tasks.py::elevated_connection()` for reviewed system paths. `GET /api/v1/healthz` exposes the current `rls_mode` so operators can verify flag changes.

## Local Supabase workflow

```bash
supabase start            # boot the stack
supabase db reset         # apply migrations + seed
supabase status -o env    # print URLs, keys, JWT secret
supabase stop --no-backup # tear down
```

Migrations are ordered by filename; new ones go in `supabase/migrations/NNN_description.sql`. After editing the schema:

1. Edit/add a migration file.
2. `supabase db reset` to verify it applies cleanly from scratch.
3. Update the backend repository (`app/repositories/postgres.py`) and Pydantic models if column names changed.
4. Run `cd backend && uv run pytest` — they use the in-memory repo but exercise the same Pydantic types.

## Production

For a hosted Supabase project, set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `DATABASE_URL`, and, when `RLS_MODE` is `shadow` or `enforce`, `APP_DATABASE_URL` and `SYSTEM_DATABASE_URL`. Migrations are applied with `supabase db push` against the remote project. The backend Docker image picks up these as environment variables.

# Constitution

Non-negotiable principles for **Thabetha / ثبتها**. Distilled from `CLAUDE.md`, `docs/product-requirements.md`, and `docs/debt-lifecycle.md`. Anything that contradicts a rule below is wrong by default.

## 1. Bilateral confirmation is the differentiator

- A debt is **binding only after the debtor accepts** (`pending_confirmation → active`).
- A debt is **`paid` only after the creditor confirms receipt** (`payment_pending_confirmation → paid`). Never go directly from `active` to `paid`.
- The debtor **cannot reject**. Their only pushback path is `request_edit`. The `rejected` status no longer exists (removed in migration 006).

## 2. Use the canonical 7-state lifecycle

States: `pending_confirmation`, `active`, `edit_requested`, `overdue`, `payment_pending_confirmation`, `paid`, `cancelled`. The transition table in [`../debt-lifecycle.md`](../debt-lifecycle.md) is exhaustive — any other transition must raise `409 Conflict`. String identifiers in DB, backend, and frontend must match exactly.

## 3. Commitment indicator, never "credit score"

- The product term is **commitment indicator / مؤشر الالتزام**.
- Stored in `profiles.commitment_score` (int, 0–100, default 50).
- Visible **only in bilateral context** where it was earned. Never published, never global, no public list.
- Updates are automatic and idempotent:
  - `+3` paid before `due_date`
  - `+1` paid on `due_date`
  - `−2 × 2^N` on each missed reminder (N = prior missed-reminder events on this debt)
  - `−2 × 2^N` on late payment (N = total missed reminders applied)
  - `−5` one-time on overdue sweep
  - clamped to `[0, 100]`
- Idempotency: missed-reminder events are unique on `(debt_id, reminder_date)` via partial index in migration 006.

## 4. Per-user data isolation

A user only ever sees debts where they are creditor, debtor, or accepted group member. Enforced **twice**:
1. In FastAPI handlers via `repo.get_authorized_debt(user.id, ...)` etc.
2. In Postgres via RLS policies (migrations 001, 005, 007).

The backend currently runs as the Postgres role and bypasses RLS at runtime — treat the policies as the **authoritative authorisation contract** and mirror them in handler code.

## 5. Arabic-first

- AR is default; EN is a runtime toggle with RTL/LTR switch.
- Every new user-facing string lands in `frontend/src/lib/i18n.ts` for **both** languages. No hardcoded strings.

## 6. Supabase-first stack

- **Auth**: Supabase Auth via `@supabase/supabase-js` on the frontend; backend validates `SUPABASE_JWT_SECRET` (HS256). The `/api/v1/auth/*` proxy is a thin wrapper around the same Supabase Auth REST endpoints — do not build a parallel auth system.
- **DB**: Supabase Postgres. Migrations in `supabase/migrations/` are auto-applied at backend startup when `REPOSITORY_TYPE=postgres`, or via `supabase db reset` locally.
- **Storage**: two private buckets — `receipts` and `voice-notes` — gated by RLS (`003_storage_policies.sql`). Path convention: `<bucket>/<debt_id>/<uuid>-<filename>`. Serve via signed URLs only.
- The `InMemoryRepository` (`REPOSITORY_TYPE=memory`) exists for tests and quick local debugging. Tests force this mode via `tests/conftest.py`.

## 7. Schemas are the single source of truth

- `backend/app/schemas/domain.py` defines all enums (`AccountType`, `DebtStatus`, `AttachmentType`, `NotificationType`, `GroupMemberStatus`).
- `frontend/src/lib/types.ts` mirrors them manually — keep in lockstep.
- New columns / enum values land in a **new** migration file. Don't edit `001_*.sql` retroactively.

## 8. Audit trail per debt

Every state transition appends a row to `debt_events` with `actor_id`, `event_type`, `message`, and structured `metadata` (jsonb). Created/confirmed/paid timestamps live on `debts` itself.

## 9. QR identity is bilateral and short-lived

- Tokens are random UUIDs, default TTL 10 minutes, rotated on demand.
- A token resolves to a profile **preview**, never raw credentials.
- The debtor's QR page and the creditor's scanner page are different components and never the same.

## 10. AI is paid-tier and hard-gated

`/api/v1/ai/*` returns `403` unless `profile.ai_enabled` is true. AI is never required for the MVP path.

## 11. MVP boundary

Hackathon target = UC1–UC8 minus the AI tier. Group debt (UC9) is post-MVP — endpoints exist but are not surfaced in MVP nav. AI (UC10) is paid-tier and gated. See [`../mvp-scope.md`](../mvp-scope.md) for MoSCoW.

## 12. Coding conventions

- Backend: Ruff (`line-length=150`, `py312`), Pyflakes, isort, pep8-naming, pyupgrade, flake8-bugbear. `E501` ignored.
- Frontend: TypeScript strict; pages in `pages/` (one per route), reusable parts in `components/`.
- Tests use `FastAPI.TestClient` via the `client` fixture, with `REPOSITORY_TYPE=memory` and demo `x-demo-*` headers. Add a test for any new state transition.

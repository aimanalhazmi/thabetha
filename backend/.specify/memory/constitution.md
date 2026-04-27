<!--
Sync Impact Report
==================
Version change: (uninitialized template) → 1.0.0
Bump rationale: Initial ratification — first concrete fill of the placeholder template.

Modified principles:
  - [PRINCIPLE_1_NAME] → I. Bilateral Confirmation Is The Differentiator
  - [PRINCIPLE_2_NAME] → II. Canonical 7-State Lifecycle
  - [PRINCIPLE_3_NAME] → III. Commitment Indicator, Never "Credit Score"
  - [PRINCIPLE_4_NAME] → IV. Per-User Data Isolation
  - [PRINCIPLE_5_NAME] → V. Arabic-First

Added sections:
  - Principles VI–X (Supabase-First Stack, Schemas Source of Truth, Audit Trail,
    QR Identity, AI Paid-Tier Gating)
  - Additional Constraints (MVP boundary)
  - Development Workflow & Quality Gates (coding conventions, tests)
  - Governance

Removed sections: none (template placeholders replaced).

Templates requiring updates:
  - ✅ .specify/templates/plan-template.md — generic "Constitution Check" gate
       remains valid; no edit required.
  - ✅ .specify/templates/spec-template.md — no constitution-specific tokens.
  - ✅ .specify/templates/tasks-template.md — no constitution-specific tokens.
  - ✅ CLAUDE.md (project root) — already aligned; constitution distilled from it.

Follow-up TODOs: none.
-->

# Thabetha / ثبتها Constitution

Non-negotiable principles for **Thabetha / ثبتها**, distilled from `CLAUDE.md`,
`docs/product-requirements.md`, and `docs/debt-lifecycle.md`. Anything that
contradicts a rule below is wrong by default.

## Core Principles

### I. Bilateral Confirmation Is The Differentiator

- A debt is **binding only after the debtor accepts** (`pending_confirmation → active`).
- A debt is **`paid` only after the creditor confirms receipt**
  (`payment_pending_confirmation → paid`). Direct `active → paid` transitions are forbidden.
- The debtor **MUST NOT reject**. Their only pushback path is `request_edit`. The
  `rejected` status no longer exists (removed in migration 006).

Rationale: bilateral confirmation is the product's reason to exist; bypassing it
collapses Thabetha into the very paper-notebook it replaces.

### II. Canonical 7-State Lifecycle

States: `pending_confirmation`, `active`, `edit_requested`, `overdue`,
`payment_pending_confirmation`, `paid`, `cancelled`. The transition table in
[`../../docs/debt-lifecycle.md`](../../docs/debt-lifecycle.md) is exhaustive — any
other transition MUST raise `409 Conflict`. String identifiers in DB, backend, and
frontend MUST match exactly.

### III. Commitment Indicator, Never "Credit Score"

- The product term is **commitment indicator / مؤشر الالتزام**.
- Stored in `profiles.commitment_score` (int, 0–100, default 50).
- Visible **only in bilateral context** where it was earned. Never published, never
  global, no public list.
- Updates are automatic and idempotent:
  - `+3` paid before `due_date`
  - `+1` paid on `due_date`
  - `−2 × 2^N` on each missed reminder (N = prior missed-reminder events on this debt)
  - `−2 × 2^N` on late payment (N = total missed reminders applied)
  - `−5` one-time on overdue sweep
  - clamped to `[0, 100]`
- Idempotency: missed-reminder events are unique on `(debt_id, reminder_date)` via
  partial index in migration 006.

### IV. Per-User Data Isolation

A user only ever sees debts where they are creditor, debtor, or accepted group
member. Enforced **twice**:

1. In FastAPI handlers via `repo.get_authorized_debt(user.id, ...)` etc.
2. In Postgres via RLS policies (migrations 001, 005, 007).

The backend currently runs as the Postgres role and bypasses RLS at runtime —
treat the policies as the **authoritative authorisation contract** and mirror them
in handler code.

### V. Arabic-First

- AR is default; EN is a runtime toggle with RTL/LTR switch.
- Every new user-facing string lands in `frontend/src/lib/i18n.ts` for **both**
  languages. No hardcoded strings.

### VI. Supabase-First Stack

- **Auth**: Supabase Auth via `@supabase/supabase-js` on the frontend; backend
  validates `SUPABASE_JWT_SECRET` (HS256). The `/api/v1/auth/*` proxy is a thin
  wrapper around the same Supabase Auth REST endpoints — do not build a parallel
  auth system.
- **DB**: Supabase Postgres. Migrations in `supabase/migrations/` are auto-applied
  at backend startup when `REPOSITORY_TYPE=postgres`, or via `supabase db reset`
  locally.
- **Storage**: two private buckets — `receipts` and `voice-notes` — gated by RLS
  (`003_storage_policies.sql`). Path convention:
  `<bucket>/<debt_id>/<uuid>-<filename>`. Serve via signed URLs only.
- The `InMemoryRepository` (`REPOSITORY_TYPE=memory`) exists for tests and quick
  local debugging. Tests force this mode via `tests/conftest.py`.

### VII. Schemas Are The Single Source Of Truth

- `backend/app/schemas/domain.py` defines all enums (`AccountType`, `DebtStatus`,
  `AttachmentType`, `NotificationType`, `GroupMemberStatus`).
- `frontend/src/lib/types.ts` mirrors them manually — keep in lockstep.
- New columns / enum values land in a **new** migration file. Don't edit
  `001_*.sql` retroactively.

### VIII. Audit Trail Per Debt

Every state transition appends a row to `debt_events` with `actor_id`,
`event_type`, `message`, and structured `metadata` (jsonb). Created / confirmed /
paid timestamps live on `debts` itself.

### IX. QR Identity Is Bilateral And Short-Lived

- Tokens are random UUIDs, default TTL 10 minutes, rotated on demand.
- A token resolves to a profile **preview**, never raw credentials.
- The debtor's QR page and the creditor's scanner page are different components
  and never the same.

### X. AI Is Paid-Tier And Hard-Gated

`/api/v1/ai/*` returns `403` unless `profile.ai_enabled` is true. AI is never
required for the MVP path.

## Additional Constraints

**MVP boundary.** Hackathon target = UC1–UC8 minus the AI tier. Group debt (UC9)
is post-MVP — endpoints exist but are not surfaced in MVP nav. AI (UC10) is
paid-tier and gated. See [`../../docs/mvp-scope.md`](../../docs/mvp-scope.md) for
MoSCoW.

## Development Workflow & Quality Gates

- **Backend**: Ruff (`line-length=150`, `py312`), Pyflakes, isort, pep8-naming,
  pyupgrade, flake8-bugbear. `E501` ignored.
- **Frontend**: TypeScript strict; pages in `pages/` (one per route), reusable
  parts in `components/`.
- **Tests**: `FastAPI.TestClient` via the `client` fixture, with
  `REPOSITORY_TYPE=memory` and demo `x-demo-*` headers. Add a test for any new
  state transition.

## Governance

This constitution supersedes ad-hoc practice. Where code, docs, or PR review
disagree with a rule above, the constitution wins until formally amended.

- **Amendment procedure**: a PR that edits this file MUST (a) state the
  motivation, (b) update the version per the policy below, (c) update
  `Last Amended`, and (d) propagate changes to dependent templates and docs
  listed in the Sync Impact Report.
- **Versioning policy** (semantic):
  - **MAJOR**: backward-incompatible governance or principle removal/redefinition.
  - **MINOR**: new principle/section added or materially expanded guidance.
  - **PATCH**: clarifications, wording, typo fixes, non-semantic refinements.
- **Compliance review**: every PR description SHOULD note whether it touches a
  principle area (lifecycle, RLS, i18n, schemas, AI gating, QR, storage). The
  `Constitution Check` gate in `.specify/templates/plan-template.md` is the
  enforcement point during planning. Runtime developer guidance lives in
  [`../../CLAUDE.md`](../../CLAUDE.md).

**Version**: 1.0.0 | **Ratified**: 2026-04-27 | **Last Amended**: 2026-04-27

# Project Status — 2026-04-27

Snapshot of what is shipped, in flight, and pending. Working branch: `spec-kit-initialization` (up to date with `develop`).

## Recent merges (last 6 commits, develop ←)

```
ef2f10b Merge pull request #6 from aimanalhazmi/feature/debt-edit-request
d0146ef feat: inline debt-edit thread + creditor amend on approve
2ceb740 feat: support partial business profile updates via profile endpoint
deefc60 feat: implement debt edit request flow and commitment indicator logic
8abc7b1 Merge pull request #5 from aimanalhazmi/cleanup/supabase-first-refactor
88b7ff3 refactor: align repository with Supabase schema and lifecycle
```

## Shipped

- **Supabase-first stack** — Auth + Postgres + Storage + RLS, migrations 001..007 auto-applied at backend startup.
- **Canonical lifecycle** (now 7 states after 006 dropped `rejected`).
- **Commitment indicator** rename + automatic update logic with idempotent missed-reminder penalties (`commitment_score_events.reminder_date` + partial unique index in migration 006).
- **Reminder dates per debt** (`debts.reminder_dates date[]`) configured by creditor at creation.
- **Debt edit-request flow** — debtor-initiated `request_edit`, creditor `approve` (amends terms, returns to `pending_confirmation`) or `reject` (original terms, returns to `pending_confirmation`). Inline thread on debt details page.
- **Role-based dashboards** — `/dashboard` resolves to creditor or debtor view based on `account_type`.
- **Per-user data isolation** — RLS policies on `profiles`, `business_profiles`, `debts`, `notifications`, `payment_confirmations`, `attachments`, `group_settlements`, `commitment_score_events`. Storage RLS on `receipts` / `voice-notes`.
- **Auth proxy** — `/api/v1/auth/{signup,signin,refresh,signout}` wrapping Supabase Auth REST.
- **QR identity** — rotating short-lived tokens, profile-preview resolution.
- **In-app notifications** with read tracking and per-creditor WhatsApp opt-out preference.
- **Group endpoints** (post-MVP) — exist behind nav, not yet surfaced in MVP UI.
- **AI stubs** (`debt-draft-from-voice`, `merchant-chat`) gated by `profile.ai_enabled`.
- **Partial business-profile updates** through `PATCH /profiles/me` (commit 2ceb740).

## In progress / pending (MVP)

- Polished bilingual UI (Arabic-first, English toggle) — strings exist in `lib/i18n.ts`, but coverage and RTL polish are not complete.
- End-to-end demo path: signup → create debt → bilateral confirm → mark-paid → confirm → indicator updates.
- **Receipt upload on Create Debt** (UC2) — create-debt UI accepts image/PDF receipts, uploads them after debt creation, lists signed receipt links on debt cards, and preserves failed uploads for retry.
- **QR scanner pass-through on Create Debt** (UC4 → UC2) — scanner page exists, hand-off to create-debt with prefilled `debtor_id` is not wired.
- Cancel-non-binding-debt UX (creditor) — backend endpoint exists, UI partial.
- Per-creditor WhatsApp opt-out enforcement on the actual sender (currently mock provider).

## Out of scope for MVP (per `../mvp-scope.md`)

- Real WhatsApp Business API integration (mock provider only today).
- Real payment gateway / settlement.
- Group debt with auto-netting (UC9 — endpoints exist, no MVP nav).
- Advanced AI (behaviour analysis, fraud detection, payment-likelihood prediction).
- Micro-credit, formal contracts, multi-country compliance.

## Known technical debt / risks

- **Backend runs as Postgres role**, so RLS is bypassed at runtime. Defence-in-depth is in handler code; switch to scoped JWTs is on the post-MVP roadmap.
- **Storage buckets duplication** — migration 001 created a legacy `thabetha-attachments` bucket; receipt upload now defaults to canonical `receipts`, and the legacy bucket still exists.
- **Migration 004** is largely a no-op safety net (idempotent enum adds) added before 005/006; safe to keep.
- `frontend/src/lib/types.ts` mirrors backend enums **manually** — drift is possible when adding new enum values.

## Branch state

- `develop`: stable, contains everything in "Shipped" above (PR #6 merged).
- `spec-kit-initialization`: current working branch — adds `docs/spec-kit/` and the `.specify/` scaffolding; up to date with `develop`.

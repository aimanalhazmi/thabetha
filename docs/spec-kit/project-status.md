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

- ~~Polished bilingual UI (Arabic-first, English toggle)~~ ✅ **Shipped** (Phase 5 — branch `004-bilingual-coverage-audit`) — full AR/EN coverage sweep (25 Blocker/Major findings, all fixed), ESLint v9 flat config with `react/jsx-no-literals` + custom `no-untranslated-jsx` prop rule (19/20 calibration catch rate), Vitest per-page locale tests (18 passing), `profiles.preferred_language` persisted to Supabase, `<html lang dir>` set without first-paint flicker.
- **Receipt upload on Create Debt** (UC2) — create-debt UI accepts image/PDF receipts, uploads them after debt creation, lists signed receipt links on debt cards, and preserves failed uploads for retry.
- ~~**QR scanner pass-through on Create Debt**~~ ✅ **Shipped** (UC4 → UC2) — scanner confirm step, `/debts?qr_token=` deep link, prefilled-and-locked debtor identity, re-resolve on submit, expired/self/error handling, bilingual strings (AR+EN), backend self-billing 409 guard, integration test.
- ~~**Cancel non-binding debt UX (creditor)**~~ ✅ **Shipped** (Phase 3) — two-tap confirmation dialog with optional message (≤ 200 chars), hidden for all non-cancellable states and for the debtor, post-cancel page stays on debt details, 8 backend tests, 6 AR+EN i18n keys.
- ~~**End-to-end demo path**~~ ✅ **Shipped** (Phase 4) — `humanizeError` helper eliminates raw API errors from all four MVP pages, loading states on all transition buttons, translated empty-states, canonical happy-path + edit-request-branch integration tests (`commitment_score == 53`), self-serve demo script at `docs/demo-script.md`.
- ~~Per-creditor WhatsApp opt-out enforcement on the actual sender (currently mock provider).~~ ✅ **Shipped** (Phase 6 — branch `006-whatsapp-business-integration`)
- ~~**Real WhatsApp Business API integration**~~ ✅ **Shipped** (Phase 6 — branch `006-whatsapp-business-integration`) — `WhatsAppProvider` ABC; `MockWhatsAppProvider` (tests/dev) + `CloudAPIWhatsAppProvider` (Meta Graph API); opt-out enforcement (global + per-creditor); per-message delivery state; HMAC-verified idempotent webhook; `WebhookReceiptOut` response model; 26 new tests; delivery badge on creditor notifications view; AR+EN i18n for all failure reason codes.

## Out of scope for MVP (per `../mvp-scope.md`)
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

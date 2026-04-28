# Phase 0 — Research: End-to-End Demo Polish

**Date**: 2026-04-28
**Feature**: 003-e2e-demo-polish

The spec has no `[NEEDS CLARIFICATION]` markers after `/speckit-clarify`. This document captures the implementation-direction decisions that ground the polish sweep.

## R1 — How errors currently leak to the UI

- **Finding**: `frontend/src/lib/api.ts:32` throws `new Error(\`${response.status}: ${text}\`)` for any non-2xx response. Pages then `catch` and call `setMessage(err instanceof Error ? err.message : 'Failed to load')` (e.g., `DebtsPage.tsx:188`, `DebtsPage.tsx:391`). This surfaces strings like `409: Active or paid debts cannot be cancelled` to the user — backend English copy regardless of locale, with a status code prefix.
- **Decision**: Introduce `humanizeError(err: unknown, language: Language, context?: ErrorContext): string` in a new `frontend/src/lib/errors.ts`. The helper parses the `apiRequest`-thrown Error shape (`"<status>: <body>"`) and returns a translated string keyed on (status code, optional context). Default fallback is `tr('errorGeneric')` per locale. Page-level catches replace `err.message` with `humanizeError(err, language, '<context>')`.
- **Alternatives considered**: (a) Change `apiRequest` itself to throw a structured error class — rejected because it expands the blast radius beyond this phase and risks breaking other callers; the helper sits next to the existing throw and does the parsing on read. (b) Replace fetch with a fetch-wrapper hook — rejected as scope creep.

## R2 — Error contexts that need distinct messages

After scanning the four target pages, the contexts that need their own translated string (rather than the generic fallback) are:

- `loadDebts` (GET /debts failure): "Couldn't load your debts. Please retry."
- `loadDashboard` (GET /dashboard/* failure): "Couldn't load your dashboard. Please retry."
- `loadNotifications` (GET /notifications failure): "Couldn't load your notifications. Please retry."
- `transition` (POST /debts/{id}/{action} 409): "This debt's status changed — please refresh." (separate from existing `cancel_debt_state_changed`; reused for all transition 409s.)
- `qrResolve` (GET /qr/resolve/{token} 404 or 410): "QR expired, ask the customer to refresh their code." (key already exists per Phase 2's i18n keys.)
- Generic 500 / network failure: `errorGeneric`.

These map to ~5 new i18n keys plus reuse of 1 existing key. Plus the four pages each need 1 empty-state key (debts, dashboard sections, notifications, QR), some of which already exist (e.g., `noDebtsYet`).

## R3 — Pre-seeded demo data is sufficient

- **Finding**: `backend/app/services/demo_data.py` already creates two accounts (`merchant-1` "Baqala Al Noor" + `customer-1` "Ahmed") plus an active debt and a paid debt, gated by `SEED_DEMO_DATA=true`. This matches the clarified Q1 ("pre-seeded accounts" path).
- **Decision**: The demo script begins with "ensure `SEED_DEMO_DATA=true` is set in `backend/.env`" then "sign in as merchant-1" — but for **Supabase Auth**, the test accounts must exist in Supabase Auth too, not just the in-memory repo. For the demo script's purposes on local Supabase, the simplest path is to (a) ask the contributor to run signup once in `docs/local-development.md` to create the two Supabase Auth users, or (b) include a one-time seed step in the demo script. We choose (b): a single optional Step 0 in the demo script that says "if accounts don't exist yet, sign up `merchant@thabetha.local` and `customer@thabetha.local` once via Inbucket — then bookmark this step as done". This preserves the 5-minute budget on subsequent runs.
- **Alternatives considered**: Adding Supabase Auth seeding to backend startup — rejected as cross-cutting infrastructure work not in scope. Documenting the seed in `local-development.md` — accepted **in addition** to the script's Step 0, so a contributor following either path lands in the same place.

## R4 — Integration test will use demo headers, not Supabase Auth

- **Finding**: Existing tests (`backend/tests/test_debt_lifecycle.py`) use `auth_headers(user_id, ...)` which sets `x-demo-*` headers — accepted in non-production mode (`backend/app/core/security.py`). This is the constitution-blessed pattern for integration tests.
- **Decision**: The new `test_e2e_demo_path.py` uses `auth_headers` with two demo user ids (e.g., `"creditor-demo"` / `"debtor-demo"`) and the same `client` + `reset_repository` fixtures as the existing tests. No Supabase Auth involvement.
- **Alternatives considered**: Driving the test through real Supabase JWTs — rejected; the `x-demo-*` path is what `conftest.py` is designed for.

## R5 — Test asserts the commitment-score delta from the lifecycle doc

- **Finding**: `docs/debt-lifecycle.md` (and constitution §III) says `+3` if paid before `due_date`, `+1` on `due_date`. Existing test `test_two_party_debt_and_payment_lifecycle` already asserts `commitment_score == 53` (50 base + 3 early-payment). 
- **Decision**: The new happy-path test mirrors that pattern: create debt with `due_date = today + 2`, transition through accept → mark-paid → confirm-payment, then assert `commitment_score == 53` on the debtor's dashboard. The edit-request branch test additionally asserts `+3` after the creditor approves new terms and the debtor accepts — same delta because final `due_date` is still in the future at payment time.
- **Alternatives considered**: Asserting individual `commitment_score_events` rows — rejected as over-specification; the dashboard score is the user-visible contract.

## R6 — Combined test runtime budget

- **Finding**: Existing `pytest -q` runs 21 tests in ~1.7 seconds locally. Two new tests with ~6–8 transitions each will add well under 1 second.
- **Decision**: Trust the existing fixture overhead; do not optimise. SC-005's budget (combined < 5 s) has plenty of headroom.

## R7 — Demo script length: counting + sample structure

- **Decision**: Eleven steps. Outline:
  1. Prereqs check (Supabase + backend + frontend running)
  2. (Optional, one-time) Sign up two demo accounts via Inbucket
  3. Sign in as the creditor
  4. Open creditor's QR scanner; scan debtor's QR
  5. Create a debt (with one receipt) prefilled from QR
  6. Sign in as the debtor in another window
  7. Either: Accept (happy path) **or** Request edit + Accept (branch)
  8. Mark paid as debtor
  9. Sign in as creditor; confirm payment
  10. Verify commitment indicator on debtor's dashboard
  11. (Optional) Toggle UI to Arabic and re-execute step 7 to spot any RTL issue

That is 11 steps, fits one printed page, covers happy path + branch.

## R8 — Untranslated-string capture mechanism

- **Decision**: Maintain a single section in the PR description titled "Phase 5 hand-off — untranslated strings", with each entry as a path:line reference and the offending literal. Do **not** create a tracking file in the repo (would dangle if Phase 5 lands in a different sprint). The PR description survives indefinitely on GitHub.
- **Alternatives considered**: A new `docs/spec-kit/i18n-debt.md` — rejected; the file would need a follow-up PR to delete.

## R9 — Per-page rough-edge inventory (preliminary, planner-level)

A first-pass scan to seed the implementation tasks. Final list lives in `tasks.md`.

| Page | Likely rough edges (planner read, not exhaustive) |
|------|---------------------------------------------------|
| `DebtsPage.tsx` | Action buttons (accept/mark-paid/confirm/edit) lack disabled state during `runAction`; catch in `runAction` (line 391) leaks `err.message`; create-debt form load failure uses raw English fallback. |
| `DashboardPage.tsx` | Already has a `loading` empty-state but error path likely raw; sub-panels (overdue, recent debts) may render blank when empty. |
| `NotificationsPage.tsx` | TBD — verify catch path, empty-state, and that mark-as-read is non-blocking. |
| `QRPage.tsx` | Verify expired-token error is translated; verify scanner empty/idle state has copy. |

## Open questions

None. All decisions above are firm. Proceed to Phase 1.

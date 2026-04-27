# Quickstart — QR-scanner pass-through to Create Debt

A reviewer should be able to validate this feature end-to-end against a local Supabase stack in under five minutes.

## Prerequisites

- `supabase start` running (Auth + DB + Storage + Studio in Docker).
- Backend running: `cd backend && uv run uvicorn app.main:app --reload`.
- Frontend running: `cd frontend && npm run dev`.
- Two browsers (or one normal + one private window) so two users can be signed in simultaneously.

## Walkthrough

### Setup — two test users

1. In Browser **A**, sign up as `creditor@test.local` and confirm the email via Inbucket (`http://127.0.0.1:55324`).
2. In Browser **B**, sign up as `debtor@test.local` and confirm the email.

### Happy path — QR scan → prefilled Create Debt → submit

3. In Browser **B** (debtor), navigate to the QR page (`/qr`) and let the page render the debtor's QR token.
4. In Browser **A** (creditor), navigate to `/qr` (the scanner half).
5. Scan the QR shown in Browser B (use the camera, or paste the token if the scanner exposes a manual-input mode for development).
6. **Expected**: an overlay appears on the scanner showing the debtor's name, the last 4 digits of their phone, and their commitment indicator badge, with two actions — "Create debt for this person" and "Cancel".
7. Tap "Create debt for this person".
8. **Expected**: navigation to `/debts/new?qr_token=<token>`. The Create Debt form renders with:
   - A preview header above the form: name, last-4 phone, commitment indicator.
   - The debtor name field locked, with the `scanned_debtor_label` indicator.
   - A visible "clear / change debtor" link.
   - All debt fields (amount, currency, description, due date, reminders) editable.
9. Fill in amount, currency, and description; tap submit.
10. **Expected**: debt is created. The URL on the resulting page no longer contains `qr_token`. Hitting back **does not** restore the prefilled state — it lands in the manual-entry view.
11. In Browser **B** (debtor), refresh the dashboard. **Expected**: the new `pending_confirmation` debt appears, attributed to creditor A, with the correct amount.

### Error path 1 — Expired token at submit

12. In Browser **A**, scan a fresh token, confirm on the overlay, and arrive on `/debts/new?qr_token=...`.
13. Fill the amount and description but **don't submit yet**.
14. In Browser **B**, rotate the QR (`POST /qr/rotate` via the QR page UI). The previous token is now expired.
15. In Browser **A**, tap submit.
16. **Expected**: the preview header is replaced by the translated `qr_expired_ask_refresh` banner with "Rescan" + "Switch to manual entry" actions. The amount and description fields **still hold** the values you typed (per SC-004).

### Error path 2 — Self-scan

17. In Browser **A**, navigate to `/qr` (the QR page) and grab the *creditor's own* token.
18. Manually open `/debts/new?qr_token=<own-token>` in Browser A.
19. **Expected**: the preview is replaced by the translated `cannot_bill_self` message; the submit affordance is hidden entirely (not just disabled). The "clear / change debtor" link remains, and tapping it reverts to manual entry.

### Manual-path regression

20. In Browser **A**, navigate to `/debts/new` (no `qr_token`).
21. **Expected**: form is exactly as it was before this feature — debtor field editable, no preview header, manual entry works and produces a debt without a `debtor_id`.

## Bilingual check

22. Toggle the locale to Arabic. Re-walk steps 6, 16, and 19. **Expected**: all four new strings (`qr_expired_ask_refresh`, `cannot_bill_self`, `clear_debtor`, `scanned_debtor_label`) render in Arabic with correct RTL alignment. No `missing.key.X` placeholders.

## Backend integration test

The integration test that locks this in (`backend/tests/test_create_debt_with_debtor_id.py`) runs as part of `uv run pytest`. It:

1. Creates two demo users (creditor A, debtor B).
2. Calls `GET /qr/current` as B, then `GET /qr/resolve/{token}` as A.
3. Calls `POST /debts` as A with both `debtor_id` and `debtor_name` derived from the resolve response.
4. Asserts that the debt appears in B's debt list and is linked via `debtor_id` (not just by free-text name).

Failing this test means the QR pass-through has lost its identity guarantee.

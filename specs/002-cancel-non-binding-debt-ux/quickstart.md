# Quickstart — Cancel Non-Binding Debt UX

**Feature**: 002-cancel-non-binding-debt-ux
**Audience**: Developer or reviewer verifying the feature end-to-end on local Supabase.
**Time**: ~5 minutes.

## Prerequisites

1. `supabase start` (Docker) — Auth + DB + Storage + Studio running.
2. Backend on `:8000` (`cd backend && uv run uvicorn app.main:app --reload`).
3. Frontend on `:5173` (`cd frontend && npm run dev`).
4. Two demo accounts available (one creditor, one debtor) — either seed via `SEED_DEMO_DATA=true` or sign up two emails through the UI and confirm via Inbucket (`http://127.0.0.1:55324`).

## Verification script

### Step 1 — Create a non-binding debt

1. Sign in as the creditor.
2. Navigate to `/debts` → "New debt".
3. Enter the debtor (manually or via QR), amount, due date.
4. Submit. Verify the new debt appears in the list with status `pending_confirmation`.

### Step 2 — Cancel without a message (US1, two-tap path)

1. Click the "Cancel debt" button on the new debt card.
2. **Assert**: a dialog opens centered on screen with title "Cancel this debt?", a body paragraph, an empty textarea with the optional-reason placeholder, and confirm + dismiss buttons.
3. Click the confirm button (do not type anything).
4. **Assert**:
   - The dialog closes.
   - A success toast reads "Debt cancelled".
   - The debt card now shows status `cancelled`.
   - The "Cancel debt" button is gone from the card.
   - The page URL has not changed (you are still on the debts page) — FR-011.

### Step 3 — Cancel with a message (US2)

1. Create a second debt (Step 1).
2. From the debtor account in another browser/incognito, click "Request edit" on the debt with a short message — the debt moves to `edit_requested`.
3. Switch back to the creditor.
4. Click "Cancel debt" on the now-`edit_requested` debt.
5. Type a 30-character message: e.g., "Wrong amount, will re-issue tomorrow".
6. Click confirm.
7. **Assert**:
   - Status becomes `cancelled`.
   - Sign in as the debtor and open notifications → the latest entry is `debt_cancelled` and its body contains the typed message verbatim.

### Step 4 — Dismiss without confirming

1. Create another `pending_confirmation` debt.
2. Click "Cancel debt".
3. Type any message.
4. Click the dismiss button (or press Escape, or click outside the modal).
5. **Assert**: dialog closes; debt status is unchanged; no notification fired for the debtor.

### Step 5 — Disallowed-state hiding (US3)

1. Have a debt in `active` (debtor accepts).
2. View it as creditor.
3. **Assert**: no "Cancel debt" button is rendered.
4. Repeat for `payment_pending_confirmation`, `paid`, and `cancelled` — none should show the button.

### Step 6 — Concurrent state change (edge case)

1. Open two browsers as the creditor on the same `pending_confirmation` debt.
2. In window A, open the cancel dialog (do not confirm).
3. In window B (or from the debtor account), accept the debt — it moves to `active`.
4. In window A, click confirm.
5. **Assert**:
   - Dialog stays open.
   - Translated error appears inside the dialog: "This debt can no longer be cancelled — its status changed." (key `cancel_debt_state_changed`).
   - Page list refreshes; once the dialog is dismissed, the cancel button is gone (status is now `active`).

### Step 7 — Bilingual coverage

1. Toggle the UI to Arabic.
2. Repeat Step 2 (empty-message cancel).
3. **Assert**:
   - Dialog text renders in Arabic, RTL-aligned.
   - The success toast is in Arabic.
   - No `missing.key.x` artifacts visible anywhere in the dialog or toast.

## Backend regression check (constitution §12)

```bash
cd backend
uv run pytest tests/ -k cancel -q
```

**Assert**: existing transition tests pass (positive `pending_confirmation → cancelled` and `edit_requested → cancelled`; negative `active → cancel = 409`). If a test for empty-message cancel doesn't exist yet, the implementer should add one.

## Done when

- Steps 1–7 above all pass.
- The integration test from `backend/tests/` is green.
- The PR description ticks the Phase 3 deliverable checklist from `docs/spec-kit/implementation-plan.md`.

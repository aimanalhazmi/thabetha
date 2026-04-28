# Thabetha / ثبتها — Demo Script

**Target time**: ≤ 5 minutes · **Audience**: fresh contributor or hackathon judge · **Stack**: local Supabase

## Prerequisites (do once before the timer starts)

- `supabase start` — Supabase stack running
- `cd backend && uv run uvicorn app.main:app --reload` — API on `:8000`
- `cd frontend && npm run dev` — UI on `:5173`
- Two demo accounts exist in Supabase Auth (see Step 0 below)

---

## Step 0 — (One-time) Create two demo accounts

> Skip this step on every run after the first.

1. Open `http://127.0.0.1:5173` → **Sign up** as `merchant@thabetha.local` (account type: **Creditor / Shop owner**).
2. Confirm via Inbucket at `http://127.0.0.1:55324`.
3. Sign up as `customer@thabetha.local` (account type: **Debtor / Customer**). Confirm via Inbucket.

---

## Step 1 — Sign in as the creditor

Sign in as `merchant@thabetha.local`. You land on the **Dashboard**. Note the commitment indicator (should be 50 for a new debtor).

## Step 2 — Debtor shows their QR code

In another browser window (incognito), sign in as `customer@thabetha.local`. Navigate to **QR** → copy or note the token shown under the QR code.

## Step 3 — Creditor scans the QR

Back in the creditor window, go to **QR** → paste the debtor's token into the scanner field → click **Lookup**. The debtor's name and commitment indicator appear.

## Step 4 — Create a debt (prefilled from QR)

Click **Create debt for this person**. The create-debt form opens with the debtor's name locked. Fill in:
- Amount: `75.00 SAR`
- Description: `Demo groceries`
- Due date: any date in the future

Attach one receipt photo (any image file). Click **Create**. The debt appears in the list with status **Pending confirmation**.

## Step 5 — (Branch) Debtor requests an edit *(optional — skip to Step 6 for the straight happy path)*

In the debtor window, open **Debts** → find the new debt → click **Request edit** → enter reason `"Please lower to 60 SAR"` and proposed amount `60.00` → submit. The debt moves to **Edit requested**.

Back in the creditor window, open the debt → click **Approve edit** → confirm. The debt returns to **Pending confirmation** with the new amount.

## Step 6 — Debtor accepts the debt

In the debtor window, open **Debts** → find the pending debt → click **Accept**. Status changes to **Active**.

## Step 7 — Debtor marks debt as paid

In the debtor window, on the same debt → click **Mark paid**. Status changes to **Payment pending confirmation**.

## Step 8 — Creditor confirms payment

In the creditor window, open **Debts** → find the debt with status **Payment pending confirmation** → click **Confirm payment**. Status changes to **Paid**. ✅

## Step 9 — Verify commitment indicator

In the debtor window, navigate to **Dashboard**. The commitment indicator should have increased (from 50 to 53 for an early payment). ✅

## Step 10 — (Optional) Arabic locale check

Toggle the UI language to Arabic (Settings or language switcher). Repeat step 8 briefly — verify all labels, toasts, and the commitment indicator render in Arabic with correct RTL alignment.

---

## Expected outcome

| Step | Status |
|------|--------|
| Debt reaches **Paid** | ✅ |
| Commitment indicator increased | ✅ |
| No raw API errors in any toast | ✅ |
| No blank / untranslated panels | ✅ |

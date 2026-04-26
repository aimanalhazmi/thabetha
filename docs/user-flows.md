# User Flows

Numbered steps for the three primary flows. Status names match [`debt-lifecycle.md`](./debt-lifecycle.md).

## Creditor flow

1. Sign up (UC1). Choose `account_type = creditor` (or `both`). Optionally fill the business sub-profile (shop name, activity, location).
2. Land on the **Creditor Dashboard** (`/dashboard`). See total receivable, overdue alerts, top-compliant customers, and the `debts` list.
3. Tap **Create debt** (`/debts/new`).
4. *(optional)* Tap **Scan QR** (`/qr/scan`) — point the camera at the customer's QR. Backend resolves the token → profile preview, prefills `debtor_id` and `debtor_name`.
5. Fill amount, currency, description, due date. Attach a receipt photo or voice note → Supabase Storage.
6. Submit → debt created in `pending_confirmation`. Both parties see the debt; debtor receives an in-app + (mocked) WhatsApp notification.
7. Wait for the debtor's response:
   - **accepted** → debt becomes `active`. Visible on dashboard's "active" pile.
   - **edit_requested** → debtor proposed new terms. Open the debt, amend, re-issue → status returns to `pending_confirmation`.
   - **rejected** → terminal. Optionally `cancel` to clear from the active list.
8. As due dates pass, the system flips `active` debts to `overdue` automatically and writes a `−5` commitment-score event for the debtor.
9. When the debtor marks the debt as paid (`payment_pending_confirmation`), open it, verify cash receipt, tap **Confirm payment** (`/debts/:id/confirm-payment`).
10. Status flips to `paid`. Debtor's commitment indicator updates: `+5` if on time, `−2` if late.

## Debtor flow

1. Sign up (UC1) or accept a deep-link from a creditor's notification. `account_type = debtor` is the default.
2. Land on the **Debtor Dashboard** (`/dashboard`). See total owed, due-soon, overdue, per-creditor list, own commitment indicator.
3. New debt arrives — notification + dashboard entry. Open **Debt Confirmation** (`/debts/:id/respond`):
   - **Accept** → status `active`. Debt is now binding.
   - **Reject** → status `rejected`. Creditor is notified.
   - **Request edit** → fill `message` + optional new amount/due date → status `edit_requested`.
4. As payment day approaches, the dashboard surfaces a "due soon" pill. WhatsApp / in-app reminders fire (per-creditor opt-out lives in **Settings**).
5. When the debt is paid in cash, open the debt, tap **Mark as paid** (with optional note) → status `payment_pending_confirmation`.
6. Wait for the creditor to confirm receipt. Status flips to `paid`; commitment indicator updates.
7. **QR Profile** (`/qr`) shows a rotating short-lived token. The debtor presents it to a creditor for fast identification at debt-creation time.

## Shared debt-lifecycle flow

```
creditor: create debt
   │
   ▼  pending_confirmation
debtor: accept / reject / request_edit / (creditor cancels)
   │
   ├─► reject → rejected ─► (creditor cancels) ─► cancelled
   │
   ├─► request_edit → edit_requested ─► (creditor amends) ─► pending_confirmation
   │
   └─► accept → active
                   │
                   ▼  (system) due_date < today
                 overdue
                   │
                   ▼  debtor: mark_paid
              payment_pending_confirmation
                   │
                   ▼  creditor: confirm_payment
                 paid    (commitment indicator updated)
```

Every transition writes a row to `debt_events` with the actor, message, and metadata. The audit trail is the same record both sides see.

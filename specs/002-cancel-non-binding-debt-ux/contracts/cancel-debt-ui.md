# UI / API Contract: Cancel Debt

**Date**: 2026-04-28
**Feature**: 002-cancel-non-binding-debt-ux

This feature exposes a UI contract (the new `CancelDebtDialog` component) and consumes one existing backend contract (`POST /debts/{id}/cancel`). No new HTTP endpoints, no new DB rows.

## 1. Backend endpoint consumed (existing — no change)

```
POST /api/v1/debts/{debt_id}/cancel
Authorization: Bearer <Supabase JWT>
Content-Type: application/json

{
  "message": "<string, length 0..200, may be empty>"
}
```

**Responses**:

| Status | Body | When |
|--------|------|------|
| `200 OK` | `DebtOut` with `status: "cancelled"` | Source state was `pending_confirmation` or `edit_requested`. |
| `403 Forbidden` | error envelope | Caller is not the debt's creditor. (Should not happen — UI hides the button — but defensive.) |
| `404 Not Found` | error envelope | Debt not visible to caller. |
| `409 Conflict` | error envelope | Source state disallows cancellation (e.g., `active`, `paid`, already `cancelled`). |

The frontend treats `403` and `404` as terminal "refresh and dismiss" errors; `409` as the recoverable "state changed" inline error described in research §R5.

## 2. UI component contract — `CancelDebtDialog`

**Location**: `frontend/src/components/CancelDebtDialog.tsx` (new file).

### Props

```ts
interface CancelDebtDialogProps {
  debt: Debt;                       // The debt being cancelled. Caller is responsible for status gating.
  language: 'ar' | 'en';            // Pulled from i18n context by the caller.
  onCancelled: (updated: Debt) => void;  // Fired after a 200 OK; receives the updated debt.
  onClose: () => void;              // Fired on dismiss (overlay click, escape key, dismiss button) AND after onCancelled.
}
```

### Behavior

- On mount: render an overlay + centered card containing:
  - Title = `tr('cancel_debt_confirm_title')`
  - Body paragraph = `tr('cancel_debt_confirm_body')`
  - Always-visible `<textarea maxLength={200}>` with placeholder `tr('cancel_message_optional')`. Initial value = `""`.
  - Two buttons: confirm (`tr('cancel_debt')`) and dismiss (existing `tr('cancel')` for the dialog dismissal — note: the *page-level* "Cancel debt" button label uses `cancel_debt`; the *dialog dismiss* uses the generic `cancel`).
- Pressing Escape, clicking the overlay, or clicking dismiss → `onClose()`.
- Pressing confirm → disable both buttons, set submitting state, call `apiRequest('/debts/{id}/cancel', { method: 'POST', body: JSON.stringify({ message: trimmed }) })`.
  - On `200`: call `onCancelled(updated)`, then `onClose()`. Success toast is fired by the *caller* (`DebtsPage.tsx`) via the existing `runAction` helper, so the toast text and surface stay consistent with other actions.
  - On `409`: leave the dialog open, render a translated inline error (`tr('cancel_debt_state_changed')`), trigger the page's `refresh()`, re-enable buttons.
  - On any other error: leave the dialog open, render the existing generic `tr('errorGeneric')` (or equivalent), re-enable buttons.

### Accessibility

- The dialog is a `role="dialog"` with `aria-modal="true"` and `aria-labelledby` pointing at the title.
- Initial focus lands on the textarea (so a creditor who *does* want to type a message starts there) — but Enter does not submit (only the explicit confirm button does), so an empty-message creditor can simply press Tab → Enter or click confirm.
- Dialog respects the active text direction (Arabic = RTL) via the existing direction-aware CSS already in use elsewhere on the page.

## 3. UI integration contract — `DebtsPage.tsx`

The existing creditor-side cancel button (currently at line ~683) is replaced with:

```tsx
{isCreditor && (debt.status === 'pending_confirmation' || debt.status === 'edit_requested') && (
  <button onClick={() => setCancelDialogDebtId(debt.id)}>
    <X size={16} /><span>{tr('cancel_debt')}</span>
  </button>
)}
```

A single `<CancelDebtDialog>` is rendered at the page level when `cancelDialogDebtId !== null`, passing the matching debt object. After successful cancel, the page refreshes its debt list and the user remains on the page (FR-011).

## 4. New i18n keys (added to `frontend/src/lib/i18n.ts`)

| Key | English | Arabic |
|-----|---------|--------|
| `cancel_debt` | "Cancel debt" | "إلغاء الدين" |
| `cancel_debt_confirm_title` | "Cancel this debt?" | "إلغاء هذا الدين؟" |
| `cancel_debt_confirm_body` | "The debtor will be notified. This cannot be undone." | "سيتم إخطار المَدين. لا يمكن التراجع عن هذا الإجراء." |
| `cancel_message_optional` | "Add an optional reason (max 200 characters)" | "أضف سببًا اختياريًا (200 حرفًا كحد أقصى)" |
| `cancelled_successfully` | "Debt cancelled" | "تم إلغاء الدين" |
| `cancel_debt_state_changed` | "This debt can no longer be cancelled — its status changed." | "لم يعد بالإمكان إلغاء هذا الدين — تغيّرت حالته." |

(Final wording may be adjusted by the implementer; the keys are the contract.)

## 5. What is NOT part of this contract

- No streaming, no websockets, no realtime subscriptions.
- No batch cancel.
- No "undo" affordance after the toast (constitution-level audit-trail rules forbid it).
- No change to debtor-side rendering of the existing `debt_cancelled` notification.

# Debt Lifecycle

Canonical state machine for a debt in **Thabetha / ثبتها**. Every status name in the database, backend Pydantic models, and frontend types must match this list exactly.

## States

| State | When | Source of truth |
|---|---|---|
| `pending_confirmation` | Creditor created the debt; debtor has not yet responded. Initial state. | Created by creditor. |
| `active` | Debtor accepted. Debt is binding. | Set by debtor accept. |
| `edit_requested` | Debtor asked the creditor to amend the debt (amount, due date, etc.) before accepting. The debtor cannot reject outright — `request_edit` is the only pushback path. | Set by debtor request-edit. |
| `overdue` | Debt is `active` (or `payment_pending_confirmation`) and `due_date < today`. Auto-computed daily. | Background sweep / read-time refresh. |
| `payment_pending_confirmation` | Debtor marked the debt as paid; awaiting creditor receipt confirmation. | Set by debtor mark-paid. |
| `paid` | Creditor confirmed receipt. Terminal success. | Set by creditor confirm-payment. |
| `cancelled` | Creditor withdrew the debt before it became binding. Terminal. | Set by creditor cancel. |

## Transitions

```
                ┌──────────────────────┐
                │ pending_confirmation │ ◄── (creditor creates)
                └──────────┬───────────┘
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   edit_requested       active            cancelled
        │                  │
        │ creditor approve │
        │   (new terms)    │
        │ creditor reject  │
        │ (original terms) │
        ▼                  ▼
   pending_confirmation  overdue
                           │
                           ▼
              payment_pending_confirmation
                           │
                           ▼
                         paid
```

## Allowed transitions

| From | To | Triggered by | Notes |
|---|---|---|---|
| _(none)_ | `pending_confirmation` | creditor (create) | All new debts start here. |
| `pending_confirmation` | `active` | debtor (accept) | Sets `confirmed_at`. |
| `pending_confirmation` | `edit_requested` | debtor (request-edit) | Debtor's only pushback path. Includes requested amount/due-date. |
| `pending_confirmation` | `cancelled` | creditor (cancel) | |
| `edit_requested` | `pending_confirmation` | creditor (approve-edit) | Debt updated with the requested amount/due-date; debtor must re-confirm. |
| `edit_requested` | `pending_confirmation` | creditor (reject-edit) | Original terms stand; debtor must accept or re-request. |
| `edit_requested` | `cancelled` | creditor (cancel) | |
| `active` | `overdue` | system (daily sweep) | When `due_date < today`. |
| `active` | `payment_pending_confirmation` | debtor (mark-paid) | |
| `overdue` | `payment_pending_confirmation` | debtor (mark-paid) | |
| `payment_pending_confirmation` | `paid` | creditor (confirm-payment) | Sets `paid_at`; updates commitment indicator. |

Any other transition must raise `409 Conflict`.

## Validation rules

- A debt becomes binding **only** after `pending_confirmation → active`.
- A debt becomes `paid` **only** after the creditor confirms receipt — never directly from `active`.
- `overdue` is computed from `due_date` and the current state; it is not a destination of explicit user action.
- `cancelled` is reachable only from non-binding states (`pending_confirmation`, `edit_requested`). An `active`/`overdue`/`payment_pending_confirmation`/`paid` debt cannot be cancelled — the creditor must instead settle or write off through accounting.
- All transitions append a row to `debt_events` for the audit trail.

## Commitment-indicator impact

The creditor configures `debts.reminder_dates` (a list of `date`s) at creation. As each reminder passes unpaid, a one-time penalty fires for that `(debt_id, reminder_date)`.

| Event | Δ commitment_score (debtor) |
|---|---|
| `paid_early` — `payment_confirmed` strictly before `due_date` | +3 |
| `paid_on_time` — `payment_confirmed` on `due_date` | +1 |
| `missed_reminder` — a configured reminder date passed unpaid | −2 × 2^N where N = count of prior missed reminders for this debt (so −2, −4, −8, …) |
| `paid_late` — `payment_confirmed` after `due_date` | −2 × 2^N where N = total missed-reminder events already applied to this debt |
| `debt_overdue` (auto, one-time per debt) | −5 |

Range is clamped to `[0, 100]`, default `50`. See [`docs/supabase.md`](./supabase.md) for the schema.

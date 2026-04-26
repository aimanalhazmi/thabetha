# Debt Lifecycle

Canonical state machine for a debt in **Thabetha / ثبتها**. Every status name in the database, backend Pydantic models, and frontend types must match this list exactly.

## States

| State | When | Source of truth |
|---|---|---|
| `pending_confirmation` | Creditor created the debt; debtor has not yet responded. Initial state. | Created by creditor. |
| `active` | Debtor accepted. Debt is binding. | Set by debtor accept. |
| `edit_requested` | Debtor asked the creditor to amend the debt (amount, due date, etc.) before accepting. | Set by debtor request-edit. |
| `rejected` | Debtor refused the debt. Terminal unless creditor cancels or re-issues. | Set by debtor reject. |
| `overdue` | Debt is `active` (or `payment_pending_confirmation`) and `due_date < today`. Auto-computed daily. | Background sweep / read-time refresh. |
| `payment_pending_confirmation` | Debtor marked the debt as paid; awaiting creditor receipt confirmation. | Set by debtor mark-paid. |
| `paid` | Creditor confirmed receipt. Terminal success. | Set by creditor confirm-payment. |
| `cancelled` | Creditor withdrew the debt before it became binding (or after rejection). Terminal. | Set by creditor cancel. |

## Transitions

```
                ┌─────────────────────┐
                │ pending_confirmation │ ◄── (creditor creates)
                └──────────┬──────────┘
        ┌──────────────────┼──────────────────┬──────────────┐
        │                  │                  │              │
        ▼                  ▼                  ▼              ▼
   edit_requested      rejected            active         cancelled
        │                  │                  │
        │                  └──► cancelled     │
        │                                     │
        └────► (creditor amends) ─────► active │
                                              ▼
                                          overdue
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
| `pending_confirmation` | `rejected` | debtor (reject) | |
| `pending_confirmation` | `edit_requested` | debtor (request-edit) | Includes amended amount/date. |
| `pending_confirmation` | `cancelled` | creditor (cancel) | |
| `edit_requested` | `active` | debtor (accept) | After creditor amends. |
| `edit_requested` | `pending_confirmation` | creditor (amend) | New terms; re-await debtor. |
| `edit_requested` | `cancelled` | creditor (cancel) | |
| `rejected` | `cancelled` | creditor (cancel) | |
| `active` | `overdue` | system (daily sweep) | When `due_date < today`. |
| `active` | `payment_pending_confirmation` | debtor (mark-paid) | |
| `overdue` | `payment_pending_confirmation` | debtor (mark-paid) | |
| `payment_pending_confirmation` | `paid` | creditor (confirm-payment) | Sets `paid_at`; updates commitment score. |

Any other transition must raise `409 Conflict`.

## Validation rules

- A debt becomes binding **only** after `pending_confirmation → active`.
- A debt becomes `paid` **only** after the creditor confirms receipt — never directly from `active`.
- `overdue` is computed from `due_date` and the current state; it is not a destination of explicit user action.
- `cancelled` is reachable only from non-binding states (`pending_confirmation`, `edit_requested`, `rejected`). An `active`/`overdue`/`payment_pending_confirmation`/`paid` debt cannot be cancelled — the creditor must instead settle or write off through accounting.
- All transitions append a row to `debt_events` for the audit trail.

## Commitment-score impact

| Event | Δ commitment_score (debtor) |
|---|---|
| `payment_confirmed` on or before `due_date` | +5 |
| `payment_confirmed` after `due_date` | −2 |
| `debt_overdue` (auto) | −5 (one-time per debt) |

Range is clamped to `[0, 100]`, default `50`. See [`docs/supabase.md`](./supabase.md) for the schema.

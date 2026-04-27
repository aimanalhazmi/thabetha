# Phase 1 Data Model — QR-scanner pass-through to Create Debt

This feature adds **no persistent entities** — no new tables, columns, enum values, or migrations. The "data model" here is the local state machine that the Create Debt screen runs in the browser to choose between the QR-prefilled and manual paths.

## Persistent entities (existing, unchanged)

For reference only — listed because they are read by this feature, not modified:

| Entity | Source | Used as |
|---|---|---|
| **QR token** | `repo.resolve_qr_token(token)` → `ProfileOut` | Read on Create Debt mount and on submit. Validity = within TTL. |
| **Profile** (the debtor's) | `ProfileOut` from QR resolve | Source of `id`, `display_name`, phone (last-4), `commitment_score`. |
| **DebtCreate** | `backend/app/schemas/domain.py:120` | Submission shape. Already has `debtor_name: str` (line 121) and `debtor_id: str | None` (line 122). |

No additions to any of the above.

## Form-local state (new — frontend only)

### `debtorSource` enum

The Create Debt screen maintains a single `debtorSource` value that drives the entire UI. Its lifecycle:

```
                ┌──────────────┐
   no qr_token  │              │   "clear debtor"
   ───────────► │   manual     │ ◄──────────────┐
                │              │                │
                └──────┬───────┘                │
                       │ user types name         │
                       ▼                         │
                   (submit OK)                   │
                                                 │
   qr_token in URL on mount                     │
   ─────────────────────────────►┌──────────────┴───┐
                                 │  qr-resolving    │
                                 └─────┬──────┬─────┘
                                       │      │
              resolve OK & not self    │      │  resolve fails (expired/unknown/network)
                                       ▼      ▼
                              ┌─────────────┐  ┌──────────────┐
                              │ qr-resolved │  │ qr-expired   │
                              └─────┬───────┘  │ qr-error     │
                                    │           └──────────────┘
                  resolve OK & self │
                                    ▼
                            ┌─────────────┐
                            │  qr-self    │
                            └─────────────┘
```

| State | How entered | UI affordances rendered |
|---|---|---|
| `manual` | No `qr_token` in URL on mount, **or** user tapped "clear / change debtor" | Editable debtor-name field, no preview header, normal submit button. |
| `qr-resolving` | `qr_token` present on mount; resolve in flight | Skeleton preview header; debt fields visible but **disabled**; submit hidden. |
| `qr-resolved` | Resolve succeeds; resolved id ≠ current user id | Preview header (name + last-4 phone + commitment indicator badge); debtor field locked + `scanned_debtor_label`; "clear / change debtor" link visible; debt fields enabled; submit visible. |
| `qr-expired` | Resolve returns 404/expired (mount or submit) | Error banner with `qr_expired_ask_refresh` + "Rescan" + "Switch to manual entry" actions; debt fields **kept** with their current values; submit hidden. |
| `qr-self` | Resolve succeeds but resolved id == current user id | Preview header replaced by `cannot_bill_self` message; submit **hidden** (not just disabled); "clear / change debtor" still visible. |
| `qr-error` | Resolve returns malformed/unknown token or network error | Same shape as `qr-expired` but with a generic error message; "Retry" + "Switch to manual entry". |

### `prefilled` payload

Held only when `debtorSource ∈ { 'qr-resolved' }`. Otherwise `null`.

```ts
type Prefilled = {
  debtor_id: string;        // sent as DebtCreate.debtor_id
  debtor_name: string;      // sent as DebtCreate.debtor_name (locked in UI)
  phone_last4: string;      // display only; never sent
  commitment_score: number; // display only; never sent
};
```

### Submission rules

- `manual`: send `DebtCreate` with `debtor_name` only (no `debtor_id`). Today's behavior — unchanged.
- `qr-resolved`: send `DebtCreate` with both `debtor_id = prefilled.debtor_id` and `debtor_name = prefilled.debtor_name`. Re-resolve the token first; if that re-resolve fails, transition to `qr-expired` and abort the submit.
- `qr-resolving` | `qr-self` | `qr-expired` | `qr-error`: submit is hidden — the user cannot reach this code path from the UI.

### Single-use enforcement (Q2 clarification)

After a successful `POST /debts` from the `qr-resolved` state, immediately `history.replaceState` (or `navigate(..., { replace: true })`) to drop `qr_token` from the URL. Refresh / back / revisit therefore lands in `manual` state.

## Validation rules

Inherited from `DebtCreate`:
- `debtor_name`: required, `min_length=1` (locked but populated when QR-resolved).
- `debtor_id`: optional; when present, MUST be the resolved profile id from the same token used at mount.

New invariants enforced in the UI (no schema impact):
- The user can never reach a submitted `DebtCreate` where `debtorSource == 'qr-resolved'` and `debtor_id` is missing — the submit button is gated on `prefilled !== null`.
- The user can never submit from `qr-self`, `qr-expired`, or `qr-error` — submit is hidden in those states.

## State transitions touched

None on the canonical 7-state debt lifecycle. A QR-originated debt enters `pending_confirmation` exactly like any other debt and follows the existing transitions thereafter.

# Contract — Frontend deep-link route for QR-prefilled Create Debt

This feature introduces no new HTTP API. The only new contract is a frontend-internal deep-link convention between the QR scanner page and the Create Debt page.

## Route

```
/debts/new?qr_token=<token>
```

| Field | Type | Source |
|---|---|---|
| `qr_token` | URL query string parameter | The same string returned by `GET /qr/current` and consumed by `GET /qr/resolve/{token}`. |

A request to `/debts/new` **without** `qr_token` is the existing manual-entry route — unchanged.

## Producer

**`frontend/src/pages/QRPage.tsx`** (creditor's scanner half).

After the camera reads a QR payload that the existing scanner logic recognizes as a Thabetha QR token, the page resolves the token via `GET /qr/resolve/{token}` and presents the confirm overlay (R1). On confirm:

```ts
navigate(`/debts/new?qr_token=${encodeURIComponent(token)}`);
```

On cancel: dismiss the overlay; the camera remains live.

If the scanner reads anything other than a Thabetha QR (e.g., a vCard, an unrelated URL), the scanner page surfaces the existing "not a Thabetha QR" error and does **not** navigate.

## Consumer

**`frontend/src/pages/DebtsPage.tsx`** (Create Debt route).

On mount:

1. Parse `qr_token` from `useSearchParams()`.
2. If absent → `debtorSource = 'manual'`. Render today's form.
3. If present → `debtorSource = 'qr-resolving'`, immediately call `GET /qr/resolve/{token}`.
4. On success and `resolved.id !== currentUser.id` → `debtorSource = 'qr-resolved'`, populate `prefilled`.
5. On success and `resolved.id === currentUser.id` → `debtorSource = 'qr-self'`.
6. On 404 / expired-token response → `debtorSource = 'qr-expired'`.
7. On any other failure → `debtorSource = 'qr-error'`.

On submit (only reachable from `manual` or `qr-resolved`):

- `manual`: post `DebtCreate` with `debtor_name` only.
- `qr-resolved`: re-call `GET /qr/resolve/{token}` first.
  - If resolve still succeeds: post `DebtCreate` with `debtor_id` + `debtor_name` from `prefilled`.
  - If resolve fails: transition to `qr-expired`, keep all other entered fields, abort submit.

On a successful `POST /debts` from `qr-resolved`:

- `navigate(`/debts/${created.id}`, { replace: true })` (or whatever the existing post-create destination is) — the new URL no longer carries `qr_token`, satisfying client-side single-use.

## Backend touchpoints (existing, unchanged)

| Method | Path | Source | Used by |
|---|---|---|---|
| `GET` | `/api/v1/qr/resolve/{token}` | `backend/app/api/qr.py:31` | Scanner (initial resolve before confirm), Create Debt (mount + submit re-resolve) |
| `POST` | `/api/v1/debts` | existing | Submit |

No new endpoints. No new request/response shapes.

## Error codes (consumer expectations)

| Backend response | Consumer state |
|---|---|
| `200 OK` with `ProfileOut` whose `id !== currentUser.id` | `qr-resolved` |
| `200 OK` with `ProfileOut` whose `id === currentUser.id` | `qr-self` |
| `404 Not Found` (token unknown / expired) | `qr-expired` |
| Any other 4xx/5xx or network failure | `qr-error` |

## Test surface

- **Backend**: `backend/tests/test_create_debt_with_debtor_id.py` exercises the full chain — mint a QR token for user B, resolve it as user A, post a debt with both `debtor_id` and `debtor_name`, and assert that user B sees the resulting debt with the correct `debtor_id` linkage. Uses `REPOSITORY_TYPE=memory` and the `client` fixture per the constitution's testing rule.
- **Frontend**: manual E2E checklist captured in `quickstart.md` and re-stated in the PR description.

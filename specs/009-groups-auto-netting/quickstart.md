# Quickstart — Group Auto-Netting

**Feature**: `009-groups-auto-netting`

End-to-end smoke walkthrough on local Supabase. Confirms the happy path (3-member circular debt → 1 transfer settles all three) and the two main failure paths (rejection voids, mixed-currency rejected at create).

## Prerequisites

- Phase 8 (`008-groups-mvp-surface`) is in your branch base.
- `supabase start` running (Auth + DB + Storage + Studio).
- Migrations applied through `012_group_settlement_proposals.sql`:

  ```bash
  supabase db reset
  ```

- Backend running with `REPOSITORY_TYPE=postgres`:

  ```bash
  cd backend && uv run uvicorn app.main:app --reload
  ```

- Frontend:

  ```bash
  cd frontend && npm run dev
  ```

## Walkthrough

### 1. Sign up three users (A, B, C) and form a group

In three browser sessions (or one + two private windows), sign up three users. Confirm each via Inbucket (`http://127.0.0.1:55324`).

As A, create a group ("Hackathon Squad") and invite B + C by email. As B and C, accept the invite from the Notifications page.

### 2. Create the circular debts (all SAR)

- A creates a debt: A is creditor, B is debtor, 100 SAR, **tagged to the group**.
  - As B, accept it. Status → `active`.
- B creates a debt: B is creditor, C is debtor, 100 SAR, **tagged to the group**.
  - As C, accept it. Status → `active`.
- C creates a debt: C is creditor, A is debtor, 100 SAR, **tagged to the group**.
  - As A, accept it. Status → `active`.

The group now has three `active` debts forming a perfect cycle. Net positions: A = 0, B = 0, C = 0 — but every member has both a payable and a receivable.

### 3. Trigger the settlement

As A, open the group detail page. The "Settle group" CTA in the `SettlementProposalPanel` is enabled. Tap it.

**Expected**: The proposal is created with **zero transfers** because every member's net is zero. The `confirmations` roster is empty, the proposal goes straight to `status='settled'` in the same transaction as creation, and all three `active` debts atomically transition to `paid`.

> If your test scenario should require an actual transfer, change one of the amounts: e.g. A→B 150 SAR, B→C 100 SAR, C→A 100 SAR. Net: A=−50, B=+50, C=0. The algorithm should produce a single transfer A→B of 50 SAR. The rest of the walkthrough assumes this asymmetric setup.

### 4. Confirm the transfers

As A (the only payer in this proposal), open the active proposal. Tap **Confirm**.

As B (the only receiver), open the same proposal in B's session. Tap **Confirm**.

C has no row in the `group_settlement_confirmations` roster — the proposal page shows the transfer list (FR-007 observer view) but no Confirm/Reject buttons.

**Expected after B's confirm**: the proposal goes `open → settled` atomically. All three debts in the snapshot are now `paid`. Each carries two `debt_events` rows (`marked_paid` then `payment_confirmed`) with `metadata.source='group_settlement'`. Each member's commitment indicator is unchanged (delta 0 — `settlement_neutral` event).

### 5. Verify success criteria

- **SC-001**: Open the proposal. `transfers` has length 1. ✅
- **SC-002**: All three debts show `paid` immediately on the dashboard, no manual confirm step needed. ✅
- **SC-006**: No member needed to message anyone outside the app. ✅

### 6. Reject path

Repeat steps 2–3 with a fresh circular setup. At step 4, instead of confirming, B taps **Reject**.

**Expected**: proposal `status → rejected`. Reload the dashboard — all three debts remain `active`. SC-003 verified. As A, the "Settle group" CTA is enabled again — start a new proposal.

### 7. Mixed-currency path

Add a fourth debt to the group denominated in `USD` (e.g. A creditor, B debtor, 10 USD). Tap **Settle group**.

**Expected**: HTTP 409, error code `MixedCurrency`, no proposal row created in DB. SC-004 verified.

### 8. Expiry path (manual)

Create a proposal as in §3 but **do not** confirm. In Studio, run:

```sql
update public.group_settlement_proposals
set expires_at = now() - interval '1 minute'
where status = 'open';
```

Reload the group detail page (this triggers the lazy sweep). The proposal flips to `status='expired'`, all debts unchanged, all members get a `settlement_expired` notification. SC-005 verified.

## Cross-checks

- `select status, count(*) from public.group_settlement_proposals group by 1` — should show your test proposals across `settled`, `rejected`, `expired`.
- `select event_type, count(*) from public.debt_events where metadata->>'source' = 'group_settlement' group by 1` — should show paired `marked_paid` and `payment_confirmed` counts.
- `select event_type, count(*) from public.commitment_score_events where event_type='settlement_neutral'` — one row per settled debt across all your test proposals.

## Test command (CI parity)

```bash
cd backend
uv run pytest tests/test_netting_algorithm.py tests/test_group_settlements.py -v
```

Both files run with `REPOSITORY_TYPE=memory` and exercise the in-memory implementation; the postgres path is exercised end-to-end by the manual walkthrough above.

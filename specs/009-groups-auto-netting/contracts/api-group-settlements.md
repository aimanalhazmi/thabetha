# Contract — Group Settlement Proposals API

**Feature**: `009-groups-auto-netting` · Base path: `/api/v1/groups/{group_id}/settlement-proposals`

All endpoints require a verified Supabase JWT (`Authorization: Bearer …`). Membership in `groups{group_id}` with `status='accepted'` is required for **all** routes — non-members get **404** (not 403, to avoid leaking group existence). Required-party gating is layered on top for confirm/reject (returns 403 with `code='NotARequiredParty'`).

The lazy expiry sweep runs at the start of every read on this surface. Notifications are dispatched synchronously in the same transaction as the action that triggers them.

## 1. Create proposal

`POST /api/v1/groups/{group_id}/settlement-proposals`

Snapshots all `active`/`overdue` group-tagged debts, runs the netting algorithm, and persists the proposal + confirmation roster.

**Request body**: empty object `{}` (server snapshots; no inputs).

**Responses**:

- `201 Created` — `SettlementProposalOut`. The proposer is included as a confirmer if and only if they appear in the transfer set.
- `409 Conflict` (`code='OpenProposalExists'`) — body contains `existing_proposal_id`.
- `409 Conflict` (`code='MixedCurrency'`) — snapshot would span multiple currencies.
- `409 Conflict` (`code='NothingToSettle'`) — snapshot empty (all members net to zero, or no `active`/`overdue` group debts).
- `404 Not Found` — caller is not an accepted group member.

**Side effects**:
- Insert `group_settlement_proposals` row (status `open`, `expires_at = now + 7d`).
- Insert one `group_settlement_confirmations` row per required party (status `pending`).
- Insert `group_events(event_type='settlement_proposed', actor_id=proposer)`.
- Dispatch `settlement_proposed` notifications to every required confirmer (FR-014).

## 2. List proposals

`GET /api/v1/groups/{group_id}/settlement-proposals?status=open|all` *(query optional, default `all`)*

**Responses**:

- `200 OK` — `list[SettlementProposalOut]`, most-recent-first. For non-required parties, `snapshot` is `null` per FR-007.
- `404 Not Found` — caller is not an accepted group member.

Lazy sweep runs first.

## 3. Get one proposal

`GET /api/v1/groups/{group_id}/settlement-proposals/{pid}`

**Responses**:

- `200 OK` — `SettlementProposalOut`. `snapshot` is included only when the caller is a required party (`(pid, caller)` row exists in `group_settlement_confirmations`); observers get `snapshot: null` per FR-007.
- `404 Not Found` — caller is not an accepted group member, or proposal does not belong to this group.

Lazy sweep runs first.

## 4. Confirm proposal

`POST /api/v1/groups/{group_id}/settlement-proposals/{pid}/confirm`

**Request body**: empty `{}`.

**Behaviour**:
- Lookup `(pid, caller)` in `group_settlement_confirmations`. If missing → 403 `NotARequiredParty`. If present with status `confirmed` → idempotent 200 (no state change). If `rejected` → 409 `AlreadyResponded`.
- Set `status='confirmed'`, `responded_at=now()`. Insert `group_events(event_type='settlement_confirmed')`.
- If this is the *last* `pending` confirmation, the handler immediately runs the atomic settle (see §6) inside the same request transaction.

**Responses**:

- `200 OK` — `SettlementProposalOut`. If the atomic settle ran, `status='settled'` (or `settlement_failed` on technical failure per FR-010).
- `403 Forbidden` (`code='NotARequiredParty'`) — caller has no row in confirmations.
- `409 Conflict` (`code='AlreadyResponded'`) — caller previously rejected.
- `409 Conflict` (`code='ProposalNotOpen'`) — proposal is not in `open` status (already settled / rejected / expired / failed).
- `404 Not Found` — non-member, or wrong group.

## 5. Reject proposal

`POST /api/v1/groups/{group_id}/settlement-proposals/{pid}/reject`

**Request body**: empty `{}`.

**Behaviour**:
- Lookup `(pid, caller)` in `group_settlement_confirmations`. If missing → 403 `NotARequiredParty`. If `confirmed`/`rejected` → 409 `AlreadyResponded`.
- Set caller's row to `rejected`, `responded_at=now()`.
- Set proposal `status='rejected'`, `resolved_at=now()`. Insert `group_events(event_type='settlement_rejected', actor_id=caller)`.
- Dispatch `settlement_rejected` notifications to all required parties.
- All snapshotted debts are left untouched (FR-009).

**Responses**:

- `200 OK` — `SettlementProposalOut` with `status='rejected'`.
- Same error codes as §4.

## 6. Atomic settle (internal — invoked by the last `confirm`)

Not directly exposed. Triggered when the final `pending` confirmation transitions to `confirmed`. Runs in the same DB transaction as that confirm:

1. For each `snapshot[i]` debt, in deterministic order (sorted by `debt_id`):
   1. `UPDATE debts SET status='payment_pending_confirmation' WHERE id=$1 AND status IN ('active','overdue')`. If 0 rows → raise `StaleSnapshot`.
   2. `INSERT INTO debt_events (event_type='marked_paid', actor_id=debtor, metadata={source:'group_settlement', proposal_id})`.
   3. `UPDATE debts SET status='paid', paid_at=now() WHERE id=$1 AND status='payment_pending_confirmation'`.
   4. `INSERT INTO debt_events (event_type='payment_confirmed', actor_id=creditor, metadata={source:'group_settlement', proposal_id})`.
   5. `INSERT INTO commitment_score_events (debt_id, event_type='settlement_neutral', delta=0, metadata={proposal_id}) ON CONFLICT (debt_id, event_type, proposal_id) DO NOTHING`.
2. `UPDATE group_settlement_proposals SET status='settled', resolved_at=now() WHERE id=$pid`.
3. Insert `group_events(event_type='settlement_settled')`.
4. Dispatch `settlement_settled` notifications to all required parties.

**On any exception**: rollback, then in a new transaction:

1. `UPDATE group_settlement_proposals SET status='settlement_failed', resolved_at=now(), failure_reason=$exc_class WHERE id=$pid`.
2. Insert `group_events(event_type='settlement_failed')`.
3. Dispatch `settlement_failed` notifications to all required parties.

## 7. Lazy expiry sweep (internal)

Invoked at the start of §2, §3, and the existing `GET /groups/{id}` and `GET /groups/{id}/debts` endpoints. Per group:

1. Mark expired: `UPDATE group_settlement_proposals SET status='expired', resolved_at=now() WHERE group_id=$1 AND status='open' AND expires_at < now() RETURNING id`. For each, insert `group_events(event_type='settlement_expired')` and dispatch `settlement_expired` notifications.
2. Send near-expiry reminder: for each proposal where `status='open' AND expires_at < now() + interval '24 hours' AND reminder_sent_at IS NULL`, dispatch `settlement_reminder` notifications to each `pending` confirmer; set `reminder_sent_at=now()`.

Both steps are idempotent.

## Error codes summary

| Code | HTTP | Meaning |
|---|---|---|
| `OpenProposalExists` | 409 | A proposal is already open for this group |
| `MixedCurrency` | 409 | Snapshot spans more than one currency |
| `NothingToSettle` | 409 | Snapshot is empty |
| `NotARequiredParty` | 403 | Caller is not in this proposal's confirmation roster |
| `AlreadyResponded` | 409 | Caller has already confirmed or rejected |
| `ProposalNotOpen` | 409 | Proposal is not in `open` status |
| `StaleSnapshot` | 409 | A debt in the snapshot is no longer in `active`/`overdue` |
| `LeaveBlockedByOpenProposal` | 409 | (Returned by `POST /groups/{id}/leave`) caller is in an open proposal's transfers |

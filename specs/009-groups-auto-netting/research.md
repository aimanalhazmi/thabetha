# Phase 0 — Research: Group Auto-Netting

**Feature**: `009-groups-auto-netting` · **Date**: 2026-04-29

Eight decisions resolved before design. Each section: **Decision** · **Rationale** · **Alternatives considered**.

---

## R1 — Netting algorithm

**Decision**: Hand-rolled greedy min-flow on net positions. Compute each member's net balance (`sum(received) − sum(owed)`), partition into payers (negative) and receivers (positive), sort each side by absolute amount descending, repeatedly match the largest payer with the largest receiver and emit a transfer of `min(|payer|, |receiver|)`. Worst case `N − 1` transfers, where `N` is the number of members with non-zero net.

**Rationale**: Optimal in *number of transfers* for the min-flow netting problem. Implementation is ≤30 lines of Python, no external dependencies, trivially testable as a pure function. Matches the canonical "Splitwise simplify debts" heuristic.

**Alternatives considered**:
- *Exact min-edge MILP* (e.g. via `pulp` / `scipy.optimize.linprog`): NP-hard in general, dependency-heavy, overkill for ≤20-member groups.
- *Cycle elimination on the original multigraph*: more LOC, harder to test, no transfer-count advantage over net-position greedy.

---

## R2 — Lifecycle path for snapshotted debts

**Decision**: Each settled debt traverses the canonical chain `active|overdue → payment_pending_confirmation → paid` inside a single transaction at full-confirmation time. Two `debt_events` rows per debt: `marked_paid` (debtor side) then `payment_confirmed` (creditor side), each carrying `metadata.source = "group_settlement"` and `metadata.proposal_id`.

**Rationale**: Constitution II forbids non-canonical transitions. The settlement is bilateral by construction (every payer and receiver confirmed), so collapsing the two canonical hops into one transaction satisfies the lifecycle without inventing new states.

**Alternatives considered**:
- *Direct `active → paid`*: forbidden by Constitution II.
- *New `settled` terminal state*: principle violation; settlement is paid by another mechanism, not a separate end-state.

---

## R3 — Commitment-indicator update on settlement

**Decision**: Add a third `commitment_score_events.event_type` value `settlement_neutral` with `delta = 0`, idempotent on `(debt_id, proposal_id)`. Each settled debt produces exactly one such event, replacing the on-time / late evaluation that would normally apply to a `payment_confirmed`.

**Rationale**: FR-011 says settlement is neutral. The +3 / +1 / −2·2^N rules from Constitution III are tied to debtor on-time payment, which is meaningless for a netted multi-party settlement. A zero-delta event preserves the audit trail (you can still see *why* the score didn't move) and the existing rules stay untouched.

**Alternatives considered**:
- *Skip the commitment event entirely*: breaks the audit invariant that every paid debt has a commitment event.
- *Apply the standard rule based on settlement date*: punishes/rewards timing the debtor did not control unilaterally — incorrect modelling.

---

## R4 — Confirmation roster (who must confirm)

**Decision**: The required-confirmer set is the union of all `payer_id` and `receiver_id` values across the proposed transfers. Members of the group with zero net position are observers only — they may view the proposal but their confirmation is not required (FR-007). The roster is materialised as `group_settlement_confirmations` rows at proposal-creation time (one row per required user, status `pending`).

**Rationale**: Mathematically only members in the transfer set are affected by the settlement. Observers seeing it is consistent with the Phase 8 group-privacy relaxation. Materialising the roster up-front (vs. computing on read) makes idempotent confirmation straightforward and lets the backend reject `confirm` from non-required users with a 403 by table lookup.

**Alternatives considered**:
- *All accepted members must confirm*: noisier, delays settlement when a zero-net member is unreachable.
- *Compute roster lazily on each confirm*: harder to reason about idempotency and partial state.

---

## R5 — Single open proposal enforcement

**Decision**: Postgres partial-unique index `one_open_proposal_per_group ON group_settlement_proposals(group_id) WHERE status = 'open'`. The `POST /settlement-proposals` handler uses `INSERT … ON CONFLICT (group_id) WHERE status='open' DO NOTHING RETURNING id` — when the insert produces no row, return 409 with `existing_proposal_id`. In `InMemoryRepository`, equivalent guard via a dict lookup before insert.

**Rationale**: Database-level enforcement defeats race conditions where two members tap "Settle group" at the same instant. Mirrors the partial-unique-live-row pattern already used in migration 011 for `group_members`.

**Alternatives considered**:
- *Application-level `SELECT … FOR UPDATE` then insert*: requires elevated isolation; the partial-unique is simpler.
- *Single-status table column*: doesn't compose with multiple non-open historical proposals.

---

## R6 — Lazy expiry sweeper

**Decision**: Reuse the existing on-read sweep pattern from the missed-reminder commitment-score updater. Every endpoint that returns a settlement proposal (`GET /groups/{id}/settlement-proposals/...`, `GET /groups/{id}` if it embeds the active proposal, `GET /groups/{id}/debts`) calls `repo.sweep_settlement_proposals(group_id)` first. The sweeper:
1. Finds proposals where `status = 'open' AND expires_at < now()` → mark `expired`, write `group_events` row, fire `settlement_expired` notification once.
2. Finds proposals where `status = 'open' AND expires_at < now() + 24h AND reminder_sent_at IS NULL` → fire `settlement_reminder` notification to each pending confirmer, set `reminder_sent_at`.

**Rationale**: No background worker required for hackathon scale, no external scheduler. Idempotency is enforced by the `reminder_sent_at` column and the `status = 'open'` predicate. Same pattern proven in `commitment_score_events`.

**Alternatives considered**:
- *Cron / pg_cron job*: adds infra surface; not needed at this scale.
- *Eager sweep on every write*: redundant; reads dominate.

---

## R7 — Mixed-currency rejection point

**Decision**: Reject at proposal *creation* time inside `repo.create_settlement_proposal`. Snapshot is taken first, currencies are checked, and a 409 is returned if `len({d.currency for d in snapshot}) > 1`. No proposal row is persisted on rejection.

**Rationale**: SC-004 requires rejection before any confirmation flow begins. Checking at creation gives the user immediate feedback and avoids polluting the proposal table with proposals that can never settle.

**Alternatives considered**:
- *Reject at first confirmation*: violates SC-004 and confuses the confirmer ("why am I being asked?").
- *Group debts by currency and produce one proposal per currency*: scope creep; explicitly out of scope per FR-004.

---

## R8 — Endpoint shape and routing

**Decision**: Five new endpoints, all under the existing `groups` router (no new file):

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/groups/{group_id}/settlement-proposals` | Create proposal (201) or 409 if open exists / mixed currency |
| GET | `/api/v1/groups/{group_id}/settlement-proposals` | List proposals (most recent first; sweep first) |
| GET | `/api/v1/groups/{group_id}/settlement-proposals/{pid}` | Read one proposal (sweep first) |
| POST | `/api/v1/groups/{group_id}/settlement-proposals/{pid}/confirm` | Required-party confirms (idempotent) |
| POST | `/api/v1/groups/{group_id}/settlement-proposals/{pid}/reject` | Required-party rejects (voids proposal) |

**Rationale**: Resource-style routing mirrors the existing `/groups/{id}/settlements` (manual transfer record). Confirm/reject as distinct verbs avoids overloading a single PATCH with status semantics. Membership in the group is checked once in a dependency; required-party check is per-action.

**Alternatives considered**:
- *Single `POST /confirm-or-reject` with a body status*: less greppable, harder to authorise per action.
- *Separate router file*: not enough surface area; keeps the import graph simple.

---

## Open items deferred to `/speckit-tasks`

None. All NEEDS CLARIFICATION are resolved (5 in spec clarifications, 8 here).

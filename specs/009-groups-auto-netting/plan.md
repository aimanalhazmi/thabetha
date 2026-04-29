# Implementation Plan: Group Auto-Netting (UC9 Part 2)

**Branch**: `009-groups-auto-netting` | **Date**: 2026-04-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-groups-auto-netting/spec.md`

## Summary

Add a multi-party "settle group" flow that nets all open group-tagged debts to the minimum-edge transfer set, then atomically clears them on full party confirmation. Implementation centres on a pure netting algorithm (`backend/app/services/netting.py`), two new tables (`group_settlement_proposals`, `group_settlement_confirmations`) with one-active-proposal-per-group enforcement via partial-unique index, and a single migration `012_group_settlement_proposals.sql`. Settlement is wired through the existing canonical lifecycle: each snapshotted debt transitions `active|overdue → payment_pending_confirmation → paid` inside one transaction, recording two `debt_events` rows per debt with `metadata.source = "group_settlement"` and a neutral commitment-score event (zero delta), preserving Constitution II while honouring FR-011. Lazy expiry / near-expiry-reminder fires from the same on-read sweeper that already handles missed-reminder events. Frontend adds a `SettlementProposalPanel` to `GroupDetailPage`, a `SettlementReviewModal` for the confirmation step, and ~20 new bilingual i18n keys.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend), SQL (Supabase Postgres 15).
**Primary Dependencies**: FastAPI, Pydantic v2, `@supabase/supabase-js`, React 19 + Vite + React Router. No new dependencies — netting algorithm is hand-rolled (greedy min-flow, ≤30 LOC).
**Storage**: Supabase Postgres. Two new tables (`group_settlement_proposals`, `group_settlement_confirmations`), one new enum (`settlement_proposal_status`), one partial-unique index (`one_open_proposal_per_group`), and an extension to `commitment_score_events.event_type` accepting `settlement_neutral`.
**Testing**: `pytest` with `FastAPI.TestClient` and `REPOSITORY_TYPE=memory`; pure-function unit tests for `services/netting.py`; Vitest + Testing Library for frontend smoke.
**Target Platform**: Web (mobile-first). Local: `supabase start` + `uvicorn` + `vite`. Production: FastAPI SPA fallback.
**Project Type**: Web application (`backend/` + `frontend/` + `supabase/`).
**Performance Goals**: Proposal creation P95 < 500 ms (snapshot + algorithm + persist) for groups up to the 20-member cap; confirmation atomic settle P95 < 800 ms; lazy sweep adds < 50 ms to `GET /groups/{id}` reads.
**Constraints**: Constitution II — settlement uses the existing `active|overdue → payment_pending_confirmation → paid` chain in one transaction (no new lifecycle states). Constitution III — adds a third `commitment_score_events.event_type` value (`settlement_neutral`, delta 0); existing rules untouched. Constitution IV — RLS enforced on both new tables (group members only). 20-member cap inherited from Phase 8 caps proposal complexity. Bilingual on first release.
**Scale/Scope**: 5 new endpoints, 1 migration, ~20 new i18n keys, 2 new frontend components, 1 new pure service module, 7 new `NotificationType` values, 1 new `commitment_score_events.event_type` value.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Note |
|---|---|---|
| I. Bilateral confirmation | ✅ pass | Each settled debt still requires the creditor's confirmation — collected via `POST /settlement-proposals/{pid}/confirm` rather than the per-debt endpoint, but bilaterally binding. The debtor's confirmation discharges their `mark_paid`; the creditor's confirmation discharges their `confirm_payment`. No silent state change. |
| II. Canonical 7-state lifecycle | ✅ pass | Settlement reuses the canonical chain `active|overdue → payment_pending_confirmation → paid` for each debt, executed inside one transaction. Each debt produces two `debt_events` rows (`marked_paid` then `payment_confirmed`) with `metadata.source = "group_settlement"` and `metadata.proposal_id`. No new debt status, no forbidden transition. |
| III. Commitment indicator wording | ✅ pass | Adds one new `commitment_score_events.event_type` value `settlement_neutral` with delta `0`, idempotent on `(debt_id, proposal_id)`. The five existing rules (+3 / +1 / −2·2^N / −5 overdue) are untouched. Score remains clamped 0–100. |
| IV. Per-user data isolation | ✅ pass | RLS on `group_settlement_proposals` and `group_settlement_confirmations` mirrors the Phase 8 pattern: only accepted group members of the parent `groups` row can `select`; only the proposer (insert) and required parties (update on their own confirmation row) can write. Handler code mirrors via `repo.get_authorized_proposal(user_id, ...)`. |
| V. Arabic-first | ✅ pass | All ~20 new strings (proposal status labels, confirm/reject CTAs, notification copies, mixed-currency error, expired banner, settlement-failed banner) land in `frontend/src/lib/i18n.ts` for both `ar` and `en` on first release. |
| VI. Supabase-first stack | ✅ pass | Single migration `012_group_settlement_proposals.sql`; reuses existing Supabase Auth, RLS, `notifications` table (plain-text `type` column — no enum mutation needed). No new buckets. |
| VII. Schemas single source of truth | ✅ pass | `backend/app/schemas/domain.py` adds: `SettlementProposalStatus` enum, `SettlementProposalCreate`, `SettlementProposalOut`, `ProposedTransferOut`, `SettlementConfirmationIn`, `SettlementConfirmationOut`, plus 7 new `NotificationType` values (`settlement_proposed`, `settlement_reminder`, `settlement_confirmed`, `settlement_rejected`, `settlement_settled`, `settlement_failed`, `settlement_expired`). `frontend/src/lib/types.ts` mirrors in lockstep. The pre-existing `SettlementCreate`/`SettlementOut` (manual transfer record) is unchanged. |
| VIII. Audit trail | ✅ pass | Two `debt_events` rows per settled debt (`marked_paid`, `payment_confirmed`) carry `metadata.source = "group_settlement"` and `metadata.proposal_id`. The proposal lifecycle itself logs to `group_events` (`settlement_proposed`, `settlement_confirmed`, `settlement_rejected`, `settlement_expired`, `settlement_settled`, `settlement_failed`) reusing the Phase 8 audit table — no new audit table required. |
| IX. QR identity | ✅ N/A | Not touched. |
| X. AI paid-tier gating | ✅ N/A | Not touched. |

No violations. Complexity Tracking section is empty.

## Project Structure

### Documentation (this feature)

```text
specs/009-groups-auto-netting/
├── plan.md              # This file
├── spec.md              # Authored
├── research.md          # Phase 0 — 8 decisions resolved (R1..R8)
├── data-model.md        # Phase 1 — migration 012 shape, schema deltas, lifecycle
├── quickstart.md        # Phase 1 — local dev / smoke walk-through
├── contracts/
│   └── api-group-settlements.md   # Phase 1 — HTTP surface (5 new endpoints)
├── checklists/
│   └── requirements.md            # Pre-existing
└── tasks.md             # Phase 2 — produced by /speckit.tasks (NOT this command)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   └── groups.py                       # +5 endpoints (proposal create/get/list/confirm/reject); existing /settlements untouched
│   ├── repositories/
│   │   ├── base.py                         # New ABC methods: create_settlement_proposal, get_settlement_proposal, list_settlement_proposals, confirm_settlement_proposal, reject_settlement_proposal, sweep_settlement_proposals
│   │   ├── memory.py                       # In-memory parity: snapshot, netting algorithm wired, atomic settle, lazy expiry
│   │   └── postgres.py                     # SELECT … FOR UPDATE on the open-proposal row; full settle inside one transaction; partial-unique index governs collision
│   ├── schemas/
│   │   └── domain.py                       # SettlementProposalStatus enum; SettlementProposalCreate/Out, ProposedTransferOut, SettlementConfirmationIn/Out; 7 new NotificationType values
│   └── services/
│       └── netting.py                      # NEW — pure greedy min-flow algorithm (debtor → creditor → minimum-edge transfers)
└── tests/
    ├── test_netting_algorithm.py           # NEW — unit tests for services/netting.py (3-cycle, 4-chain, mixed currency raises, net-zero group, observers detected)
    └── test_group_settlements.py           # NEW — integration: happy path, rejection voids, expiry voids, observer 403 on confirm, mixed currency 409 at create, double-open 409, leave-blocked-during-open

frontend/
└── src/
    ├── pages/
    │   └── GroupDetailPage.tsx             # Mounts <SettlementProposalPanel /> in a new "Settle" section
    ├── components/
    │   ├── SettlementProposalPanel.tsx     # NEW — shows current open proposal or "Settle group" CTA
    │   └── SettlementReviewModal.tsx       # NEW — full-detail review: my role (payer/receiver/observer), confirm/reject buttons, expiry countdown
    └── lib/
        ├── api.ts                          # Typed wrappers for all 5 new endpoints
        ├── i18n.ts                         # ~20 new keys
        └── types.ts                        # Mirror domain.py — SettlementProposalStatus, proposal/transfer/confirmation shapes, new NotificationType values

supabase/
└── migrations/
    └── 012_group_settlement_proposals.sql  # CREATE TYPE settlement_proposal_status; CREATE TABLE group_settlement_proposals; CREATE TABLE group_settlement_confirmations; partial-unique index one_open_proposal_per_group; RLS policies; allow commitment_score_events.event_type 'settlement_neutral'
```

**Structure Decision**: Existing Option 2 (web app) layout. Anchor points are the existing `backend/app/api/groups.py` (extend, do not split) and `frontend/src/pages/GroupDetailPage.tsx` (mount the panel). The single migration `012_group_settlement_proposals.sql` is the only schema-touching artefact. Pure algorithm sits in a new `services/netting.py` to keep the repository implementations thin.

## Complexity Tracking

> No Constitution violations. Section intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

# Implementation Plan: Surface Groups in MVP Navigation (UC9 Part 1)

**Branch**: `008-groups-mvp-surface` | **Date**: 2026-04-29 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-groups-mvp-surface/spec.md`

## Summary

Surface the existing `groups` backend in the MVP and complete the lifecycle gaps. Add the Groups entry to main navigation behind a new `profile.groups_enabled` flag (default `true`, toggleable in Settings). Extend the existing endpoints with the missing lifecycle: decline / leave / rename / transfer-ownership / delete-empty / revoke-invite / member-list-with-pending. Make the `groups.invite` endpoint accept email or phone (resolved server-side against existing profiles only — no SMS / email signup invites in this phase). Surface a group selector on the create-debt and edit-non-binding-debt forms when both parties share an accepted group; lock the `group_id` tag once the debt becomes binding. Auto-netting stays out of scope (deferred to Phase 9). The technical approach is a single migration `011_groups_mvp.sql` that adds the `groups_enabled` column, widens `group_members.status` to `{pending, accepted, declined, left}` with a partial-unique live-row index, adds a `group_events` audit table mirroring `debt_events`, refreshes RLS so accepted members read group-tagged debts and `groups.updated_at` is maintained — paired with parallel additions in `Repository` (in-memory + Postgres), `schemas/domain.py`, `frontend/src/lib/types.ts`, and a rebuilt `GroupsPage` plus a new `GroupDetailPage`.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend), SQL (Supabase Postgres 15).
**Primary Dependencies**: FastAPI, Pydantic v2, `@supabase/supabase-js`, React 19 + Vite + React Router. No new dependencies.
**Storage**: Supabase Postgres. New audit table `group_events` and one new column on `profiles` (`groups_enabled`); enum widening for `group_members.status`; new partial-unique live-row index; `groups.updated_at` column.
**Testing**: `pytest` with `FastAPI.TestClient` and `REPOSITORY_TYPE=memory`; existing Vitest + Testing Library smoke tests on the frontend (no new framework).
**Target Platform**: Web (mobile-first). Local: `supabase start` + `uvicorn` + `vite`. Production: FastAPI SPA fallback.
**Project Type**: Web application (`backend/` + `frontend/` + `supabase/`).
**Performance Goals**: SC-001 < 5 s nav load; SC-002 < 2 min create-invite-accept; SC-003 < 3 s invite resolution; SC-004 < 5 s debt-to-group propagation; SC-007 < 2 s flag toggle.
**Constraints**: Bilingual (AR + EN) on first release (FR-026, SC-008). Constitution IV — RLS is the authoritative authorisation contract. Constitution II — debt lifecycle string identifiers untouched. 20-member cap (FR-016) enforced at acceptance under `SELECT … FOR UPDATE` on the parent `groups` row.
**Scale/Scope**: Hackathon scope. ~9 endpoints (4 new, 1 modified `PATCH /debts/{id}`, 4 existing kept), 1 migration, ~30 new i18n keys, 2 frontend pages (rebuilt `GroupsPage`, new `GroupDetailPage`), 1 Settings toggle, 1 reusable `GroupSelector` component on create-debt and edit-non-binding-debt.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Note |
|---|---|---|
| I. Bilateral confirmation | ✅ pass | Group tag is metadata; debt state machine untouched. Tag locks at debtor acceptance (FR-022c); creditor cannot retroactively change visibility audience. |
| II. Canonical 7-state lifecycle | ✅ pass | No new debt states. `group_id` mutation is a non-state attribute edit allowed only in `pending_confirmation` / `edit_requested`, returning `409 GroupTagLocked` otherwise — same shape as other edit-window violations. |
| III. Commitment indicator wording | ✅ pass | Group surface reuses existing `commitment_score` labels. No new "score" / "rating" terms (FR-027). |
| IV. Per-user data isolation | ✅ pass | Migration 011 refreshes RLS on `groups`, `group_members`, `group_events`, and `debts` so accepted members read group-tagged debts and nothing more. Handler code mirrors RLS via `get_authorized_*`. |
| V. Arabic-first | ✅ pass | All ~30 new strings land in `frontend/src/lib/i18n.ts` for both `ar` and `en` on first release (SC-008). |
| VI. Supabase-first stack | ✅ pass | One new migration; reuses Supabase Auth and existing `notifications` table; no parallel auth or storage. |
| VII. Schemas single source of truth | ✅ pass | `GroupMemberStatus` is widened from `{pending, accepted}` to `{pending, accepted, declined, left}` in `backend/app/schemas/domain.py`; `frontend/src/lib/types.ts` mirrors. New shapes (`GroupDetailOut`, `GroupRenameIn`, `GroupOwnershipTransferIn`) and three new `NotificationType` values land in the same file, with `frontend/src/lib/types.ts` updated in lockstep (T009 + T010). |
| VIII. Audit trail | ✅ pass | New `group_events` table mirrors `debt_events` for governance ops (created / renamed / member_invited / member_joined / member_declined / member_left / invite_revoked / ownership_transferred / deleted). Debt-tag changes still flow through `debt_events` (`metadata.group_id_changed`). |
| IX. QR identity | ✅ N/A | Not touched. |
| X. AI paid-tier gating | ✅ N/A | Not touched. |

No violations. Complexity Tracking section is empty.

## Project Structure

### Documentation (this feature)

```text
specs/008-groups-mvp-surface/
├── plan.md              # This file
├── spec.md              # Authored
├── research.md          # Phase 0 — 10 decisions resolved (R1..R10)
├── data-model.md        # Phase 1 — migration 011 shape, schema deltas
├── quickstart.md        # Phase 1 — local dev / smoke walk-through
├── contracts/
│   └── api-groups.md    # Phase 1 — HTTP surface (existing + new + modified)
├── checklists/
│   └── requirements.md  # Pre-existing
└── tasks.md             # Phase 2 — produced by /speckit.tasks (NOT this command)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── groups.py           # +decline, +leave, +rename, +transfer-ownership, +delete, +revoke-invite, +group-detail, +members; invite accepts email/phone
│   │   ├── debts.py            # PATCH accepts optional group_id (null clears); enforces NotInSharedGroup / GroupTagLocked
│   │   └── profiles.py         # ProfileOut.groups_enabled exposed; ProfileUpdate accepts groups_enabled
│   ├── repositories/
│   │   ├── base.py             # New ABC methods for the 7 new lifecycle ops + shared_accepted_group(creditor, debtor)
│   │   ├── memory.py           # In-memory parity: cap-at-acceptance, partial-unique live-row, group_events
│   │   └── postgres.py         # SELECT ... FOR UPDATE on groups for cap; group_events inserts; widened enum handling
│   └── schemas/
│       └── domain.py           # Widen GroupMemberStatus to {pending,accepted,declined,left}; add GroupDetailOut, GroupRenameIn, GroupOwnershipTransferIn; extend GroupInviteIn (user_id|email|phone XOR); add NotificationType: group_invite, group_invite_accepted, group_ownership_transferred; ProfileOut/Update gain groups_enabled
└── tests/
    └── test_groups.py          # Cap-at-acceptance race, decline, leave, transfer (immediate), delete-blocked-with-debts, delete-empty cascades pending invites, retag-while-pending, retag-locked-after-active, non-member 403, pending-invitee 403, invite self/dup, recipient-not-found 404

frontend/
└── src/
    ├── pages/
    │   ├── GroupsPage.tsx        # Rebuilt: my-groups list + create + invitations panel (pending invites for me)
    │   ├── GroupDetailPage.tsx   # NEW route /groups/:id — members tab, owner-only pending invites tab, group debts tab, owner actions (rename, transfer, delete), member actions (leave, decline)
    │   ├── SettingsPage.tsx      # +groups_enabled toggle bound to /profile
    │   └── CreateDebtPage.tsx    # Mounts <GroupSelector /> when shared groups exist
    ├── components/
    │   ├── Layout.tsx            # Hide /groups nav entry when profile.groups_enabled === false
    │   └── GroupSelector.tsx     # NEW; reused on create + edit-non-binding flows
    └── lib/
        ├── api.ts                # Typed wrappers for all new and changed endpoints
        ├── i18n.ts               # ~30 new keys (group lifecycle, error codes, member-cap, ownership, retag locked)
        └── types.ts              # Mirror domain.py — widened enum + new shapes + ProfileOut.groups_enabled

supabase/
└── migrations/
    └── 011_groups_mvp.sql       # ALTER profiles ADD groups_enabled; widen group_members.status enum; partial-unique live-row index; ALTER groups ADD updated_at; CREATE TABLE group_events; refresh RLS on groups, group_members, group_events, debts (relaxed-privacy OR clause)
```

**Structure Decision**: Existing Option 2 (web app) layout. No new top-level directories. Anchor points are the existing `backend/app/api/groups.py` and `frontend/src/pages/GroupsPage.tsx`; everything else is an extension. The single migration `011_groups_mvp.sql` is the only schema-touching artefact.

## Complexity Tracking

> No Constitution violations. Section intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

# Implementation Plan: Surface Groups in MVP Navigation (UC9 Part 1)

**Branch**: `008-groups-mvp-surface` | **Date**: 2026-04-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-groups-mvp-surface/spec.md`

## Summary

Promote the existing Groups capability (already partially implemented in `backend/app/api/groups.py` and a stub `frontend/src/pages/GroupsPage.tsx`) into the MVP navigation, complete the lifecycle (leave / decline / revoke / delete / transfer / rename), and surface it in the create-debt flow as an optional group tag. Auto-netting is explicitly deferred to Phase 9. The work is dominated by frontend (full Groups surface, Settings toggle, create-debt selector) plus a small set of new backend endpoints, one schema migration (feature flag + new member statuses), and bilingual coverage.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x strict (frontend).
**Primary Dependencies**: FastAPI + Pydantic v2 (backend); React 19 + Vite + React Router + `@supabase/supabase-js` (frontend).
**Storage**: Supabase Postgres (canonical) with `InMemoryRepository` for tests.
**Testing**: `pytest` with `FastAPI.TestClient` and `REPOSITORY_TYPE=memory`; Vitest + Testing Library for frontend smoke tests where harness exists.
**Target Platform**: Mobile-first responsive web (Vite SPA), served by FastAPI in production.
**Project Type**: Web application — `backend/` (FastAPI) + `frontend/` (Vite SPA).
**Performance Goals**: Match existing pages: every transition or list render under 800 ms perceived on local Supabase (per Phase 4 polish budget).
**Constraints**: Bilateral confirmation, Arabic-first, per-user isolation, audit trail per state transition (constitution §I, IV, V, VIII). 20-member cap per group.
**Scale/Scope**: 5 user stories, 35 functional requirements, 8 success criteria. Target surfaces: 1 new top-level page (`GroupsPage` rewrite) + 1 settings panel addition + 1 create-debt-form selector. ~6 new endpoints, 1 new migration, 2 new `GroupMemberStatus` enum values, 3 new `NotificationType` values.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design (see end-of-file).*

| Principle | Application in this feature | Status |
|---|---|---|
| **I. Bilateral confirmation** | Group invites require explicit accept by the invitee; ownership transfer is unilateral by design (clarified Q1) but intentionally targets a different domain (group governance, not debt binding). Group-tagged debts continue to follow the unchanged 7-state lifecycle. | ✅ |
| **II. 7-state lifecycle** | This feature adds **no** new debt states and **no** new debt transitions. The only mutability change to debts is `group_id` while non-binding (FR-022b/c), which is metadata, not state. | ✅ |
| **III. Commitment indicator** | Untouched. Group-tagged debts still apply the same +3/+1/−2×2^N rules; no group-level score is introduced. The phrase "commitment indicator" is the only term used wherever member standing is shown (FR-027). | ✅ |
| **IV. Per-user isolation** | Visibility extended in *exactly* the way the constitution allows: an "accepted group member" gains read access to other members' group-tagged debts. Personal (untagged) debts remain strictly party-only (FR-023). RLS policies and handler-side checks both updated; non-members and pending invitees see nothing (FR-024). | ✅ |
| **V. Arabic-first** | All new strings land in `frontend/src/lib/i18n.ts` for AR + EN on first commit (FR-026). Bilingual lint guard from Phase 5 must pass. | ✅ |
| **VI. Supabase-first** | One migration in `supabase/migrations/`; no parallel auth or storage path introduced. | ✅ |
| **VII. Schemas as SoT** | New `GroupMemberStatus` enum values (`declined`, `left`), new `NotificationType` values, and new request/response shapes added in `backend/app/schemas/domain.py` first; `frontend/src/lib/types.ts` mirrored manually. | ✅ |
| **VIII. Audit trail** | Group-level events (created, renamed, ownership-transferred, member-joined/left, invite-revoked, group-deleted) recorded in a new `group_events` table mirroring `debt_events`. Required for governance traceability. | ✅ |
| **IX. QR identity** | Untouched. Group invites are user-id (or email/phone-resolved) based, not QR. | ✅ |
| **X. AI gating** | Untouched. No AI surface added. | ✅ |
| **MVP boundary** | This feature *is* the planned promotion of UC9 part 1 into MVP nav. Phase 8 of `docs/spec-kit/implementation-plan.md` explicitly authorises this scope. | ✅ |

**Gate verdict**: PASS. No violations to track in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/008-groups-mvp-surface/
├── plan.md              # This file
├── spec.md              # Already complete (with Q1–Q5 clarifications)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── api-groups.md    # REST endpoints, request/response shapes, status codes
│   └── ui-surfaces.md   # Frontend screens, props, navigation
├── checklists/
│   └── requirements.md  # Spec-quality checklist (already passing)
└── tasks.md             # Phase 2 output (not created here — see /speckit-tasks)
```

### Source code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   └── groups.py                 # EXTEND: add leave, decline, revoke, delete, transfer, rename, members, group detail
│   ├── repositories/
│   │   ├── base.py                   # EXTEND: ABC methods for new lifecycle ops
│   │   ├── memory.py                 # EXTEND: in-memory implementation
│   │   └── postgres.py               # EXTEND: SQL implementation
│   ├── schemas/
│   │   └── domain.py                 # EXTEND: GroupMemberStatus +declined +left, NotificationType +group_*, new I/O shapes
│   └── core/                         # (no changes expected)
├── tests/
│   └── test_groups.py                # NEW or EXTEND: positive + negative for every new transition
└── ...

frontend/
├── src/
│   ├── pages/
│   │   ├── GroupsPage.tsx            # REWRITE: list, detail, invite, accept/decline, leave, rename, delete, transfer
│   │   ├── DebtsPage.tsx             # EXTEND: group selector on create + non-binding edit
│   │   └── SettingsPage.tsx          # EXTEND: groups feature toggle
│   ├── components/
│   │   ├── Layout.tsx                # EXTEND: Groups nav entry gated on groups_enabled
│   │   └── GroupSelector.tsx         # NEW: shared component for create/edit-debt
│   ├── lib/
│   │   ├── api.ts                    # EXTEND: groups endpoints
│   │   ├── types.ts                  # EXTEND: mirror new schemas
│   │   └── i18n.ts                   # EXTEND: AR + EN strings (~25 new keys)
│   └── contexts/
│       └── AuthContext.tsx           # EXTEND: surface profile.groups_enabled to consumers
└── ...

supabase/
└── migrations/
    └── 011_groups_mvp.sql            # NEW: feature flag + member status enum + group_events + RLS updates
```

**Structure decision**: This is the existing **Option 2 (web application)** layout already used throughout the repository. The feature is a horizontal slice across `backend/app/api/groups.py`, `frontend/src/pages/GroupsPage.tsx`, and one migration; no new top-level package or directory is created.

## Phase 0 — Outline & Research

See [`research.md`](./research.md). Summary of decisions:

1. **Member-status enum extension** chosen over a parallel "soft-deleted" boolean: keeps a single source of truth for membership state and aligns with the existing `GroupMemberStatus` enum already exposed to the frontend.
2. **Invite resolution**: extend `GroupInviteIn` to accept either `user_id`, `email`, or `phone`. Backend resolves to a `user_id` server-side; if no profile exists, return 404 with a translated reason code (FR-012).
3. **Reuse existing `notifications` table** for `group_invite`, `group_invite_accepted`, and `group_ownership_transferred`. No new channel or table.
4. **`group_events` table** modelled on `debt_events` for audit trail per constitution §VIII; required because group lifecycle ops happen outside the per-debt audit table.
5. **Member cap**: enforced at *acceptance* time (per spec — pending invites do not pre-consume slots). Atomic `SELECT ... FOR UPDATE` on the group row prevents two simultaneous accepts from racing past the cap.
6. **Group-tag mutability** uses the existing `debts.group_id` column (already `nullable`); the existing `PATCH /debts/{id}` flow on non-binding debts is the natural host for the tag-edit gate (FR-022b/c). No separate endpoint.
7. **Feature flag**: a single `profiles.groups_enabled boolean default true`, surfaced through `/profiles/me` and updatable via the existing `ProfileUpdate` flow. The default-on choice is documented in spec assumptions.

## Phase 1 — Design & Contracts

### Data model

See [`data-model.md`](./data-model.md). Key shapes:

- `groups` (existing) — gains `updated_at` for rename audit; everything else as today.
- `group_members` (existing) — `status` widened to `pending | accepted | declined | left`.
- `group_invitations` — *not* introduced as a separate table; pending membership rows already serve the role.
- `group_events` (new) — `(id, group_id, actor_id, event_type, message, metadata jsonb, created_at)` with `event_type ∈ {created, renamed, member_invited, member_joined, member_declined, member_left, invite_revoked, ownership_transferred, deleted}`.
- `profiles.groups_enabled` (new) — `boolean not null default true`.
- `notifications.notification_type` — three new variants.

### API contracts

See [`contracts/api-groups.md`](./contracts/api-groups.md). Net-new endpoints:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/groups/{id}` | Group detail (members, owner, name) — accepted members only. |
| `GET` | `/api/v1/groups/{id}/members` | Accepted-member list; owner additionally sees pending invites. |
| `POST` | `/api/v1/groups/{id}/decline` | Invitee declines a pending invite. |
| `POST` | `/api/v1/groups/{id}/leave` | Non-owner accepted member leaves. |
| `POST` | `/api/v1/groups/{id}/transfer-ownership` | Owner transfers to another accepted member (immediate; FR-009a). |
| `POST` | `/api/v1/groups/{id}/rename` | Owner renames; body `{name}`. |
| `DELETE` | `/api/v1/groups/{id}` | Owner deletes; only if zero attached debts (FR-007/FR-008). |
| `DELETE` | `/api/v1/groups/{id}/invites/{user_id}` | Owner revokes a pending invite. |

Modified endpoints:

- `POST /api/v1/groups/{id}/invite` — request shape extended: `{ user_id?, email?, phone? }`. Exactly one identifier required.
- `POST /api/v1/groups/{id}/accept` — now atomically enforces the 20-member cap.
- `PATCH /api/v1/debts/{id}` — accepts `group_id` mutation while debt is `pending_confirmation` or `edit_requested` (FR-022b); rejected with 409 once `active`+ (FR-022c).

### UI contracts

See [`contracts/ui-surfaces.md`](./contracts/ui-surfaces.md). Surfaces touched:

- **Layout (nav)**: `Groups` entry, gated on `profile.groups_enabled`, between `QR` and `Notifications`.
- **GroupsPage** (rewrite): list view → detail view (members tab + debts tab) → modals for invite/rename/transfer/leave/delete.
- **DebtsPage create form**: optional `GroupSelector` (hidden when no shared group exists). Same selector reused on the non-binding-debt edit flow.
- **SettingsPage**: new "Groups" section with the feature toggle.

### Quickstart

See [`quickstart.md`](./quickstart.md): a 10-minute walk-through that exercises every story (P1–P5) on local Supabase, ending in a verifiable state on every screen.

### Agent context update

Update the `<!-- SPECKIT START -->` … `<!-- SPECKIT END -->` block in `CLAUDE.md` (project root) to reference this plan file. Done in step 5 below.

## Re-evaluated Constitution Check (post-design)

After Phase 1 design, all gates still PASS:

- **§II (lifecycle)**: design touches `debts.group_id` only as metadata while the debt is non-binding; no new debt states or transitions.
- **§IV (isolation)**: every new endpoint enforces both handler-side authorisation (`get_authorized_group`) and an RLS policy update in migration `011`.
- **§VII (schemas)**: enum extensions are additive; the existing `pending | accepted` values are preserved, so no breaking change.
- **§VIII (audit)**: every new transition emits a `group_events` row; tests cover the audit row alongside the state change.

No entries to add to **Complexity Tracking**.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| *(none)* | — | — |

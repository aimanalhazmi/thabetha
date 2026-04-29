---
description: "Task list for 008-groups-mvp-surface — Surface Groups in MVP Navigation (UC9 Part 1)"
---

# Tasks: Surface Groups in MVP Navigation (UC9 Part 1)

**Input**: Design documents from `/specs/008-groups-mvp-surface/`
**Prerequisites**: `plan.md`, `spec.md` (required); `research.md`, `data-model.md`, `contracts/api-groups.md`, `quickstart.md` (loaded).

**Tests**: Backend test tasks are included because the spec carries explicit measurable outcomes (SC-005, SC-006) and edge-case requirements (member-cap race, retag lock, non-member 403) that are only credible with regression tests. Frontend tests are limited to typecheck/build smoke (no harness change).

**Organization**: Tasks are grouped by user story (US1..US5, priorities P1..P3) so each story is independently implementable and testable.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Different file, no dependency on incomplete tasks → safe to run in parallel.
- **[Story]**: Required on user-story-phase tasks (US1..US5). Setup / Foundational / Polish phases carry no story label.
- File paths are absolute under the repo (`backend/`, `frontend/`, `supabase/`).

## Path Conventions (Web app — Option 2)

- Backend: `backend/app/...`, tests in `backend/tests/`.
- Frontend: `frontend/src/...`.
- Migrations: `supabase/migrations/011_groups_mvp.sql`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Branch is already created and dependencies are already installed for the existing project. Setup is therefore a thin sanity pass — no scaffolding.

- [X] T001 Verify the working tree is on `008-groups-mvp-surface`, `uv sync` (in `backend/`) and `npm install` (in `frontend/`) are green, and `supabase status` reports the local stack is up. No file changes.
- [X] T002 [P] Add `011_groups_mvp.sql` as an empty placeholder file in `supabase/migrations/` so subsequent foundational tasks can append idempotently and `supabase db reset` does not lose ordering. Header comment only.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema + repository ABC + i18n surface + nav gate. Every user story below depends on these.

**⚠️ CRITICAL**: No user-story phase may start until this phase is complete.

### Migration 011 — schema and RLS

- [X] T003 In `supabase/migrations/011_groups_mvp.sql`, add `alter table public.profiles add column groups_enabled boolean not null default true;` and backfill is implicit via the `default` for existing rows.
- [X] T004 In `supabase/migrations/011_groups_mvp.sql`, widen the `group_member_status` enum to include `'declined'` and `'left'` (Postgres `alter type ... add value`), and replace the existing `unique (group_id, user_id)` constraint on `public.group_members` with a partial-unique index `ux_group_members_live` on `(group_id, user_id) where status in ('pending','accepted')`.
- [X] T005 In `supabase/migrations/011_groups_mvp.sql`, add `updated_at timestamptz not null default now()` to `public.groups` plus an `update_updated_at` trigger (or service-side maintenance — pick the trigger for parity with other timestamped tables).
- [X] T006 In `supabase/migrations/011_groups_mvp.sql`, create `public.group_events`: `(id uuid pk default gen_random_uuid(), group_id uuid references public.groups(id) on delete set null, actor_id uuid references public.profiles(id) on delete set null, event_type text not null, message text, metadata jsonb not null default '{}', created_at timestamptz not null default now())`, plus index `(group_id, created_at desc) where group_id is not null`. **Important**: the FK uses `on delete set null` (not cascade) so the `deleted` audit row survives group removal — Constitution VIII (audit trail). Live-group queries filter `where group_id is not null`; admin/audit queries can read orphaned rows directly.
- [X] T007 In `supabase/migrations/011_groups_mvp.sql`, refresh RLS policies per `research.md#R8` and `data-model.md`:
  - `groups`: select for owner or accepted member; update for owner.
  - `group_members`: select for accepted members of the same group + the row's own user; insert/update via service role only.
  - `group_events`: select for accepted members; insert via service role.
  - `debts`: add an additional `select` policy `EXISTS (select 1 from group_members gm where gm.group_id = debts.group_id and gm.user_id = auth.uid() and gm.status = 'accepted')` ORed with the existing party-only policy.
- [ ] T008 Run `supabase db reset` locally to apply 011 cleanly from a fresh database; confirm no migration ordering errors.

### Backend foundations

- [X] T009 In `backend/app/schemas/domain.py`, widen `GroupMemberStatus` to `{pending, accepted, declined, left}`; add `groups_enabled: bool = True` to `ProfileOut` and `groups_enabled: bool | None = None` to `ProfileUpdate`; add new types `GroupDetailOut`, `GroupRenameIn { name: str (≥1) }`, `GroupOwnershipTransferIn { new_owner_user_id: str }`; widen `GroupInviteIn` to accept exactly one of `{ user_id, email, phone }` with a Pydantic validator enforcing the XOR; add `NotificationType` values `group_invite`, `group_invite_accepted`, `group_ownership_transferred`.
- [X] T010 [P] In `frontend/src/lib/types.ts`, mirror every change made in T009 — widened enum, new shapes, `ProfileOut.groups_enabled`. Keep field names byte-identical.
- [X] T011 In `backend/app/repositories/base.py`, declare new abstract methods: `decline_group_invite`, `leave_group`, `rename_group`, `transfer_group_ownership`, `delete_group`, `revoke_group_invite`, `list_pending_group_invites`, `get_group_detail`, `shared_accepted_groups(creditor_id, debtor_id)`, `find_profile_by_email_or_phone`, `update_debt_group_tag`. Method signatures must match the contract bodies in `contracts/api-groups.md`.
- [X] T012 In `backend/app/repositories/memory.py`, implement every method declared in T011, including: cap-at-acceptance serialized through a `threading.Lock` held on the `InMemoryRepository` instance for the duration of accept (introduce `self._lock = threading.Lock()` in `__init__` if no equivalent already exists); partial-unique live-row semantics (decline/leave keep terminal rows; new pending insert is allowed because no live row exists); `group_events` recorded in a list and exposed via a test helper `get_group_events(group_id)`; `transfer_group_ownership` rejects when target is not an accepted member with `409 NotAGroupMember` (covers both "no membership row" and "pending row" cases) and rejects when target is the current owner with `400 SameOwner`; `delete_group` blocked while any `debt.group_id == id` exists with `409 GroupHasDebts`; `update_debt_group_tag` enforces `409 GroupTagLocked` when debt status is not in `{pending_confirmation, edit_requested}` and `409 NotInSharedGroup` when target group is not shared.
- [ ] T013 In `backend/app/repositories/postgres.py`, implement every method declared in T011 with parity to memory: `accept_group_invite` and concurrent paths take `select ... for update` on the parent `groups` row before the cap-count `select count(*) from group_members where group_id=$1 and status='accepted'`; all `group_events` inserts run inside the same transaction as the state mutation; `delete_group` uses a single transactional check `select 1 from debts where group_id=$1 limit 1` then `delete from groups where id=$1`; widened-enum reads/writes use the new `'declined'` and `'left'` literals.
- [X] T014 [P] In `backend/app/api/profiles.py`, ensure `GET /api/v1/profile` includes `groups_enabled` in the response and `PUT /api/v1/profile` accepts `groups_enabled` from `ProfileUpdate`. No new endpoint.

### Frontend foundations

- [X] T015 [P] In `frontend/src/lib/i18n.ts`, add ~30 new keys for both `ar` and `en` covering: nav label (already exists), group lifecycle CTAs (`groups.create`, `groups.invite`, `groups.accept`, `groups.decline`, `groups.leave`, `groups.rename`, `groups.transferOwnership`, `groups.delete`, `groups.revokeInvite`), settings toggle (`settings.groupsFeature`, `settings.groupsFeatureHint`), commitment-indicator label used inside the group surface (`commitment.indicator` — AR: "مؤشر الالتزام", EN: "Commitment indicator"; never "score"/"rating" — FR-027, Constitution III), error codes for FRONTEND lookup keyed off backend `code`: `errors.NotPlatformUser`, `errors.AlreadyMember`, `errors.InviteToSelf`, `errors.GroupFull`, `errors.OwnerCannotLeave`, `errors.NotAGroupMember`, `errors.NotGroupOwner`, `errors.GroupHasDebts`, `errors.GroupTagLocked`, `errors.NotInSharedGroup`, `errors.SameOwner`, `errors.NoPendingInvite`, `errors.IdentifierAmbiguous`. Bilingual lint guard must pass (SC-008).
- [X] T016 [P] In `frontend/src/components/Layout.tsx`, hide the `/groups` nav entry when `profile.groups_enabled === false`. The flag comes from the existing AuthContext profile fetch — no new hook needed. Reactive: toggling the flag in Settings updates the nav within one render (SC-007).
- [X] T017 [P] In `frontend/src/lib/api.ts`, add typed wrappers for every endpoint in `contracts/api-groups.md`: `groups.list`, `groups.create`, `groups.get(id)`, `groups.invite(id, body)`, `groups.accept(id)`, `groups.decline(id)`, `groups.leave(id)`, `groups.rename(id, body)`, `groups.transferOwnership(id, body)`, `groups.delete(id)`, `groups.revokeInvite(id, userId)`, `groups.listMembers(id)`, `groups.listDebts(id)`, `groups.shared(withUserId)`, `debts.update(id, body)` extended for `group_id`. All errors surface `code` for i18n lookup.

**Checkpoint**: Foundation ready — user-story phases below can run in parallel where their tasks touch disjoint files.

---

## Phase 3: User Story 1 — Create a group and invite (Priority: P1) 🎯 MVP

**Goal**: A logged-in user with `groups_enabled` can find Groups in the nav, create a named group, invite an existing platform user by email or phone, and the invitee sees the pending invitation in their own Groups area.

**Independent Test**: Two users sign up. User A creates "Family", invites User B by email, User B sees the pending invite, accepts. End-to-end visible without leaving the app — under 2 minutes from cold start (SC-002).

### Backend

- [X] T018 [US1] In `backend/app/api/groups.py`, update `POST /api/v1/groups/{id}/invite` to accept the widened `GroupInviteIn` (user_id | email | phone XOR) and return errors per contract: `400 IdentifierAmbiguous`, `400 InviteToSelf`, `403 NotGroupOwner`, `404 NotPlatformUser`, `409 AlreadyMember`. On success: insert pending row, emit `notifications.group_invite` to the invitee, append `group_events.member_invited`.
- [X] T019 [US1] [P] In `backend/app/api/groups.py`, leave `POST /api/v1/groups` and `GET /api/v1/groups` shape-compatible but ensure `GroupOut` now exposes `member_count` and `updated_at`; sort `GET /groups` accepted-before-pending then by `updated_at desc`.
- [X] T020 [US1] In `backend/app/api/groups.py`, update `POST /api/v1/groups/{id}/accept` to enforce the 20-member cap at acceptance via the repository's `select … for update` path; return `404 NoPendingInvite` or `409 GroupFull` per contract; on success emit `notifications.group_invite_accepted` to the owner and `group_events.member_joined`.
- [X] T021 [US1] In `backend/tests/test_groups.py`, add tests: invite-by-email happy path, invite-by-phone happy path, invite-self → `400`, invite-already-pending → `409`, invite-non-platform-user → `404`, accept-happy-path, accept-on-full-group → `409`, two parallel accepts that would push to 21 — only one succeeds (uses repo's lock; for memory repo, simulate with the per-repo lock). Verify a `group_invite` notification row exists for the invitee and a `group_events.member_invited` row exists for the group.

### Frontend

- [X] T022 [US1] [P] In `frontend/src/pages/GroupsPage.tsx`, rebuild as a three-section page: "My groups" list (data from `groups.list`), "Pending invitations for me" (filtered from same list where my membership status is `pending`), and a "Create group" form (modal or inline) calling `groups.create`. All strings via i18n keys from T015.
- [X] T023 [US1] [P] In `frontend/src/pages/GroupsPage.tsx` (continued), wire the per-row "Accept" / "Decline" buttons in the pending-invitations panel to `groups.accept` / `groups.decline`. On error, render the localised string from `errors.<code>`.
- [X] T024 [US1] In `frontend/src/pages/GroupDetailPage.tsx`, create a new route component reachable at `/groups/:id`. Initial scope for US1: render group name, owner badge, member list (accepted only for non-owners, accepted + pending for owner via `groups.listMembers`) — each accepted member row MUST surface their `commitment_score` next to their name, labelled with the `commitment.indicator` i18n key and never with a "score"/"rating" word (FR-027, Constitution III) — and an owner-only **Invite** form with email-or-phone input (XOR validated client-side and server-side). Member rows source `commitment_score` from `ProfileOut` (already part of `GroupMemberOut`'s embedded profile, or via a follow-up profile fetch keyed by `user_id`). Add the route in `frontend/src/App.tsx`.

**Checkpoint at end of US1**: A user can create a group and invite a real platform user end-to-end. The MVP scope per the implementation-plan ("the consumer model is friends/family") is satisfied.

---

## Phase 4: User Story 2 — Tag a debt to a shared group at creation (Priority: P2)

**Goal**: When the creditor opens the create-debt form with a debtor selected, an optional group selector lists groups in which both parties are accepted members. Selecting a group sets `debt.group_id`; leaving it unset means a personal debt.

**Independent Test**: Two users in group `G`. User A (creditor) opens create-debt with B as debtor; the selector lists `G`; selecting it produces a debt with `group_id == G.id`. Without `G` membership, the selector is hidden.

### Backend

- [X] T025 [US2] In `backend/app/api/groups.py`, add `GET /api/v1/groups/shared?with_user_id=...` returning the list of groups in which both the caller and the named user are `accepted`. Empty array when none. Backed by `repo.shared_accepted_groups`.
- [X] T026 [US2] In `backend/app/api/debts.py`, accept `group_id` on `POST /api/v1/debts` (`DebtCreate` already has it — wire validation): when present, the repository must verify both creditor and debtor are accepted members of the group; otherwise `409 NotInSharedGroup`. When the debtor is not yet a platform user (`debtor_id is null`), `group_id` MUST be rejected with `400` (a debt cannot be group-tagged without a debtor profile).
- [X] T027 [US2] [P] In `backend/tests/test_groups.py`, add tests: create-debt-with-group happy path, create-debt-with-group when parties don't share group → `409 NotInSharedGroup`, create-debt without group_id stays personal, create-debt with group_id but null debtor_id → `400`, **non-party-silence** — when a group-tagged debt is created in a group with members A (creditor), B (debtor), and C (third accepted member), exactly two `notifications` rows fire (one per party) and zero are addressed to C (FR-022a).

### Frontend

- [X] T028 [US2] In `frontend/src/components/GroupSelector.tsx`, create a new reusable component that takes `creditorId`, `debtorId`, current `value`, and an `onChange` callback. On mount and on `debtorId` change, call `groups.shared(debtorId)`; when the array is empty, render nothing; otherwise render a select with a default `(no group — private)` first option and one entry per shared group. Bilingual.
- [X] T029 [US2] [P] In `frontend/src/pages/CreateDebtPage.tsx`, mount `<GroupSelector />` immediately after the debtor field. Submit `group_id` (or omit when "no group" selected) on the `POST /debts` call.

**Checkpoint at end of US2**: Group-tagged debts can be created end-to-end. Visibility is enforced server-side via the RLS policy added in T007 — the next story exercises that surface.

---

## Phase 5: User Story 3 — View debts shared inside a group (Priority: P2)

**Goal**: Any accepted member of a group sees all debts tagged to that group on the group's detail surface, including ones they are not a party to. Non-members and pending invitees see nothing.

**Independent Test**: Group `G` has accepted members A, B, C. A debt between A and B is tagged to G. C opens the group detail page → sees the debt with parties' names and amount. A non-member D navigating to the same URL gets a `403`.

### Backend

- [X] T030 [US3] In `backend/app/api/groups.py`, ensure `GET /api/v1/groups/{id}/debts` returns every `DebtOut` where `debts.group_id = id` for accepted members; returns `403 NotAGroupMember` for everyone else (including pending invitees). Backed by `repo.group_debts` which respects status.
- [X] T031 [US3] [P] In `backend/tests/test_groups.py`, add tests: accepted-member-can-list-group-debts (sees a debt they are not a party to), pending-invitee-cannot-list → `403`, non-member-cannot-list → `403`, leaver-loses-visibility (after `leave`, a previously-visible group-only debt is no longer in their list of group debts; their personal debts unchanged).

### Frontend

- [X] T032 [US3] In `frontend/src/pages/GroupDetailPage.tsx`, add a **Debts** tab calling `groups.listDebts(id)`. Render rows showing debtor name, creditor name, amount, currency, status badge (reuse the existing debt-status pill component). On `403`, render the localised `errors.NotAGroupMember` placeholder.

**Checkpoint at end of US3**: Stories 1–3 together deliver the relaxed-privacy contract. Group debts are visible exactly where the spec says they should be.

---

## Phase 6: User Story 4 — Leave / transfer ownership / delete empty group (Priority: P3)

**Goal**: Non-owner members can leave at will; owners cannot leave but can transfer ownership (immediate, no acceptance) or delete the group when it has no debts. Pending invites silently cascade on group deletion.

**Independent Test**: Non-owner C runs **Leave group** → C is removed and loses visibility into group-only debts. Owner A on a non-empty group attempts **Delete** → blocked with `409 GroupHasDebts`. Owner A transfers ownership to B → effective immediately; B receives `group_ownership_transferred` notification. With no debts attached, B deletes the group; pending invitees see invitations vanish with no notification.

### Backend

- [X] T033 [US4] In `backend/app/api/groups.py`, add `POST /api/v1/groups/{id}/decline` per contract: invitee-only; `404 NoPendingInvite` if no pending row; updates membership row to `declined`; appends `group_events.member_declined`; no notification.
- [X] T034 [US4] In `backend/app/api/groups.py`, add `POST /api/v1/groups/{id}/leave` per contract: any accepted non-owner; `403 OwnerCannotLeave` for owner; `404 NotAGroupMember` if no accepted row; updates row to `left`; appends `group_events.member_left`.
- [X] T035 [US4] In `backend/app/api/groups.py`, add `POST /api/v1/groups/{id}/transfer-ownership` per contract: owner-only; body `GroupOwnershipTransferIn`; rejects when target is not an accepted member (`409 NotAGroupMember`) or is current owner (`400 SameOwner`); updates `groups.owner_id` and `updated_at`; emits `notifications.group_ownership_transferred` to the new owner; appends `group_events.ownership_transferred`. Effective immediately (FR-009a).
- [X] T036 [US4] In `backend/app/api/groups.py`, add `POST /api/v1/groups/{id}/rename` per contract: owner-only; body `GroupRenameIn`; validates non-empty name; updates `name` and `updated_at`; appends `group_events.renamed` with `metadata.{old_name, new_name}`. (Implements FR-006a — included here because it shares the owner-only authorisation pattern.)
- [X] T037 [US4] In `backend/app/api/groups.py`, add `DELETE /api/v1/groups/{id}` per contract: owner-only; checks `select 1 from debts where group_id=$1 limit 1` and returns `409 GroupHasDebts` with `{count: <int>}` body when non-empty; on success, in a single transaction: insert `group_events.deleted` (with `actor_id`, `metadata.{name_at_delete}` so the audit row remains useful after `group_id` becomes NULL), then `delete from groups where id=$1` — `group_members` cascades away (FK on cascade); `group_events.group_id` flips to NULL via `on delete set null` from T006, preserving the audit row; pending invites silently disappear with their member rows (FR-007a). No notification.
- [X] T038 [US4] In `backend/app/api/groups.py`, add `DELETE /api/v1/groups/{id}/invites/{user_id}` per contract: owner-only; `404 NoPendingInvite` when no pending row; hard-deletes the pending row; appends `group_events.invite_revoked`; no notification.
- [X] T039 [US4] [P] In `backend/app/api/groups.py`, add `GET /api/v1/groups/{id}` (GroupDetailOut) and `GET /api/v1/groups/{id}/members` per contract — accepted-only fields for non-owner viewers; owner additionally sees `pending_invites[]`.
- [X] T040 [US4] [P] In `backend/tests/test_groups.py`, add tests: leave-as-non-owner happy, leave-as-owner → `403 OwnerCannotLeave`, decline-happy, decline-when-no-pending → `404`, transfer-immediate-no-acceptance, transfer-to-pending-invitee → `409 NotAGroupMember`, transfer-to-user-with-no-membership-row → `409 NotAGroupMember` (same code, both branches verified), transfer-to-self → `400 SameOwner`, rename-happy, rename-to-empty → `400`, delete-with-debts → `409 GroupHasDebts` with count, delete-empty cascades pending invites without notification, revoke-invite-happy, revoke-when-no-pending → `404`, group-detail-owner-sees-pending-invites, group-detail-non-owner-does-not-see-pending-invites.

### Frontend

- [X] T041 [US4] In `frontend/src/pages/GroupDetailPage.tsx`, add owner-action buttons (**Rename**, **Transfer ownership**, **Delete**) and member-action buttons (**Leave**) gated by the caller's role within the group. Owner pending-invites section gains a per-row **Revoke** button calling `groups.revokeInvite`.
- [X] T042 [US4] [P] In `frontend/src/pages/GroupsPage.tsx`, add a **Decline** button next to **Accept** in the pending-invitations panel for the user's own pending invites (already added in T023; ensure error handling for `404 NoPendingInvite` resolves to a quiet refresh).

**Checkpoint at end of US4**: Group lifecycle is complete — users are no longer permanently stuck in test groups.

---

## Phase 7: User Story 5 — Opt in / out of the groups feature (Priority: P3)

**Goal**: A per-user toggle in Settings flips `profile.groups_enabled`. New accounts default to `true`. Toggling does not destroy memberships; it only hides the nav entry.

**Independent Test**: A user with feature on toggles it off → Groups nav entry disappears within ~2 s. Toggling back on restores the entry and all previously-joined groups still listed (zero data loss).

- [X] T043 [US5] In `frontend/src/pages/SettingsPage.tsx`, add a toggle bound to `profile.groups_enabled` calling `PUT /profile` with `{ groups_enabled: <bool> }`. Optimistic update for snappy SC-007 latency; reconcile on server response. Bilingual labels via T015 keys.
- [X] T044 [US5] [P] In `backend/tests/test_profile.py` (or the equivalent existing test file for profiles), add tests asserting (a) `repo.ensure_profile(<freshly-authenticated user>)` produces a `ProfileOut` with `groups_enabled == True` (proves FR-002 end-to-end via the same code path the API uses), (b) `GET /profile` for a brand-new account returns `groups_enabled: true`, (c) `PUT /profile` with `{ groups_enabled: false }` persists and a subsequent `GET` returns `false`, (d) toggling the flag in either direction does not delete or modify any `group_members` rows for that user (FR-004).

### Edge case — retag while non-binding (US2 + US5 hybrid)

- [X] T045 [US5] [P] In `backend/app/api/debts.py`, extend the existing edit-non-binding-debt path (`PATCH /api/v1/debts/{id}` per contract `api-groups.md#Modified existing endpoint`) to accept `group_id` (string or `null`). When debt status ∉ `{pending_confirmation, edit_requested}`, return `409 GroupTagLocked`. When `group_id` is set but parties don't share that group, `409 NotInSharedGroup`. Append a `debt_events` row with `metadata.{group_id_changed: true, from, to}`. Tests in T046.
- [X] T046 [US5] [P] In `backend/tests/test_groups.py`, add tests: retag-while-pending happy, retag-while-edit-requested happy, retag-after-active → `409 GroupTagLocked`, retag-to-clear (`null`) happy, retag-to-non-shared → `409 NotInSharedGroup`. Verify `debt_events` row contents.
- [X] T047 [US5] [P] In `frontend/src/pages/CreateDebtPage.tsx` or the corresponding edit page (whichever hosts the non-binding-debt edit), reuse `<GroupSelector />` from T028 in the edit context for `pending_confirmation` and `edit_requested` debts. Hide it for any later state.

**Checkpoint at end of US5**: Every functional requirement in the spec is covered. The only remaining work is cross-cutting polish.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Lint, bilingual sweep, docs, and the small project-status updates the implementation-plan calls for.

- [X] T048 Run `cd backend && uv run ruff check --fix .` and resolve any new findings introduced by Phases 2–7. No `noqa` suppressions for new code.
- [X] T049 [P] Run `cd frontend && npm run lint && npm run lint:suppressions-justified && npm run typecheck && npm run build`; resolve any ESLint findings (the bilingual i18n guard ships as ESLint rules — no raw user-visible strings outside `i18n.ts`), any unjustified `eslint-disable` comments, and any TS strict-mode regressions. SC-008 is provably enforced by these commands exiting zero.
- [X] T050 [P] Update `docs/spec-kit/use-cases.md` UC9 status from `⛔` to `🟡` (auto-netting still pending) and `docs/spec-kit/database-schema.md` to reflect the `profiles.groups_enabled` column, the widened `group_member_status` enum, the partial-unique live-row index, the new `groups.updated_at`, and the new `group_events` table — per `implementation-plan.md#Phase 8`.
- [ ] T051 [P] Walk through `specs/008-groups-mvp-surface/quickstart.md` end-to-end on a fresh `supabase db reset` with two browser profiles; confirm SC-001 (find Groups < 5 s), SC-002 (create-invite-accept < 2 min), SC-004 (debt-to-group propagation < 5 s), SC-005 (21st acceptance rejected), SC-006 (non-member sees zero debts), SC-007 (toggle hides nav < 2 s). SC-003 (95 % of invite resolutions < 3 s) is treated as a runtime/observability target, not a buildable test — it falls out naturally from the Supabase single-region latency profile and will be observed via existing request logs rather than asserted in a task here.
- [X] T052 Verify final `git status` is clean except for the intended diff and that `cd backend && uv run pytest` passes locally.

---

## Dependencies

```text
Phase 1 Setup (T001..T002)
   ↓
Phase 2 Foundational (T003..T017)            ← blocks everything below
   ↓
   ├─→ Phase 3 US1  (T018..T024)             ← MVP boundary
   ├─→ Phase 4 US2  (T025..T029)             [depends on US1: needs an existing group to tag]
   ├─→ Phase 5 US3  (T030..T032)             [depends on US2: tagged debts to view]
   ├─→ Phase 6 US4  (T033..T042)             [independent of US2/US3 in code; uses groups from US1]
   └─→ Phase 7 US5  (T043..T047)             [independent — touches Settings + retag-while-pending]
        ↓
   Phase 8 Polish    (T048..T052)
```

**Story-level**: US1 is the only hard prerequisite for the others. US2→US3 share data flow but their code is in disjoint files, so a developer can take both. US4 and US5 are independent of US2/US3 and can run in parallel after Foundational.

**File-level [P]**: tasks marked `[P]` touch a file no other in-progress task touches. Within Foundational, T010, T014, T015, T016, T017 are parallelizable. Within US1, T019, T022, T023 vs T024 cluster carefully (T022/T023 share `GroupsPage.tsx`).

---

## Parallel execution examples

**During Foundational** (after the migration tasks T003–T008 land):

```text
T009  (backend schemas)         ── sequential (single file)
T010  [P] frontend types        ── parallel
T014  [P] profiles API          ── parallel
T015  [P] i18n strings          ── parallel
T016  [P] Layout nav gate       ── parallel
T017  [P] frontend api wrappers ── parallel
T011  (repo ABC)                ── sequential (must precede T012/T013)
T012  (memory repo)             ── after T011
T013  (postgres repo)           ── after T011, parallel with T012
```

**During US1 implementation**:

```text
T018  (invite endpoint)         ── sequential
T019  [P] groups list/get out   ── parallel (different handler, same file — coordinate)
T020  (accept endpoint)         ── after T012/T013
T021  (tests)                   ── after T018/T020
T022  [P] GroupsPage rebuild    ── parallel (frontend)
T023  [P] GroupsPage actions    ── after T022 (same file)
T024  (GroupDetailPage skel)    ── parallel (different file)
```

**During US4 implementation**: T033, T034, T035, T036, T037, T038 all live in `backend/app/api/groups.py` so coordinate file ownership; T039 and T040 are `[P]` against the others when locked-merging by section.

---

## Implementation strategy

- **MVP cut**: Phases 1 + 2 + 3 (US1) only. After T024 the team can demo "create a group, invite by email, accept" end-to-end and call it shippable. SC-001, SC-002, SC-005 (cap) are already provable at this point.
- **Increment 2**: US2 + US3 together — they are the two halves of one user-visible payoff (tag → see). Stop after T032 and you have the relaxed-privacy contract live.
- **Increment 3**: US4 — lifecycle. This is what stops users getting permanently stuck in test groups; ship before public testing widens.
- **Increment 4**: US5 + retag — the safety valve and the non-binding edit window. T045–T047 land together because the frontend reuses the same `GroupSelector`.
- **Polish**: Phase 8 runs at the very end; it depends on the actual diff being final.

## Format validation

Every task above:

- Begins with `- [ ]`.
- Has a sequential `T###` ID.
- Carries `[P]` if and only if it is parallel-safe with all in-progress siblings.
- Carries a `[USx]` label on every Phase 3..7 task; carries no story label on Phase 1, 2, or 8 tasks.
- Names a concrete file path or filesystem operation.

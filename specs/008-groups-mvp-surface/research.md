# Phase 0 Research — Groups MVP Surface

**Feature**: 008-groups-mvp-surface
**Date**: 2026-04-28

This document resolves every open technical question implied by the spec and the implementation-plan phase. Each section follows the *Decision / Rationale / Alternatives* format.

---

## R1. How to model `declined` and `left` membership?

**Decision**: Extend the existing `GroupMemberStatus` enum from `{pending, accepted}` to `{pending, accepted, declined, left}`. Membership rows are kept in place after a decline or leave; the row is the audit record.

**Rationale**:

- The existing enum is already exposed end-to-end (Pydantic → TypeScript → DB CHECK). Reusing it keeps a single source of truth and avoids a parallel "soft-deleted" boolean.
- A row that transitions through `pending → declined` (or `accepted → left`) is queryable for owner audit views ("who has refused this group?") without resurrecting a tombstone.
- Re-invitation after `declined` or `left` is handled naturally by inserting a new `pending` row; the existing `(group_id, user_id)` uniqueness must drop in favour of `(group_id, user_id, status='pending'|'accepted')` partial uniqueness so the decline/leave row coexists with a fresh invite. This is a standard pattern.

**Alternatives considered**:

- **Hard-delete on decline/leave**: simplest but loses the audit trail. Constitution §VIII expects per-action provenance for governance-relevant transitions; a deleted row is the wrong granularity.
- **Separate `group_member_history` table**: more flexible but introduces double-bookkeeping and a sync burden. Not justified for the four states this MVP needs.

---

## R2. Invite by `email` / `phone` vs `user_id` only

**Decision**: Extend `GroupInviteIn` to accept exactly one of `{user_id, email, phone}`. Backend resolves email/phone to a `user_id` server-side via `repo.find_profile_by_email_or_phone` (already used elsewhere). If no matching profile exists, return `404 NotPlatformUser` with a translated reason code.

**Rationale**:

- Spec FR-011 explicitly mentions email or phone; the current schema accepts only `user_id`, which is unhelpful in an inviter UX (you don't know strangers' UUIDs).
- FR-012 requires a clear "recipient must sign up first" message; a typed reason code lets the frontend localise without parsing a string.
- Keeping `user_id` as a third option preserves backward compatibility for any internal flow already calling the existing endpoint shape.

**Alternatives considered**:

- **Drop `user_id` entirely**: cleaner shape but breaks any existing caller and forces tests to mint contact identifiers. Not worth the churn.
- **SMS / email "invite to install" flow**: explicitly out of scope (FR-029); deferred.

---

## R3. Where does the audit trail for group lifecycle live?

**Decision**: New `group_events` table mirroring `debt_events`: `(id uuid, group_id uuid, actor_id uuid, event_type text, message text, metadata jsonb, created_at timestamptz)`. Indexed by `group_id, created_at desc`.

**Rationale**:

- Constitution §VIII requires structured audit per state transition. Group governance ops (rename, ownership transfer, member-join, member-left, group-deleted) are state transitions in the spirit of the principle, even though they are not debt transitions.
- Mirroring `debt_events` reuses the test pattern (`assert_event(repo, type=…, actor=…)`) and the read pattern.

**Alternatives considered**:

- **Reuse `debt_events`**: violates the table's name and the existing `debt_id` foreign key constraint. Misleading for any future query.
- **No audit at all**: fails constitution §VIII gate; rejected at constitution check.

---

## R4. Member-cap enforcement under concurrency

**Decision**: Enforce the 20-member cap inside the `accept` endpoint, via `SELECT count(*) FROM group_members WHERE group_id = $1 AND status = 'accepted' FOR UPDATE` followed by the upsert. The `FOR UPDATE` lock is taken on the parent `groups` row to serialise simultaneous accepts.

**Rationale**:

- The spec is explicit: pending invites do *not* pre-consume slots. So the only place the cap is checked is at acceptance.
- Without serialisation, two invitees could both pass the count check and both insert, pushing the group to 21. Locking the parent row is the standard pattern for this race in Postgres.
- The in-memory repository serialises by virtue of the GIL + a per-repository lock already used for similar invariants.

**Alternatives considered**:

- **Database-level CHECK constraint via trigger**: harder to maintain, and the failure is harder to map to a translated user-facing error.
- **Optimistic concurrency with retry**: more code, no benefit; this code path is far below the latency budget.

---

## R5. Notifications surface

**Decision**: Reuse the existing `notifications` table. Add three `NotificationType` values: `group_invite`, `group_invite_accepted`, `group_ownership_transferred`. No WhatsApp template work in this phase.

**Rationale**:

- Spec assumption explicitly states notifications reuse the existing in-app surface.
- Phase 8 of the implementation plan does not depend on Phase 6 (WhatsApp Business). Outbound WhatsApp for group events can be layered in later by adding template rows.
- Keeping the notification *types* distinct (rather than reusing a generic `group_event`) lets the frontend render appropriate icons and CTAs.

**Alternatives considered**:

- **Single `group_event` notification type with payload-discriminator**: simpler at the schema level, fiddly at the UI layer; rejected because frontend rendering becomes a string-match-on-metadata.

---

## R6. Group-tag mutability — new endpoint or reuse?

**Decision**: Reuse the existing debt-edit flow. Mutating `group_id` on a non-binding debt is permitted via `PATCH /debts/{id}`; once the debt is `active` or beyond, attempts to change `group_id` are rejected with `409 Conflict` and a translated reason. No new endpoint.

**Rationale**:

- The existing edit-while-non-binding contract already exists for `amount`, `description`, etc. Adding `group_id` to the allowed-fields list is the smallest possible change.
- Keeps the API surface tight and avoids parallel authorisation logic.
- The eligibility rule "both parties accepted in the chosen group" is a reusable predicate (`shared_accepted_group`) that works the same on create and edit.

**Alternatives considered**:

- **`POST /debts/{id}/group` with separate verb**: more "verb-rich" but no semantic gain; the data is one column.
- **Immutable** (Q3 option A): rejected by user during clarify (they chose option B).

---

## R7. Default-on feature flag — does it need a migration?

**Decision**: Yes. New migration `011_groups_mvp.sql` adds `profiles.groups_enabled boolean not null default true`, and backfills the column for existing rows in the same migration. Surfaced via `/profiles/me` (already returning `whatsapp_enabled` and `ai_enabled`); updatable via `ProfileUpdate`.

**Rationale**:

- Default-on is the spec's choice (FR-002). Postgres applies the `default true` to existing rows during the `ALTER TABLE` only if the column is `NOT NULL`; we guarantee that.
- Frontend gates the nav entry on the live profile, not on a build-time constant, so the toggle is reactive without redeploy.

**Alternatives considered**:

- **Client-side localStorage flag**: doesn't survive device changes; can drift from server reality. Rejected.
- **Default-off rollout**: contradicts the spec's "default true" decision.

---

## R8. RLS policy updates required

**Decision**: Migration `011_groups_mvp.sql` updates RLS on:

- `groups` — read: any accepted member; write: owner only.
- `group_members` — read: any accepted member of the same group (so members can see each other); write: only via service-role for the four lifecycle ops above.
- `group_events` — read: accepted members only; insert: service-role.
- `debts` — additional `select` policy: `EXISTS (select 1 from group_members where status='accepted' and user_id = auth.uid() and group_id = debts.group_id)`. The existing party-only policy is preserved (logical OR).

**Rationale**:

- Constitution §IV requires RLS to be the authoritative authorisation contract. Any handler-side check must have a matching RLS policy.
- The new "OR member of accepted group" predicate is exactly the spec's relaxed-privacy contract for group-tagged debts.

**Alternatives considered**:

- **Defer RLS to Phase 10 (`backend-rls-enforcement`)**: no — Phase 10 is about *enforcing* RLS at runtime via JWT-scoped roles. Even today, the policies are the contract; we cannot ship inconsistent policies just because the runtime currently bypasses them.

---

## R9. Where does the group-tag dropdown live in the create-debt UX?

**Decision**: A `GroupSelector` component conditionally rendered on the create-debt form. It appears only when:

1. A debtor has been selected (from QR scan or manual input that resolves to a known platform user); AND
2. The creditor and debtor share at least one accepted group.

If both conditions are met, the selector lists all shared groups with a "no group (private)" first option, default-selected. Component is reused on the non-binding-debt edit flow.

**Rationale**:

- Mirrors the spec's FR-019/FR-020 exactly.
- Reuse on edit avoids divergent rules between create and edit.
- The "no group (private)" first option makes the privacy default visible and explicit, addressing edge case "leaving the selector unset → personal debt".

**Alternatives considered**:

- **Always show the selector with an empty list**: surfaces noise to single users; rejected.
- **Show the selector only when exactly one shared group exists**: punishes power users; rejected.

---

## R10. Do we need any frontend testing harness changes?

**Decision**: Use existing Vitest + Testing Library setup (per Phase 5). Add smoke tests for `GroupsPage` in both AR and EN locales; do not introduce a new framework.

**Rationale**:

- Phase 5 already established the bilingual snapshot pattern.
- Backend tests remain the canonical regression for state transitions; frontend tests cover render and i18n only.

**Alternatives considered**:

- **Playwright E2E**: useful but disproportionate for this phase; the integration-test pattern in `backend/tests/` already covers happy-path correctness.

---

## Summary

All 10 research items resolved. No `NEEDS CLARIFICATION` markers remain. Ready to proceed to data-model, contracts, and quickstart.

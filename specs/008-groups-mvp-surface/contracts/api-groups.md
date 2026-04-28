# API Contract — Groups Endpoints

**Feature**: 008-groups-mvp-surface
**Base path**: `/api/v1/groups`
**Auth**: All endpoints require a valid Supabase JWT (or `x-demo-*` headers in non-production). Authorisation rules below are enforced both in handler code and by RLS.

---

## Existing endpoints (kept; minor changes)

### `POST /api/v1/groups` — Create group

- **Body**: `GroupCreate` `{ name: string (≥1), description?: string }`
- **Response**: `201 GroupOut` (now includes `member_count` and `updated_at`)
- **Auth**: any authenticated user.
- **Side effects**: row in `groups`; row in `group_members` (status=`accepted`, user=creator); `group_events` `created`.

### `GET /api/v1/groups` — List my groups

- **Response**: `200 GroupOut[]`
- **Definition of "my groups"**: the caller has a row in `group_members` with `status in ('pending','accepted')` for that group.
- **Sort**: `accepted` before `pending`, then by `updated_at desc`.

### `POST /api/v1/groups/{id}/invite` — Invite a member (CHANGED shape)

- **Body**: `GroupInviteIn` `{ user_id? | email? | phone? }` — **exactly one** required.
- **Response**: `200 GroupMemberOut` (status `pending`).
- **Errors**:
  - `400 IdentifierAmbiguous` — zero or >1 of the three identifiers supplied.
  - `400 InviteToSelf` — resolved user is the caller.
  - `403 NotGroupOwner` — caller is not the owner.
  - `404 NotPlatformUser` — email/phone did not resolve.
  - `409 AlreadyMember` — invitee is already `accepted` or `pending`.
- **Side effects**: row in `group_members` (status=`pending`); notification `group_invite` to invitee; `group_events` `member_invited`.

### `POST /api/v1/groups/{id}/accept` — Accept invite

- **Body**: empty.
- **Response**: `200 GroupMemberOut` (status `accepted`).
- **Errors**:
  - `404 NoPendingInvite` — caller has no pending invite for this group.
  - `409 GroupFull` — accepting would push accepted-member count to 21.
- **Side effects**: update row to `accepted`; notification `group_invite_accepted` to owner; `group_events` `member_joined`.
- **Concurrency**: serialised by `SELECT ... FOR UPDATE` on the parent `groups` row.

### `GET /api/v1/groups/{id}/debts` — List group debts

- **Response**: `200 DebtOut[]` — every debt where `debts.group_id = id`.
- **Auth**: caller must be an accepted member; otherwise `403 NotAGroupMember`.

---

## New endpoints

### `GET /api/v1/groups/{id}` — Group detail

- **Response**: `200 GroupDetailOut`. Fields:
  - For any accepted member: `id`, `name`, `description`, `owner_id`, `member_count`, `members[]` (accepted only), `created_at`, `updated_at`.
  - For the owner additionally: `pending_invites[]`.
- **Errors**: `403 NotAGroupMember`.

### `GET /api/v1/groups/{id}/members` — Members list (alternate)

- **Response**: `200 GroupMemberOut[]` — accepted only for non-owner viewers; owner additionally sees pending rows.
- **Use**: dedicated endpoint for the members tab; same data as `/groups/{id}.members` but cheaper for clients that only need the list.

### `POST /api/v1/groups/{id}/decline` — Decline invite

- **Body**: empty.
- **Response**: `200 GroupMemberOut` (status `declined`).
- **Errors**: `404 NoPendingInvite` if the caller has no pending invite for this group.
- **Side effects**: update row to `declined`; `group_events` `member_declined`. **No notification** to the owner (per UX restraint; the owner can see decline events in the group's event feed if/when an audit surface is added).

### `POST /api/v1/groups/{id}/leave` — Leave group

- **Body**: empty.
- **Response**: `200 GroupMemberOut` (status `left`).
- **Errors**:
  - `403 OwnerCannotLeave` — caller is the owner; must transfer or delete first.
  - `404 NotAGroupMember` — caller is not an accepted member.
- **Side effects**: update row to `left`; `group_events` `member_left`. The leaver's visibility into group-only debts (where they were not a party) is revoked immediately by the next read passing through the updated RLS predicate.

### `POST /api/v1/groups/{id}/transfer-ownership` — Transfer ownership

- **Body**: `GroupOwnershipTransferIn` `{ new_owner_user_id: string }`
- **Response**: `200 GroupOut`.
- **Errors**:
  - `403 NotGroupOwner` — caller is not the current owner.
  - `409 NotAGroupMember` — target is not an accepted member.
  - `400 SameOwner` — target is the current owner.
- **Side effects**: `groups.owner_id` updated; `groups.updated_at` updated; notification `group_ownership_transferred` to the new owner; `group_events` `ownership_transferred`. Transfer is **immediate** (FR-009a) — no acceptance step.

### `POST /api/v1/groups/{id}/rename` — Rename group

- **Body**: `GroupRenameIn` `{ name: string (≥1) }`
- **Response**: `200 GroupOut`.
- **Errors**: `403 NotGroupOwner`.
- **Side effects**: `groups.name` and `updated_at`; `group_events` `renamed` with `metadata.{old_name,new_name}`.

### `DELETE /api/v1/groups/{id}` — Delete empty group

- **Body**: empty.
- **Response**: `204 No Content`.
- **Errors**:
  - `403 NotGroupOwner`.
  - `409 GroupHasDebts` — at least one row in `debts` with `group_id = id` exists. Body includes `{count: <int>}` for UX messaging.
- **Side effects**: cascade delete of `group_members`, `group_events`, and pending invitations. `group_events` `deleted` is emitted *before* the cascade in the same transaction so the audit row is captured (or recorded in a parallel `deleted_groups` audit if cascade priority makes that infeasible — implementation detail). No notification is sent to invitees (FR-007a).

### `DELETE /api/v1/groups/{id}/invites/{user_id}` — Revoke pending invite

- **Body**: empty.
- **Response**: `204 No Content`.
- **Errors**:
  - `403 NotGroupOwner`.
  - `404 NoPendingInvite` — no pending row exists for that user.
- **Side effects**: hard delete of the pending row; `group_events` `invite_revoked`. No notification to the invitee.

---

## Modified existing endpoint

### `PATCH /api/v1/debts/{id}` — Edit non-binding debt

- **Body**: `DebtUpdate` — newly accepts an optional `group_id: string | null`.
- **Authorisation**: caller must be the creditor.
- **Allowed states**: only `pending_confirmation` or `edit_requested` (unchanged).
- **New rules**:
  - When `group_id` is set, both creditor and debtor must be accepted members of that group → otherwise `409 NotInSharedGroup`.
  - When `group_id` is `null`, the tag is cleared.
  - When the debt is in any other state, `group_id` cannot be present in the body → `409 GroupTagLocked` (covers FR-022c).
- **Side effects**: `debt_events` `edited` (existing); the metadata gains `{group_id_changed: true, from: <id|null>, to: <id|null>}`.

---

## Status code summary

| Code | When |
|---|---|
| `200` | Successful read or in-place update returning the resource. |
| `201` | Group creation. |
| `204` | Delete / revoke success. |
| `400` | Bad request body shape (identifier ambiguity, self-invite). |
| `403` | Authenticated but not authorised for this resource. |
| `404` | Resource not found *or* caller has no pending invite (used to avoid leaking existence to non-members). |
| `409` | Conflict with current state (group full, has debts, owner cannot leave, group-tag locked). |

Every error body is `{ "code": "<MachineReadableSlug>", "message": "<i18n key or fallback English>" }`. The frontend uses `code` for translation lookup (`errors.<code>`); the `message` is the dev-facing fallback.

---

## Idempotency

- `accept`, `decline`, and `leave` are naturally idempotent on already-terminal states: re-calling on a `declined` or `left` row returns `404 NoPendingInvite` / `404 NotAGroupMember` respectively. The frontend treats these as "already done — refresh and continue".
- `transfer-ownership` to the same target as the current state is rejected with `400 SameOwner` to avoid silent-no-op confusion.
- `rename` to the same name is permitted (a no-op event row is still emitted; it costs nothing and helps audit clarity for cosmetic edits like trimmed whitespace).

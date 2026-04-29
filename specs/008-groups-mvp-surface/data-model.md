# Phase 1 Data Model — Groups MVP Surface

**Feature**: 008-groups-mvp-surface
**Date**: 2026-04-28

This document captures the data shapes required by the spec. It is the source of truth for the migration `011_groups_mvp.sql` and for the schema additions in `backend/app/schemas/domain.py` and `frontend/src/lib/types.ts`.

---

## 1. Existing tables we touch

### `profiles` (existing)

Add one column:

| Column | Type | Default | Nullable | Notes |
|---|---|---|---|---|
| `groups_enabled` | `boolean` | `true` | `not null` | Surfaced in `ProfileOut`. |

### `groups` (existing)

Add one column:

| Column | Type | Default | Nullable | Notes |
|---|---|---|---|---|
| `updated_at` | `timestamptz` | `now()` | `not null` | Maintained by trigger or service code on rename / ownership-transfer. |

No other columns change.

### `group_members` (existing)

Existing row shape is preserved. The `status` column constraint is widened to permit four values:

```text
status text not null
  check (status in ('pending','accepted','declined','left'))
```

Uniqueness changes from a flat `(group_id, user_id)` to a partial unique index allowing multiple terminal-state rows alongside one live row:

```sql
create unique index ux_group_members_live
  on group_members (group_id, user_id)
  where status in ('pending', 'accepted');
```

Rationale: a user who declined or left should be re-invitable.

### `notifications` (existing)

Add three new `notification_type` enum values: `group_invite`, `group_invite_accepted`, `group_ownership_transferred`. Recipient inference:

| Type | Recipient |
|---|---|
| `group_invite` | the invited user |
| `group_invite_accepted` | the group owner |
| `group_ownership_transferred` | the new owner |

Payload uses the existing `metadata jsonb` column. Required keys: `group_id`, `group_name`, and (for `group_invite_accepted`) `user_id` of the accepter.

### `debts` (existing)

No structural change. The existing `group_id uuid null` column carries the optional group tag. The handler-side rule "tag editable while non-binding, locked from `active` onwards" is enforced in code; no DB constraint needed.

---

## 2. New table: `group_events`

```sql
create table group_events (
  id uuid primary key default gen_random_uuid(),
  group_id uuid references groups(id) on delete set null,
  actor_id uuid not null references profiles(id),
  event_type text not null
    check (event_type in (
      'created', 'renamed', 'member_invited', 'member_joined',
      'member_declined', 'member_left', 'invite_revoked',
      'ownership_transferred', 'deleted'
    )),
  message text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index ix_group_events_group_created
  on group_events (group_id, created_at desc);
```

**Insertion rules** (one row per lifecycle action):

| Action | `event_type` | `actor_id` | `metadata` keys |
|---|---|---|---|
| `POST /groups` | `created` | creator | — |
| `POST /groups/{id}/rename` | `renamed` | owner | `old_name`, `new_name` |
| `POST /groups/{id}/invite` | `member_invited` | owner | `invited_user_id`, `invited_by_email_or_phone` |
| `POST /groups/{id}/accept` | `member_joined` | the invitee | — |
| `POST /groups/{id}/decline` | `member_declined` | the invitee | — |
| `POST /groups/{id}/leave` | `member_left` | the leaver | — |
| `DELETE /groups/{id}/invites/{user_id}` | `invite_revoked` | owner | `revoked_user_id` |
| `POST /groups/{id}/transfer-ownership` | `ownership_transferred` | old owner | `from_user_id`, `to_user_id` |
| `DELETE /groups/{id}` | `deleted` | owner | — |

`group_events` rows for a deleted group are **preserved** with `group_id` set to `NULL` (the FK uses `on delete set null`, not cascade). This satisfies Constitution VIII's audit-trail principle: the `deleted` event row survives the group's removal, retaining `actor_id`, `event_type`, `metadata`, and `created_at`. Queries scoped to a live group filter on `group_id is not null`; admin/audit queries can read the orphaned rows directly.

---

## 3. Pydantic schemas (`backend/app/schemas/domain.py`)

### Enum extensions

```python
class GroupMemberStatus(StrEnum):
    pending = "pending"
    accepted = "accepted"
    declined = "declined"   # NEW
    left = "left"           # NEW

class NotificationType(StrEnum):
    # ...existing values...
    group_invite = "group_invite"                                # NEW
    group_invite_accepted = "group_invite_accepted"              # NEW
    group_ownership_transferred = "group_ownership_transferred"  # NEW
```

### Updated input/output models

```python
class ProfileUpdate(BaseModel):
    # ...existing fields...
    groups_enabled: bool | None = None   # NEW

class ProfileOut(BaseModel):
    # ...existing fields...
    groups_enabled: bool = True          # NEW

class GroupOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    owner_id: str
    member_count: int                    # NEW (accepted members only, includes owner)
    created_at: datetime
    updated_at: datetime                 # NEW

class GroupDetailOut(GroupOut):          # NEW
    members: list[GroupMemberOut]        # accepted only for non-owner viewers
    pending_invites: list[GroupMemberOut] | None = None  # populated only when viewer == owner

class GroupInviteIn(BaseModel):
    user_id: str | None = None           # CHANGED: was required
    email: str | None = None             # NEW
    phone: str | None = None             # NEW

    @model_validator(mode="after")
    def exactly_one_identifier(self) -> "GroupInviteIn":
        present = sum(x is not None for x in (self.user_id, self.email, self.phone))
        if present != 1:
            raise ValueError("Provide exactly one of user_id, email, phone.")
        return self

class GroupRenameIn(BaseModel):          # NEW
    name: str = Field(min_length=1)

class GroupOwnershipTransferIn(BaseModel):  # NEW
    new_owner_user_id: str = Field(min_length=1)

class DebtUpdate(BaseModel):              # ALREADY EXISTS — extended
    # ...existing editable fields (amount, description, due_date, currency, reminder_dates)...
    group_id: str | None = None           # NEW (only honoured while debt is non-binding)
```

### Validation rules

- `GroupInviteIn`: exactly one of `user_id | email | phone` must be present (model_validator above). Self-invite (`user_id == requester.id` after resolution) → `400 InviteToSelf`.
- `GroupOwnershipTransferIn`: target must be an *accepted* member of the group; otherwise `409 NotAGroupMember`.
- `GroupRenameIn`: same min-length rule as `GroupCreate.name`.
- `DebtUpdate.group_id`: when provided, both creditor and debtor of the debt must be accepted members of that group; if not, `409 NotInSharedGroup`. Also rejected with `409 GroupTagLocked` when the debt is in any state except `pending_confirmation` or `edit_requested`.

---

## 4. TypeScript mirrors (`frontend/src/lib/types.ts`)

```ts
export type GroupMemberStatus = 'pending' | 'accepted' | 'declined' | 'left';

export type NotificationType =
  | /* existing values */
  | 'group_invite'
  | 'group_invite_accepted'
  | 'group_ownership_transferred';

export interface Profile {
  // ...existing fields...
  groups_enabled: boolean;
}

export interface Group {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface GroupDetail extends Group {
  members: GroupMember[];
  pending_invites?: GroupMember[];
}

export interface GroupMember {
  id: string;
  group_id: string;
  user_id: string;
  status: GroupMemberStatus;
  created_at: string;
  accepted_at: string | null;
}

export interface GroupInviteRequest {
  user_id?: string;
  email?: string;
  phone?: string;
}

export interface GroupRenameRequest { name: string }
export interface GroupOwnershipTransferRequest { new_owner_user_id: string }
```

---

## 5. RLS policies (in migration `011_groups_mvp.sql`)

### `groups`

```sql
-- already exists (read by member). Replaced/refined:
drop policy if exists groups_read on groups;
create policy groups_read on groups for select
  using (
    exists (
      select 1 from group_members
      where group_members.group_id = groups.id
        and group_members.user_id = auth.uid()
        and group_members.status = 'accepted'
    )
  );

create policy groups_owner_write on groups for update
  using (owner_id = auth.uid());

create policy groups_owner_delete on groups for delete
  using (owner_id = auth.uid());
```

### `group_members`

```sql
create policy gm_member_read on group_members for select
  using (
    user_id = auth.uid()
    or exists (
      select 1 from group_members gm
      where gm.group_id = group_members.group_id
        and gm.user_id = auth.uid()
        and gm.status = 'accepted'
    )
  );

-- writes only via service-role (handler enforces).
```

### `group_events`

```sql
create policy ge_member_read on group_events for select
  using (
    exists (
      select 1 from group_members
      where group_members.group_id = group_events.group_id
        and group_members.user_id = auth.uid()
        and group_members.status = 'accepted'
    )
  );
-- inserts only via service-role.
```

### `debts` (additional select-permitting policy)

```sql
create policy debts_group_member_read on debts for select
  using (
    debts.group_id is not null
    and exists (
      select 1 from group_members
      where group_members.group_id = debts.group_id
        and group_members.user_id = auth.uid()
        and group_members.status = 'accepted'
    )
  );
```

The existing party-only policies on `debts` remain untouched and combine with this one as a logical OR.

---

## 6. State transitions

### Group lifecycle

```text
                              (rename)                      (rename)
                                 ▲                              ▲
                                 │                              │
created ──► active ──(transfer)──► active ──(transfer)──► active ─… (delete, only if 0 debts) ──► deleted
                │
                ├──(member: pending → accepted)
                ├──(member: pending → declined)
                ├──(member: accepted → left)
                └──(member: pending → invite_revoked, by owner)
```

### Membership lifecycle

```text
        (invite)                          (accept)
   ── ─────────────► pending ──────────────────────► accepted ──(leave)──► left
                       │                                                      │
                       │ (decline)                                            │ (re-invite)
                       ▼                                                      ▼
                   declined ─────────(re-invite)─────────────► pending ──► …
```

`invite_revoked` is recorded as an event but the row is hard-deleted (since pending invites are not externally durable). This is the only deviation from "rows are kept as audit"; the audit happens via `group_events`.

---

## 7. Indexes added

| Index | Purpose |
|---|---|
| `ux_group_members_live` (partial unique on `(group_id, user_id) where status in ('pending','accepted')`) | Allow re-invitation after decline/leave; prevent duplicate live memberships. |
| `ix_group_events_group_created` | Cheap "show me this group's audit feed" reads. |
| `ix_debts_group_id` (already exists per migration 001) | Already indexed; reused for the new RLS predicate. |

No others. The 20-member cap is enforced via `FOR UPDATE` on the parent row; no specialised index is needed.

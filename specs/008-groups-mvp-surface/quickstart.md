# Phase 1 Quickstart — Groups MVP Surface

**Feature**: 008-groups-mvp-surface
**Date**: 2026-04-29

A walk-through that exercises every user story in the spec end-to-end on a local stack, plus the headless `pytest` command for the same flows.

---

## Prerequisites

```bash
supabase start                       # Auth + DB + Storage + Studio (Docker)
supabase db reset                    # apply migrations 001..011 + seed
cd backend && uv sync && uv run uvicorn app.main:app --reload   # :8000
cd frontend && npm install && npm run dev                       # :5173
```

Two browser profiles (or two Inbucket accounts) are required so you can act as both creditor and debtor. Mailbox: `http://127.0.0.1:55324`.

---

## Story 1 — Create a group and invite (P1)

1. Sign up as **User A** at `http://127.0.0.1:5173`. Confirm via Inbucket.
2. Open **Settings** → confirm "Groups feature" toggle is **on** by default (FR-002, US5 #3).
3. Open **Groups** in the main nav → click **Create group** → name `Family` → submit. The group appears with you as owner and the only accepted member (FR-006).
4. Sign up as **User B** in a second browser profile. Confirm.
5. Back as **User A**, open the `Family` group → **Invite member** → enter User B's email → submit. The invitation appears under "Pending invites" (owner-only view, FR-017 / FR-018).
6. As **User B**, open **Groups** → see the pending invitation in the invitations panel → accept (FR-015). User A's owner view now shows User B as an accepted member.

**Expected**: SC-002 ≤ 2 minutes from cold start.

## Story 2 — Tag a debt to a shared group at creation (P2)

1. As **User A** (creditor), open **Create debt** with User B selected as the debtor (via QR scan or manual lookup).
2. The form now shows a **Group** selector with `Family` and a default `(no group — private)` option (FR-019, FR-021).
3. Pick `Family` → submit. The debt is created with `group_id = <Family.id>` (FR-022).
4. Optional re-tag: while the debt is `pending_confirmation`, the creditor can change the group on the debt's edit screen (FR-022b). Confirming the debt as the debtor locks the field (FR-022c) — attempting a re-tag returns `409 GroupTagLocked`.

## Story 3 — View shared debts (P2)

1. Sign up a third user **User C**, accept an invitation from User A to `Family`.
2. As **User C**, open `Family` → **Debts** tab → the debt between A and B is visible with both names and the amount (FR-022, US3 acceptance #1).
3. As an unrelated user **User D** with no membership, navigating to the group's URL returns `403 NotAGroupMember` (FR-024, SC-006).

## Story 4 — Leave / transfer / delete (P3)

1. As **User C**, open `Family` → **Leave group** → confirm. C is removed and loses visibility into the A↔B group debt (FR-010).
2. As **User A** (owner), attempt **Leave** → blocked with "transfer ownership first" (FR-009).
3. As **User A**, **Transfer ownership** to User B → effective immediately, no acceptance (FR-009a). User B receives an in-app notification `group_ownership_transferred` (FR-009b).
4. As the new owner **User B**, **Delete group** → blocked with `409 GroupHasDebts` and a count (FR-008).
5. Mark the A↔B debt paid (creditor-confirmed). Now **Delete group** → succeeds; group disappears for everyone, pending invites silently cascade (FR-007a).

## Story 5 — Feature flag toggle (P3)

1. As any user, open **Settings** → toggle **Groups feature** off → the **Groups** nav entry disappears within ~2 s (SC-007).
2. Toggle back on → entry reappears, all previously-joined groups still listed (FR-004).

---

## Edge cases to verify

| Scenario | Expected |
|---|---|
| Invite to self | `400 InviteToSelf` with translated body. |
| Invite duplicate (already pending or accepted) | `409 AlreadyMember`; UI surfaces the existing state. |
| Invite recipient not on the platform | `404 NotPlatformUser`; UI shows "ask them to sign up first". |
| 21st acceptance | `409 GroupFull` with translated message (SC-005). |
| Pending invitee tries `/groups/:id/debts` | `403 NotAGroupMember`. |
| Re-tag debt to a group both parties don't share | `409 NotInSharedGroup`. |
| Disabling flag while owning groups | Memberships preserved server-side; nav hidden; re-enable restores entry losslessly (FR-004, SC-007). |
| Bilingual lint guard | Zero raw untranslated strings (SC-008). |

---

## Headless test command

```bash
cd backend
uv run pytest tests/test_groups.py -v
```

Backend tests cover every endpoint in `contracts/api-groups.md` against `InMemoryRepository`. Frontend smoke tests run via `npm run typecheck && npm run build` (no dedicated test script in this phase).

---

## Cleanup

```bash
supabase stop          # tear down Docker stack
```

State is ephemeral on a `db reset`; nothing in this phase persists outside Postgres.

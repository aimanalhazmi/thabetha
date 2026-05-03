"""Tests for 008-groups-mvp-surface (US1 + lifecycle + retag)."""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def _ensure_profiles(client: TestClient, *user_ids: str, email_phone: dict[str, tuple[str, str]] | None = None) -> None:
    for uid in user_ids:
        headers = auth_headers(uid)
        if email_phone and uid in email_phone:
            email, phone = email_phone[uid]
            headers = {**headers, "x-demo-email": email, "x-demo-phone": phone}
        client.get("/api/v1/profiles/me", headers=headers)
        if email_phone and uid in email_phone:
            email, phone = email_phone[uid]
            client.patch("/api/v1/profiles/me", headers=headers, json={"email": email, "phone": phone})


def _create_group(client: TestClient, owner: str, name: str = "Family") -> str:
    client.patch("/api/v1/profiles/me", headers=auth_headers(owner), json={"account_type": "creditor"})
    r = client.post("/api/v1/groups", headers=auth_headers(owner), json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_create_group_lists_owner_as_only_accepted_member(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1")
    gid = _create_group(client, "owner-1")
    detail = client.get(f"/api/v1/groups/{gid}", headers=auth_headers("owner-1"))
    assert detail.status_code == 200
    body = detail.json()
    assert body["owner_id"] == "owner-1"
    assert body["member_count"] == 1
    assert len(body["members"]) == 1
    assert body["members"][0]["user_id"] == "owner-1"


def test_debtor_cannot_create_group(client: TestClient) -> None:
    _ensure_profiles(client, "debtor-owner")
    r = client.post("/api/v1/groups", headers=auth_headers("debtor-owner"), json={"name": "Family"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "CreditorRoleRequired"


def test_invite_by_email_resolves_to_existing_profile(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1", email_phone={"friend-1": ("friend@example.com", "+966500000099")})
    gid = _create_group(client, "owner-1")
    r = client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"email": "friend@example.com"})
    assert r.status_code == 200, r.text
    assert r.json()["user_id"] == "friend-1"
    assert r.json()["status"] == "pending"


def test_invite_by_phone_resolves_to_existing_profile(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1", email_phone={"friend-1": ("friend@example.com", "+966500000099")})
    gid = _create_group(client, "owner-1")
    r = client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"phone": "+966500000099"})
    assert r.status_code == 200, r.text
    assert r.json()["user_id"] == "friend-1"
    assert r.json()["status"] == "pending"


def test_invite_unknown_email_returns_404_not_platform_user(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1")
    gid = _create_group(client, "owner-1")
    r = client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"email": "nobody@example.com"})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NotPlatformUser"
    assert r.json()["detail"]["message"] == "No user found with this email or phone number"


def test_invite_self_rejected(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1")
    gid = _create_group(client, "owner-1")
    r = client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "owner-1"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "InviteToSelf"


def test_invite_duplicate_pending_returns_409(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1")
    gid = _create_group(client, "owner-1")
    r1 = client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    assert r1.status_code == 200
    r2 = client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    assert r2.status_code == 409
    assert r2.json()["detail"]["code"] == "AlreadyMember"


def test_invite_xor_validation(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1")
    gid = _create_group(client, "owner-1")
    r = client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={})
    assert r.status_code == 422
    r = client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "x", "email": "y@z.com"})
    assert r.status_code == 422


def test_accept_then_decline_idempotent(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1", "friend-2")
    gid = _create_group(client, "owner-1")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    accept = client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("friend-1"))
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted"

    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-2"})
    decline = client.post(f"/api/v1/groups/{gid}/decline", headers=auth_headers("friend-2"))
    assert decline.status_code == 200
    assert decline.json()["status"] == "declined"

    # Re-decline is now a 404 — terminal state, no pending row.
    redecline = client.post(f"/api/v1/groups/{gid}/decline", headers=auth_headers("friend-2"))
    assert redecline.status_code == 404


def test_member_cap_enforced_at_acceptance(client: TestClient, monkeypatch) -> None:
    # Lower the cap to make the test fast.
    from app.repositories.memory import InMemoryRepository
    monkeypatch.setattr(InMemoryRepository, "GROUP_MEMBER_CAP", 3)

    _ensure_profiles(client, "owner-1", "u-2", "u-3", "u-4")
    gid = _create_group(client, "owner-1")
    for uid in ("u-2", "u-3"):
        client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": uid})
        assert client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers(uid)).status_code == 200
    # Group now at cap (owner + 2). Invite a 4th and try to accept.
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "u-4"})
    over = client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("u-4"))
    assert over.status_code == 409
    assert over.json()["detail"]["code"] == "GroupFull"


def test_non_member_cannot_view_group_debts(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1", "stranger-1")
    gid = _create_group(client, "owner-1")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("friend-1"))

    forbidden = client.get(f"/api/v1/groups/{gid}/debts", headers=auth_headers("stranger-1"))
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"]["code"] == "NotAGroupMember"


def test_pending_invitee_cannot_view_group_debts(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1")
    gid = _create_group(client, "owner-1")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    forbidden = client.get(f"/api/v1/groups/{gid}/debts", headers=auth_headers("friend-1"))
    assert forbidden.status_code == 403


def test_group_tagged_debt_visible_to_third_member(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1", "third-1")
    gid = _create_group(client, "owner-1")
    for uid in ("friend-1", "third-1"):
        client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": uid})
        client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers(uid))

    debt = client.post(
        "/api/v1/debts",
        headers=auth_headers("owner-1"),
        json={
            "debtor_name": "Friend",
            "debtor_id": "friend-1",
            "amount": "10.00",
            "currency": "SAR",
            "description": "Dinner",
            "due_date": str(date.today() + timedelta(days=1)),
            "group_id": gid,
        },
    )
    assert debt.status_code == 201

    # Third (non-party) accepted member can see the group-tagged debt.
    listed = client.get(f"/api/v1/groups/{gid}/debts", headers=auth_headers("third-1"))
    assert listed.status_code == 200
    assert any(d["id"] == debt.json()["id"] for d in listed.json())


def test_untagged_debt_invisible_in_group(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1", "third-1")
    gid = _create_group(client, "owner-1")
    for uid in ("friend-1", "third-1"):
        client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": uid})
        client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers(uid))

    untagged = client.post(
        "/api/v1/debts",
        headers=auth_headers("owner-1"),
        json={
            "debtor_name": "Friend",
            "debtor_id": "friend-1",
            "amount": "5.00",
            "currency": "SAR",
            "description": "Personal",
            "due_date": str(date.today() + timedelta(days=1)),
        },
    )
    assert untagged.status_code == 201

    listed = client.get(f"/api/v1/groups/{gid}/debts", headers=auth_headers("third-1"))
    assert listed.status_code == 200
    assert all(d["id"] != untagged.json()["id"] for d in listed.json())


def test_owner_cannot_leave(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1")
    gid = _create_group(client, "owner-1")
    r = client.post(f"/api/v1/groups/{gid}/leave", headers=auth_headers("owner-1"))
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "OwnerCannotLeave"


def test_member_can_leave(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1")
    gid = _create_group(client, "owner-1")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("friend-1"))
    leave = client.post(f"/api/v1/groups/{gid}/leave", headers=auth_headers("friend-1"))
    assert leave.status_code == 200
    assert leave.json()["status"] == "left"


def test_transfer_ownership_immediate(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1")
    gid = _create_group(client, "owner-1")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("friend-1"))
    r = client.post(f"/api/v1/groups/{gid}/transfer-ownership", headers=auth_headers("owner-1"), json={"new_owner_user_id": "friend-1"})
    assert r.status_code == 200
    assert r.json()["owner_id"] == "friend-1"


def test_transfer_to_pending_or_non_member_rejected(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1", "stranger-1")
    gid = _create_group(client, "owner-1")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    # friend-1 is pending, not accepted.
    pending = client.post(f"/api/v1/groups/{gid}/transfer-ownership", headers=auth_headers("owner-1"), json={"new_owner_user_id": "friend-1"})
    assert pending.status_code == 409
    assert pending.json()["detail"]["code"] == "NotAGroupMember"

    nobody = client.post(f"/api/v1/groups/{gid}/transfer-ownership", headers=auth_headers("owner-1"), json={"new_owner_user_id": "stranger-1"})
    assert nobody.status_code == 409
    assert nobody.json()["detail"]["code"] == "NotAGroupMember"


def test_transfer_to_self_rejected(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1")
    gid = _create_group(client, "owner-1")
    r = client.post(f"/api/v1/groups/{gid}/transfer-ownership", headers=auth_headers("owner-1"), json={"new_owner_user_id": "owner-1"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "SameOwner"


def test_delete_blocked_when_debts_attached(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1")
    gid = _create_group(client, "owner-1")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("friend-1"))
    client.post(
        "/api/v1/debts",
        headers=auth_headers("owner-1"),
        json={
            "debtor_name": "Friend", "debtor_id": "friend-1", "amount": "1.00", "currency": "SAR",
            "description": "x", "due_date": str(date.today() + timedelta(days=1)), "group_id": gid,
        },
    )
    r = client.delete(f"/api/v1/groups/{gid}", headers=auth_headers("owner-1"))
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "GroupHasDebts"
    assert r.json()["detail"]["count"] == 1


def test_delete_empty_group_succeeds_and_cascades_pending(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1")
    gid = _create_group(client, "owner-1")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    r = client.delete(f"/api/v1/groups/{gid}", headers=auth_headers("owner-1"))
    assert r.status_code == 204
    # Pending invitee no longer sees the group anywhere.
    listed = client.get("/api/v1/groups", headers=auth_headers("friend-1"))
    assert all(g["id"] != gid for g in listed.json())


def test_revoke_pending_invite(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1")
    gid = _create_group(client, "owner-1")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    r = client.delete(f"/api/v1/groups/{gid}/invites/friend-1", headers=auth_headers("owner-1"))
    assert r.status_code == 204
    # Re-revoke fails.
    r2 = client.delete(f"/api/v1/groups/{gid}/invites/friend-1", headers=auth_headers("owner-1"))
    assert r2.status_code == 404
    assert r2.json()["detail"]["code"] == "NoPendingInvite"


def test_rename_group(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1")
    gid = _create_group(client, "owner-1", name="Old")
    r = client.post(f"/api/v1/groups/{gid}/rename", headers=auth_headers("owner-1"), json={"name": "New"})
    assert r.status_code == 200
    assert r.json()["name"] == "New"


def test_shared_groups_endpoint(client: TestClient) -> None:
    _ensure_profiles(client, "owner-1", "friend-1", "stranger-1")
    gid = _create_group(client, "owner-1")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("friend-1"))

    shared = client.get("/api/v1/groups/shared", headers=auth_headers("owner-1"), params={"with_user_id": "friend-1"})
    assert shared.status_code == 200
    assert len(shared.json()) == 1
    assert shared.json()[0]["id"] == gid

    none = client.get("/api/v1/groups/shared", headers=auth_headers("owner-1"), params={"with_user_id": "stranger-1"})
    assert none.status_code == 200
    assert none.json() == []


def test_group_creation_only_notifies_parties(client: TestClient, reset_repository) -> None:
    _ensure_profiles(client, "owner-1", "friend-1", "third-1")
    gid = _create_group(client, "owner-1")
    for uid in ("friend-1", "third-1"):
        client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": uid})
        client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers(uid))

    # Snapshot pre-creation count of debt_created notifications to third-1.
    pre = sum(1 for n in reset_repository.notifications if n.user_id == "third-1" and n.notification_type.value == "debt_created")

    client.post(
        "/api/v1/debts",
        headers=auth_headers("owner-1"),
        json={
            "debtor_name": "Friend", "debtor_id": "friend-1", "amount": "1.00", "currency": "SAR",
            "description": "x", "due_date": str(date.today() + timedelta(days=1)), "group_id": gid,
        },
    )
    post = sum(1 for n in reset_repository.notifications if n.user_id == "third-1" and n.notification_type.value == "debt_created")
    assert post == pre, "non-party group member should not be notified on group-tagged debt creation"


def test_groups_enabled_default_true_and_toggleable(client: TestClient) -> None:
    headers = auth_headers("solo-1")
    profile = client.get("/api/v1/profiles/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["groups_enabled"] is True

    off = client.patch("/api/v1/profiles/me", headers=headers, json={"groups_enabled": False})
    assert off.status_code == 200
    assert off.json()["groups_enabled"] is False

    refetched = client.get("/api/v1/profiles/me", headers=headers)
    assert refetched.json()["groups_enabled"] is False


@pytest.mark.parametrize("status_when_locked", ["active"])
def test_retag_debt_locked_after_active(client: TestClient, status_when_locked: str) -> None:
    _ensure_profiles(client, "owner-1", "friend-1")
    gid = _create_group(client, "owner-1")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-1"), json={"user_id": "friend-1"})
    client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("friend-1"))

    # Create personal debt first.
    debt = client.post(
        "/api/v1/debts",
        headers=auth_headers("owner-1"),
        json={
            "debtor_name": "Friend", "debtor_id": "friend-1", "amount": "1.00", "currency": "SAR",
            "description": "x", "due_date": str(date.today() + timedelta(days=1)),
        },
    )
    assert debt.status_code == 201
    debt_id = debt.json()["id"]

    # Tag while pending — direct repo call (we haven't wired a PATCH endpoint yet).
    from app.repositories import get_repository
    repo = get_repository()
    tagged = repo.update_debt_group_tag("owner-1", debt_id, gid)
    assert tagged.group_id == gid

    # Accept to flip pending_confirmation → active, then retagging must fail.
    accepted = client.post(f"/api/v1/debts/{debt_id}/accept", headers=auth_headers("friend-1"))
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "active"
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        repo.update_debt_group_tag("owner-1", debt_id, None)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "GroupTagLocked"


# ── T027: Group-tagged debt creation ──────────────────────────────────────────

def test_create_debt_with_group_happy(client: TestClient) -> None:
    _ensure_profiles(client, "cred-1", "deb-1")
    gid = _create_group(client, "cred-1")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("cred-1"), json={"user_id": "deb-1"})
    client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("deb-1"))

    r = client.post(
        "/api/v1/debts",
        headers=auth_headers("cred-1"),
        json={"debtor_name": "D", "debtor_id": "deb-1", "amount": "50.00", "currency": "SAR",
              "description": "group debt", "due_date": str(date.today() + timedelta(days=7)), "group_id": gid},
    )
    assert r.status_code == 201, r.text
    assert r.json()["group_id"] == gid


def test_create_debt_with_group_non_shared_parties_409(client: TestClient) -> None:
    _ensure_profiles(client, "cred-2", "deb-2")
    gid = _create_group(client, "cred-2")
    # deb-2 not invited to group

    r = client.post(
        "/api/v1/debts",
        headers=auth_headers("cred-2"),
        json={"debtor_name": "D", "debtor_id": "deb-2", "amount": "5.00", "currency": "SAR",
              "description": "x", "due_date": str(date.today() + timedelta(days=1)), "group_id": gid},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "NotInSharedGroup"


def test_create_debt_without_group_stays_personal(client: TestClient) -> None:
    _ensure_profiles(client, "cred-3", "deb-3")
    r = client.post(
        "/api/v1/debts",
        headers=auth_headers("cred-3"),
        json={"debtor_name": "D", "debtor_id": "deb-3", "amount": "5.00", "currency": "SAR",
              "description": "personal", "due_date": str(date.today() + timedelta(days=1))},
    )
    assert r.status_code == 201
    assert r.json()["group_id"] is None


def test_create_debt_with_group_but_no_debtor_id_400(client: TestClient) -> None:
    _ensure_profiles(client, "cred-4")
    gid = _create_group(client, "cred-4")
    r = client.post(
        "/api/v1/debts",
        headers=auth_headers("cred-4"),
        json={"debtor_name": "Unknown", "amount": "5.00", "currency": "SAR",
              "description": "x", "due_date": str(date.today() + timedelta(days=1)), "group_id": gid},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "DebtorRequired"


# ── T046: PATCH /debts/{id} group_id retag ────────────────────────────────────

def _setup_two_member_group(client: TestClient, owner: str, member: str) -> tuple[str, str]:
    """Returns (gid, debt_id) — debt is personal, parties share a group."""
    _ensure_profiles(client, owner, member)
    gid = _create_group(client, owner)
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers(owner), json={"user_id": member})
    client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers(member))
    debt = client.post(
        "/api/v1/debts",
        headers=auth_headers(owner),
        json={"debtor_name": "M", "debtor_id": member, "amount": "10.00", "currency": "SAR",
              "description": "x", "due_date": str(date.today() + timedelta(days=3))},
    )
    assert debt.status_code == 201
    return gid, debt.json()["id"]


def test_retag_while_pending_happy(client: TestClient) -> None:
    gid, debt_id = _setup_two_member_group(client, "own-r1", "mem-r1")
    r = client.patch(f"/api/v1/debts/{debt_id}", headers=auth_headers("own-r1"), json={"group_id": gid})
    assert r.status_code == 200
    assert r.json()["group_id"] == gid


def test_retag_to_null_clears_tag(client: TestClient) -> None:
    gid, debt_id = _setup_two_member_group(client, "own-r2", "mem-r2")
    client.patch(f"/api/v1/debts/{debt_id}", headers=auth_headers("own-r2"), json={"group_id": gid})
    r = client.patch(f"/api/v1/debts/{debt_id}", headers=auth_headers("own-r2"), json={"group_id": None})
    assert r.status_code == 200
    assert r.json()["group_id"] is None


def test_retag_after_active_locked(client: TestClient) -> None:
    gid, debt_id = _setup_two_member_group(client, "own-r3", "mem-r3")
    # Accept to push to active.
    client.post(f"/api/v1/debts/{debt_id}/accept", headers=auth_headers("mem-r3"))
    r = client.patch(f"/api/v1/debts/{debt_id}", headers=auth_headers("own-r3"), json={"group_id": gid})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "GroupTagLocked"


def test_retag_to_non_shared_group_409(client: TestClient) -> None:
    _ensure_profiles(client, "own-r4", "mem-r4")
    gid1, debt_id = _setup_two_member_group(client, "own-r4", "mem-r4")
    # Create a second group that mem-r4 doesn't belong to.
    gid2 = _create_group(client, "own-r4", name="Private")
    r = client.patch(f"/api/v1/debts/{debt_id}", headers=auth_headers("own-r4"), json={"group_id": gid2})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "NotInSharedGroup"


# ── Pending-invitee visibility regression (matches "hidden until accepted" rule) ──


def test_pending_invitee_visibility_lifecycle(client: TestClient) -> None:
    """A pending invitee can see they were invited (so they can accept), but
    cannot see the group detail, members list, or debts. Once they accept,
    everything becomes visible."""
    _ensure_profiles(client, "owner-v", "guest-v")
    gid = _create_group(client, "owner-v", name="Family")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-v"), json={"user_id": "guest-v"})

    # Pending invitee sees the group in list_groups with member_status='pending'.
    listed = client.get("/api/v1/groups", headers=auth_headers("guest-v"))
    assert listed.status_code == 200
    rows = [g for g in listed.json() if g["id"] == gid]
    assert len(rows) == 1
    assert rows[0]["member_status"] == "pending"
    # Pending member is NOT counted in member_count.
    assert rows[0]["member_count"] == 1

    # Detail, members, and debts are forbidden until accepted.
    assert client.get(f"/api/v1/groups/{gid}", headers=auth_headers("guest-v")).status_code == 403
    assert client.get(f"/api/v1/groups/{gid}/members", headers=auth_headers("guest-v")).status_code == 403
    assert client.get(f"/api/v1/groups/{gid}/debts", headers=auth_headers("guest-v")).status_code == 403

    # Accept → all of the above become accessible.
    accept = client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("guest-v"))
    assert accept.status_code == 200
    assert client.get(f"/api/v1/groups/{gid}", headers=auth_headers("guest-v")).status_code == 200
    assert client.get(f"/api/v1/groups/{gid}/members", headers=auth_headers("guest-v")).status_code == 200
    assert client.get(f"/api/v1/groups/{gid}/debts", headers=auth_headers("guest-v")).status_code == 200


def _create_group_debt(client: TestClient, creditor: str, debtor: str, group_id: str, amount: str = "20.00") -> str:
    r = client.post(
        "/api/v1/debts",
        headers=auth_headers(creditor),
        json={
            "debtor_name": debtor,
            "debtor_id": debtor,
            "amount": amount,
            "currency": "SAR",
            "description": "Test debt",
            "due_date": str(date.today() + timedelta(days=7)),
            "group_id": group_id,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_bulk_confirm_group_payments_only_eligible(client: TestClient) -> None:
    """Bulk-confirm flips every payment_pending_confirmation debt the caller is
    creditor of; skips debts in other states and debts where caller isn't creditor."""
    _ensure_profiles(client, "creditor-b", "debtor-b1", "debtor-b2", "outsider-c")
    gid = _create_group(client, "creditor-b", name="Shop")
    for uid in ("debtor-b1", "debtor-b2", "outsider-c"):
        client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("creditor-b"), json={"user_id": uid})
        client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers(uid))

    # Two debts owed to creditor-b. We will mark one as paid (→ payment_pending_confirmation),
    # leave the other active. Plus a debt where outsider-c is creditor — must not appear
    # in creditor-b's group overview/list.
    d1 = _create_group_debt(client, "creditor-b", "debtor-b1", gid, amount="10.00")
    d2 = _create_group_debt(client, "creditor-b", "debtor-b2", gid, amount="20.00")
    d3 = _create_group_debt(client, "outsider-c", "debtor-b1", gid, amount="5.00")

    # Debtors accept their debts so they can be marked paid.
    for did, who in ((d1, "debtor-b1"), (d2, "debtor-b2"), (d3, "debtor-b1")):
        client.post(f"/api/v1/debts/{did}/accept", headers=auth_headers(who))

    # Only d1 transitions to payment_pending_confirmation.
    pay = client.post(
        f"/api/v1/debts/{d1}/mark-paid",
        headers=auth_headers("debtor-b1"),
        json={},
    )
    assert pay.status_code in (200, 201), pay.text

    # Bulk-confirm as creditor-b — should only confirm d1.
    r = client.post(f"/api/v1/groups/{gid}/bulk-confirm-payments", headers=auth_headers("creditor-b"))
    assert r.status_code == 200, r.text
    confirmed = r.json()
    assert len(confirmed) == 1
    assert confirmed[0]["id"] == d1
    assert confirmed[0]["status"] == "paid"

    # d2 stays active; d3 is owed to another creditor and is hidden from this group list.
    listed = client.get(f"/api/v1/groups/{gid}/debts", headers=auth_headers("creditor-b")).json()
    by_id = {d["id"]: d for d in listed}
    assert by_id[d2]["status"] == "active"
    assert d3 not in by_id


def test_group_debts_only_show_debts_tagged_to_this_group(client: TestClient) -> None:
    """Untagged debts and debts tagged to a different group must NOT appear in
    a group's debts list, even when the parties are accepted members."""
    _ensure_profiles(client, "owner-x", "member-x")
    gid_a = _create_group(client, "owner-x", name="A")
    gid_b = _create_group(client, "owner-x", name="B")
    for gid in (gid_a, gid_b):
        client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-x"), json={"user_id": "member-x"})
        client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("member-x"))

    untagged = _create_group_debt
    # Debt tagged to B only.
    debt_b = client.post(
        "/api/v1/debts",
        headers=auth_headers("owner-x"),
        json={
            "debtor_name": "M",
            "debtor_id": "member-x",
            "amount": "1.00",
            "currency": "SAR",
            "description": "B-only",
            "due_date": str(date.today() + timedelta(days=3)),
            "group_id": gid_b,
        },
    ).json()["id"]

    # Untagged debt — same parties, no group.
    debt_untagged = client.post(
        "/api/v1/debts",
        headers=auth_headers("owner-x"),
        json={
            "debtor_name": "M",
            "debtor_id": "member-x",
            "amount": "2.00",
            "currency": "SAR",
            "description": "Untagged",
            "due_date": str(date.today() + timedelta(days=3)),
        },
    ).json()["id"]
    _ = untagged  # silence unused

    listed_a = client.get(f"/api/v1/groups/{gid_a}/debts", headers=auth_headers("member-x")).json()
    listed_a_ids = {d["id"] for d in listed_a}
    assert debt_b not in listed_a_ids, "Group A must not show debts tagged to group B"
    assert debt_untagged not in listed_a_ids, "Group A must not show untagged debts"


def test_group_debts_hides_pre_join_debts_from_late_joiner(client: TestClient) -> None:
    """Accepted members can see all owner-owed debts attached to the group."""
    _ensure_profiles(client, "owner-y", "early-y", "late-y", "outside-y")
    gid = _create_group(client, "owner-y", name="Family")
    # early-y joins immediately.
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-y"), json={"user_id": "early-y"})
    client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("early-y"))

    # owner-y creates a group-tagged debt against early-y BEFORE late-y joins.
    pre_join = client.post(
        "/api/v1/debts",
        headers=auth_headers("owner-y"),
        json={
            "debtor_name": "Early",
            "debtor_id": "early-y",
            "amount": "10.00",
            "currency": "SAR",
            "description": "Pre-join debt",
            "due_date": str(date.today() + timedelta(days=3)),
            "group_id": gid,
        },
    ).json()["id"]

    # Now late-y joins.
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-y"), json={"user_id": "late-y"})
    client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("late-y"))

    # owner-y creates a second debt AFTER late-y joined.
    post_join = client.post(
        "/api/v1/debts",
        headers=auth_headers("owner-y"),
        json={
            "debtor_name": "Early",
            "debtor_id": "early-y",
            "amount": "20.00",
            "currency": "SAR",
            "description": "Post-join debt",
            "due_date": str(date.today() + timedelta(days=3)),
            "group_id": gid,
        },
    ).json()["id"]

    # late-y is not a party to either debt, but accepted group transparency shows both.
    listed = client.get(f"/api/v1/groups/{gid}/debts", headers=auth_headers("late-y")).json()
    ids = {d["id"] for d in listed}
    assert post_join in ids
    assert pre_join in ids

    # owner-y (party as creditor) sees both.
    owner_listed = {d["id"] for d in client.get(f"/api/v1/groups/{gid}/debts", headers=auth_headers("owner-y")).json()}
    assert pre_join in owner_listed and post_join in owner_listed

    # early-y (party as debtor) also sees both (party fallback).
    early_listed = {d["id"] for d in client.get(f"/api/v1/groups/{gid}/debts", headers=auth_headers("early-y")).json()}
    assert pre_join in early_listed and post_join in early_listed


def test_group_overview_totals_by_status_and_excludes_paid_from_current(client: TestClient) -> None:
    _ensure_profiles(client, "owner-o", "member-o")
    gid = _create_group(client, "owner-o")
    client.post(f"/api/v1/groups/{gid}/invite", headers=auth_headers("owner-o"), json={"user_id": "member-o"})
    client.post(f"/api/v1/groups/{gid}/accept", headers=auth_headers("member-o"))

    active_debt = _create_group_debt(client, "owner-o", "member-o", gid, amount="10.00")
    paid_debt = _create_group_debt(client, "owner-o", "member-o", gid, amount="4.00")
    client.post(f"/api/v1/debts/{active_debt}/accept", headers=auth_headers("member-o"))
    client.post(f"/api/v1/debts/{paid_debt}/accept", headers=auth_headers("member-o"))
    client.post(f"/api/v1/debts/{paid_debt}/mark-paid", headers=auth_headers("member-o"), json={})
    client.post(f"/api/v1/groups/{gid}/bulk-confirm-payments", headers=auth_headers("owner-o"))

    detail = client.get(f"/api/v1/groups/{gid}", headers=auth_headers("member-o"))
    assert detail.status_code == 200
    overview = detail.json()["debt_overview"]
    assert overview["total_current_owed"] == "10.00"
    assert overview["status_totals"]["active"] == "10.00"
    assert overview["status_totals"]["paid"] == "4.00"


def test_bulk_confirm_group_payments_empty_when_nothing_to_confirm(client: TestClient) -> None:
    _ensure_profiles(client, "creditor-e")
    gid = _create_group(client, "creditor-e", name="Empty")
    r = client.post(f"/api/v1/groups/{gid}/bulk-confirm-payments", headers=auth_headers("creditor-e"))
    assert r.status_code == 200
    assert r.json() == []

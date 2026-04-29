"""Tests for 009-groups-auto-netting — US1 (Phase 3) and US2 (Phase 4).

US1 covers SC-001 and FR-001..FR-005, FR-007, FR-012.
US2 covers SC-002, SC-003, SC-005, SC-006, SC-007 and FR-006..FR-014.
"""
from datetime import UTC, date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.conftest import auth_headers

# ── helpers ──────────────────────────────────────────────────────────────────


def _ensure_profiles(client: TestClient, *user_ids: str) -> None:
    for uid in user_ids:
        client.get("/api/v1/profiles/me", headers=auth_headers(uid))


def _create_group(client: TestClient, owner: str, name: str = "TestGroup") -> str:
    r = client.post("/api/v1/groups", headers=auth_headers(owner), json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _invite_and_accept(client: TestClient, group_id: str, owner: str, member: str) -> None:
    r = client.post(f"/api/v1/groups/{group_id}/invite", headers=auth_headers(owner), json={"user_id": member})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/v1/groups/{group_id}/accept", headers=auth_headers(member))
    assert r.status_code == 200, r.text


def _create_active_debt(
    client: TestClient,
    creditor: str,
    debtor: str,
    amount: str,
    group_id: str,
    currency: str = "SAR",
) -> str:
    """Create a debt and drive it to `active` via debtor acceptance."""
    r = client.post(
        "/api/v1/debts",
        headers=auth_headers(creditor),
        json={
            "debtor_name": debtor,
            "debtor_id": debtor,
            "amount": amount,
            "currency": currency,
            "description": "test debt",
            "due_date": str(date.today() + timedelta(days=7)),
            "group_id": group_id,
        },
    )
    assert r.status_code == 201, r.text
    debt_id = r.json()["id"]
    # Accept the debt so it becomes active.
    accept = client.post(f"/api/v1/debts/{debt_id}/accept", headers=auth_headers(debtor))
    assert accept.status_code == 200, accept.text
    assert accept.json()["status"] == "active"
    return debt_id


def _setup_3_member_group(client: TestClient, a: str = "ua", b: str = "ub", c: str = "uc") -> str:
    """Create a group with three accepted members. A is owner."""
    _ensure_profiles(client, a, b, c)
    gid = _create_group(client, a)
    _invite_and_accept(client, gid, a, b)
    _invite_and_accept(client, gid, a, c)
    return gid


# ── TestProposeSettlement ─────────────────────────────────────────────────────


class TestProposeSettlement:
    """US1 — Propose Group Settlement (Phase 3).

    Tests are written to validate the implementation, covering SC-001 and
    FR-001..FR-005, FR-007, FR-012.
    """

    def test_circular_equal_amounts_auto_settles(self, client: TestClient) -> None:
        """3-member equal circular debts → net-zero → no required parties → immediate settle."""
        gid = _setup_3_member_group(client, "a1", "b1", "c1")
        # A→B 100, B→C 100, C→A 100 (perfect cycle, net zero for all)
        _create_active_debt(client, "a1", "b1", "100.00", gid)
        _create_active_debt(client, "b1", "c1", "100.00", gid)
        _create_active_debt(client, "c1", "a1", "100.00", gid)

        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers("a1"))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["transfers"] == []
        assert body["status"] == "settled"
        # Proposer is a required party only if they are payer/receiver — in net-zero they are not.
        assert body["confirmations"] == []

    def test_asymmetric_circular_creates_open_proposal(self, client: TestClient) -> None:
        """3-member asymmetric debts → 1 net transfer, open proposal, 2 roster rows."""
        gid = _setup_3_member_group(client, "a2", "b2", "c2")
        # A→B 100, B→A 40 → net A owes B 60.
        _create_active_debt(client, "a2", "b2", "100.00", gid)
        _create_active_debt(client, "b2", "a2", "40.00", gid)
        # C is an observer (no net position).
        _create_active_debt(client, "a2", "c2", "50.00", gid)
        _create_active_debt(client, "c2", "a2", "50.00", gid)

        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers("c2"))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "open"
        # Net result: b2 owes a2 100; a2 owes b2 40 → b2 pays a2 net 60; c2 is net zero.
        assert len(body["transfers"]) == 1
        transfer = body["transfers"][0]
        assert transfer["payer_id"] == "b2"
        assert transfer["receiver_id"] == "a2"
        # Roster: exactly payer + receiver = 2.
        assert len(body["confirmations"]) == 2
        roster_users = {c["user_id"] for c in body["confirmations"]}
        assert roster_users == {"a2", "b2"}
        # c2 (proposer) is observer → not in roster.
        assert "c2" not in roster_users

    def test_proposer_in_roster_when_required_party(self, client: TestClient) -> None:
        """Proposer IS in the roster when they are a payer or receiver."""
        gid = _setup_3_member_group(client, "a3", "b3", "c3")
        _create_active_debt(client, "a3", "b3", "80.00", gid)

        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers("a3"))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "open"
        roster_users = {c["user_id"] for c in body["confirmations"]}
        # a3 (proposer, payer) must be in the roster.
        assert "a3" in roster_users

    def test_second_proposal_while_open_returns_409(self, client: TestClient) -> None:
        """A second POST while an open proposal exists → 409 OpenProposalExists."""
        gid = _setup_3_member_group(client, "a4", "b4", "c4")
        _create_active_debt(client, "a4", "b4", "50.00", gid)

        r1 = client.post(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers("a4"))
        assert r1.status_code == 201, r1.text
        existing_id = r1.json()["id"]

        r2 = client.post(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers("b4"))
        assert r2.status_code == 409, r2.text
        detail = r2.json()["detail"]
        assert detail["code"] == "OpenProposalExists"
        assert detail["existing_proposal_id"] == existing_id

    def test_mixed_currency_returns_409_no_row_inserted(self, client: TestClient, reset_repository) -> None:
        """Mixed-currency snapshot → 409 MixedCurrency, no proposal row."""
        gid = _setup_3_member_group(client, "a5", "b5", "c5")
        _create_active_debt(client, "a5", "b5", "50.00", gid, currency="SAR")
        _create_active_debt(client, "b5", "c5", "30.00", gid, currency="USD")

        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers("a5"))
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "MixedCurrency"

        listed = client.get(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers("a5"))
        assert listed.status_code == 200
        assert listed.json() == []

    def test_empty_snapshot_returns_409_nothing_to_settle(self, client: TestClient) -> None:
        """Group with no active/overdue debts → 409 NothingToSettle."""
        gid = _setup_3_member_group(client, "a6", "b6", "c6")

        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers("a6"))
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "NothingToSettle"

    def test_non_member_caller_returns_404(self, client: TestClient) -> None:
        """Non-member triggers 404."""
        gid = _setup_3_member_group(client, "a7", "b7", "c7")
        _create_active_debt(client, "a7", "b7", "50.00", gid)
        _ensure_profiles(client, "x7")

        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers("x7"))
        assert r.status_code == 404, r.text

    def test_snapshot_visibility_observer_gets_null(self, client: TestClient) -> None:
        """FR-007: observer sees snapshot=null; required parties see populated snapshot."""
        gid = _setup_3_member_group(client, "a8", "b8", "c8")
        # a8 owes b8; c8 is observer.
        _create_active_debt(client, "a8", "b8", "70.00", gid)

        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers("a8"))
        assert r.status_code == 201, r.text
        pid = r.json()["id"]

        # a8 and b8 are required parties → snapshot populated.
        for uid in ("a8", "b8"):
            resp = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers(uid))
            assert resp.status_code == 200, resp.text
            assert resp.json()["snapshot"] is not None, f"Required party {uid} should see snapshot"
            assert len(resp.json()["snapshot"]) > 0

        # c8 is observer → snapshot null.
        resp_c = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("c8"))
        assert resp_c.status_code == 200, resp_c.text
        assert resp_c.json()["snapshot"] is None, "Observer should not see snapshot"

    def test_all_members_can_list_proposal(self, client: TestClient) -> None:
        """FR-012: all group members can list the open proposal."""
        gid = _setup_3_member_group(client, "a9", "b9", "c9")
        _create_active_debt(client, "a9", "b9", "90.00", gid)

        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers("a9"))
        assert r.status_code == 201, r.text
        pid = r.json()["id"]

        for uid in ("a9", "b9", "c9"):
            listed = client.get(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers(uid))
            assert listed.status_code == 200, listed.text
            ids = [p["id"] for p in listed.json()]
            assert pid in ids, f"Member {uid} should see the proposal"


# ── helpers for US2 ──────────────────────────────────────────────────────────


def _open_asymmetric_proposal(client: TestClient, a: str, b: str, c: str) -> tuple[str, str]:
    """Set up a 3-member group where a owes b 80 SAR.

    Returns (group_id, proposal_id). The required parties are a and b; c is an observer.
    """
    gid = _setup_3_member_group(client, a, b, c)
    _create_active_debt(client, a, b, "80.00", gid)
    r = client.post(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers(c))
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["status"] == "open"
    return gid, pid


# ── T025: TestConfirmSettlement ───────────────────────────────────────────────


class TestConfirmSettlement:
    """US2 — Confirm Settlement (Phase 4).

    Covers SC-002, SC-003, SC-005 and FR-006, FR-008..FR-011, FR-013.
    """

    def test_happy_path_both_confirm_settles(self, client: TestClient, reset_repository) -> None:
        """Both required parties confirm → proposal settled, debts paid, neutral commitment events."""
        gid, pid = _open_asymmetric_proposal(client, "pa", "pb", "pc")
        # Determine payer and receiver from the proposal.
        r = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("pa"))
        body = r.json()
        assert len(body["transfers"]) == 1
        transfer = body["transfers"][0]
        payer_id = transfer["payer_id"]
        receiver_id = transfer["receiver_id"]
        debt_id = body["snapshot"][0]["debt_id"]

        # Payer confirms first — proposal still open (one pending left).
        r1 = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/confirm", headers=auth_headers(payer_id))
        assert r1.status_code == 200, r1.text
        assert r1.json()["status"] == "open"

        # Receiver confirms — last confirmation → atomic settle.
        r2 = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/confirm", headers=auth_headers(receiver_id))
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["status"] == "settled"

        # Verify debt is paid.
        debt_r = client.get(f"/api/v1/debts/{debt_id}", headers=auth_headers(receiver_id))
        assert debt_r.status_code == 200, debt_r.text
        assert debt_r.json()["status"] == "paid"

        # Verify paired debt_events (marked_paid + payment_confirmed).
        events_r = client.get(f"/api/v1/debts/{debt_id}/events", headers=auth_headers(receiver_id))
        assert events_r.status_code == 200, events_r.text
        event_types = [e["event_type"] for e in events_r.json()]
        assert "marked_paid" in event_types
        assert "payment_confirmed" in event_types
        # Both carry metadata.source='group_settlement'.
        for ev in events_r.json():
            if ev["event_type"] in ("marked_paid", "payment_confirmed"):
                assert ev.get("metadata", {}).get("source") == "group_settlement"

        # Verify neutral commitment event exists (for the debtor's profile).
        events_r2 = client.get("/api/v1/profiles/me/commitment-score-events", headers=auth_headers(payer_id))
        assert events_r2.status_code == 200, events_r2.text
        neutral_events = [e for e in events_r2.json() if e["reason"] == "settlement_neutral"]
        assert len(neutral_events) >= 1
        assert neutral_events[0]["delta"] == 0

        # Commitment scores must be unchanged (neutral delta).
        for uid in (payer_id, receiver_id):
            profile_r = client.get("/api/v1/profiles/me", headers=auth_headers(uid))
            assert profile_r.json()["commitment_score"] == 50

    def test_idempotent_confirm(self, client: TestClient, reset_repository) -> None:
        """Confirming twice is a 200 no-op (idempotent)."""
        gid, pid = _open_asymmetric_proposal(client, "i1a", "i1b", "i1c")
        body = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("i1a")).json()
        payer_id = body["transfers"][0]["payer_id"]
        r1 = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/confirm", headers=auth_headers(payer_id))
        assert r1.status_code == 200
        r2 = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/confirm", headers=auth_headers(payer_id))
        assert r2.status_code == 200
        assert r2.json()["status"] == "open"  # Still open — receiver hasn't confirmed.

    def test_observer_confirm_returns_403(self, client: TestClient, reset_repository) -> None:
        """Observer (zero-net member) calling confirm → 403 NotARequiredParty."""
        gid, pid = _open_asymmetric_proposal(client, "o1a", "o1b", "o1c")
        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/confirm", headers=auth_headers("o1c"))
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "NotARequiredParty"

    def test_confirm_on_rejected_proposal_returns_409(self, client: TestClient, reset_repository) -> None:
        """Confirm on already-rejected proposal → 409 ProposalNotOpen."""
        gid, pid = _open_asymmetric_proposal(client, "rj1a", "rj1b", "rj1c")
        body = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("rj1a")).json()
        payer_id = body["transfers"][0]["payer_id"]
        receiver_id = body["transfers"][0]["receiver_id"]
        # Reject first.
        rej = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/reject", headers=auth_headers(payer_id))
        assert rej.status_code == 200
        assert rej.json()["status"] == "rejected"
        # Now try to confirm as the other party.
        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/confirm", headers=auth_headers(receiver_id))
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "ProposalNotOpen"

    def test_confirm_after_self_reject_returns_409(self, client: TestClient, reset_repository) -> None:
        """A user who already rejected cannot then confirm → 409 AlreadyResponded."""
        gid, pid = _open_asymmetric_proposal(client, "ar1a", "ar1b", "ar1c")
        body = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("ar1a")).json()
        payer_id = body["transfers"][0]["payer_id"]
        # Payer rejects — this voids the proposal immediately.
        rej = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/reject", headers=auth_headers(payer_id))
        assert rej.status_code == 200
        # Now try to confirm (proposal is rejected already).
        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/confirm", headers=auth_headers(payer_id))
        assert r.status_code == 409, r.text
        # Could be ProposalNotOpen (proposal already rejected) or AlreadyResponded.
        assert r.json()["detail"]["code"] in ("ProposalNotOpen", "AlreadyResponded")

    def test_settlement_failed_path(self, client: TestClient, reset_repository) -> None:
        """Patching _apply_settlement to raise triggers settlement_failed status."""
        from app.repositories import get_repository
        from app.repositories.memory import InMemoryRepository

        gid, pid = _open_asymmetric_proposal(client, "sf1a", "sf1b", "sf1c")
        body = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("sf1a")).json()
        payer_id = body["transfers"][0]["payer_id"]
        receiver_id = body["transfers"][0]["receiver_id"]
        debt_id = body["snapshot"][0]["debt_id"]
        original_debt_status = client.get(f"/api/v1/debts/{debt_id}", headers=auth_headers(receiver_id)).json()["status"]

        repo = get_repository()
        assert isinstance(repo, InMemoryRepository)

        # First required party confirms normally.
        r1 = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/confirm", headers=auth_headers(payer_id))
        assert r1.status_code == 200

        # Patch _apply_settlement to raise before the last confirm triggers it.
        with patch.object(repo, "_apply_settlement", side_effect=RuntimeError("boom")):
            r2 = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/confirm", headers=auth_headers(receiver_id))
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["status"] == "settlement_failed"
        assert body2["failure_reason"] == "RuntimeError"

        # Debts must be unchanged (rolled back).
        debt_after = client.get(f"/api/v1/debts/{debt_id}", headers=auth_headers(receiver_id)).json()
        assert debt_after["status"] == original_debt_status

    def test_leave_group_blocked_by_open_proposal(self, client: TestClient, reset_repository) -> None:
        """Required party cannot leave while an open proposal includes them."""
        gid, pid = _open_asymmetric_proposal(client, "lb1a", "lb1b", "lb1c")
        body = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("lb1a")).json()
        payer_id = body["transfers"][0]["payer_id"]
        r = client.post(f"/api/v1/groups/{gid}/leave", headers=auth_headers(payer_id))
        assert r.status_code == 409, r.text
        assert r.json()["detail"]["code"] == "LeaveBlockedByOpenProposal"


# ── T026: TestRejectSettlement ────────────────────────────────────────────────


class TestRejectSettlement:
    """US2 — Reject Settlement (Phase 4).

    Covers SC-006 and FR-014.
    """

    def test_any_required_party_reject_voids_proposal(self, client: TestClient, reset_repository) -> None:
        """Any required party rejects → proposal rejected, debts unchanged."""
        gid, pid = _open_asymmetric_proposal(client, "rv1a", "rv1b", "rv1c")
        body = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("rv1a")).json()
        payer_id = body["transfers"][0]["payer_id"]
        debt_id = body["snapshot"][0]["debt_id"]
        pre_status = client.get(f"/api/v1/debts/{debt_id}", headers=auth_headers("rv1a")).json()["status"]

        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/reject", headers=auth_headers(payer_id))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "rejected"

        # Debts unchanged.
        post_status = client.get(f"/api/v1/debts/{debt_id}", headers=auth_headers("rv1a")).json()["status"]
        assert post_status == pre_status

    def test_reject_notifies_required_parties(self, client: TestClient, reset_repository) -> None:
        """Rejection dispatches settlement_rejected notifications to required parties."""
        gid, pid = _open_asymmetric_proposal(client, "rn1a", "rn1b", "rn1c")
        body = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("rn1a")).json()
        payer_id = body["transfers"][0]["payer_id"]
        receiver_id = body["transfers"][0]["receiver_id"]

        client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/reject", headers=auth_headers(payer_id))

        for uid in (payer_id, receiver_id):
            notifs = client.get("/api/v1/notifications", headers=auth_headers(uid)).json()
            types = [n["notification_type"] for n in notifs]
            assert "settlement_rejected" in types, f"{uid} should have received settlement_rejected"

    def test_fresh_proposal_allowed_after_reject(self, client: TestClient, reset_repository) -> None:
        """After a rejected proposal, a new POST is allowed (201, new id)."""
        gid, pid = _open_asymmetric_proposal(client, "fr1a", "fr1b", "fr1c")
        body = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("fr1a")).json()
        payer_id = body["transfers"][0]["payer_id"]
        client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/reject", headers=auth_headers(payer_id))

        r2 = client.post(f"/api/v1/groups/{gid}/settlement-proposals", headers=auth_headers("fr1c"))
        assert r2.status_code == 201, r2.text
        assert r2.json()["id"] != pid

    def test_observer_cannot_reject(self, client: TestClient, reset_repository) -> None:
        """Observer calling reject → 403 NotARequiredParty."""
        gid, pid = _open_asymmetric_proposal(client, "or1a", "or1b", "or1c")
        r = client.post(f"/api/v1/groups/{gid}/settlement-proposals/{pid}/reject", headers=auth_headers("or1c"))
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["code"] == "NotARequiredParty"


# ── T027: TestExpirySweep ─────────────────────────────────────────────────────


class TestExpirySweep:
    """US2 — Expiry sweep (Phase 4).

    Covers SC-005 and FR-009.
    """

    def test_expired_proposal_on_read(self, client: TestClient, reset_repository) -> None:
        """Artificially expired proposal → read triggers sweep → status expired, debts unchanged."""

        from app.repositories import get_repository
        from app.repositories.memory import InMemoryRepository

        gid, pid = _open_asymmetric_proposal(client, "ex1a", "ex1b", "ex1c")
        body = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("ex1a")).json()
        debt_id = body["snapshot"][0]["debt_id"]
        pre_status = client.get(f"/api/v1/debts/{debt_id}", headers=auth_headers("ex1a")).json()["status"]

        repo = get_repository()
        assert isinstance(repo, InMemoryRepository)
        # Wind expires_at into the past.
        from datetime import datetime
        repo.settlement_proposals[pid]["expires_at"] = datetime.now(tz=UTC) - timedelta(minutes=1)

        resp = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("ex1a"))
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "expired"

        # Debts unchanged.
        assert client.get(f"/api/v1/debts/{debt_id}", headers=auth_headers("ex1a")).json()["status"] == pre_status

    def test_expired_notifications_sent_exactly_once(self, client: TestClient, reset_repository) -> None:
        """Expiry notifications fire exactly once — second read does not re-notify."""
        from datetime import datetime

        from app.repositories import get_repository
        from app.repositories.memory import InMemoryRepository

        gid, pid = _open_asymmetric_proposal(client, "en1a", "en1b", "en1c")
        body = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("en1a")).json()
        payer_id = body["transfers"][0]["payer_id"]
        receiver_id = body["transfers"][0]["receiver_id"]

        repo = get_repository()
        assert isinstance(repo, InMemoryRepository)
        repo.settlement_proposals[pid]["expires_at"] = datetime.now(tz=UTC) - timedelta(minutes=1)

        # First read — triggers sweep.
        client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("en1a"))
        notif_count_after_first = {
            uid: len([n for n in client.get("/api/v1/notifications", headers=auth_headers(uid)).json() if n["notification_type"] == "settlement_expired"])
            for uid in (payer_id, receiver_id)
        }
        for uid in (payer_id, receiver_id):
            assert notif_count_after_first[uid] == 1, f"{uid} should have exactly one settlement_expired notification"

        # Second read — should not re-notify.
        client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("en1a"))
        for uid in (payer_id, receiver_id):
            count = len([n for n in client.get("/api/v1/notifications", headers=auth_headers(uid)).json() if n["notification_type"] == "settlement_expired"])
            assert count == 1, f"{uid} should still have exactly one settlement_expired notification after second read"

    def test_near_expiry_reminder_sent_once(self, client: TestClient, reset_repository) -> None:
        """Within-24h window → pending confirmers get reminder once; second read does not re-send."""
        from datetime import datetime

        from app.repositories import get_repository
        from app.repositories.memory import InMemoryRepository

        gid, pid = _open_asymmetric_proposal(client, "nr1a", "nr1b", "nr1c")
        body = client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("nr1a")).json()
        payer_id = body["transfers"][0]["payer_id"]
        receiver_id = body["transfers"][0]["receiver_id"]

        repo = get_repository()
        assert isinstance(repo, InMemoryRepository)
        # Set expires_at to 6h from now (within 24h window, not yet expired).
        repo.settlement_proposals[pid]["expires_at"] = datetime.now(tz=UTC) + timedelta(hours=6)

        # First read triggers the reminder.
        client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("nr1a"))
        for uid in (payer_id, receiver_id):
            notifs = [n for n in client.get("/api/v1/notifications", headers=auth_headers(uid)).json() if n["notification_type"] == "settlement_reminder"]
            assert len(notifs) == 1, f"{uid} should have one settlement_reminder"

        # Verify reminder_sent_at is now set.
        assert repo.settlement_proposals[pid]["reminder_sent_at"] is not None

        # Second read — no additional reminder.
        client.get(f"/api/v1/groups/{gid}/settlement-proposals/{pid}", headers=auth_headers("nr1a"))
        for uid in (payer_id, receiver_id):
            notifs = [n for n in client.get("/api/v1/notifications", headers=auth_headers(uid)).json() if n["notification_type"] == "settlement_reminder"]
            assert len(notifs) == 1, f"{uid} should still have only one settlement_reminder"

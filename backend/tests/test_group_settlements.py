"""Tests for 009-groups-auto-netting Phase 3 — US1: Propose Group Settlement.

Tests cover SC-001 and FR-001..FR-005, FR-007, FR-012.
"""
from datetime import date, timedelta

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

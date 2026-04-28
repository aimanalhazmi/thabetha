"""Tests for POST /debts/{id}/cancel — cancel non-binding debt UX (Phase 3)."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def _create_pending_debt(client: TestClient, creditor_id: str = "creditor-1", debtor_id: str = "debtor-1") -> dict:
    """Create a debt in pending_confirmation state and return its JSON."""
    cred_headers = auth_headers(creditor_id, "Creditor")
    client.get("/api/v1/profiles/me", headers=cred_headers)
    client.get("/api/v1/profiles/me", headers=auth_headers(debtor_id, "Debtor"))
    resp = client.post(
        "/api/v1/debts",
        headers=cred_headers,
        json={
            "debtor_name": "Debtor",
            "debtor_id": debtor_id,
            "amount": "100.00",
            "currency": "SAR",
            "description": "Test debt",
            "due_date": str(date.today() + timedelta(days=7)),
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ────────────────────────────────────────────────────────────────────────────
# Positive: empty message cancel (T007 — closes research §R8 gap)
# ────────────────────────────────────────────────────────────────────────────

def test_cancel_pending_debt_empty_message(client: TestClient) -> None:
    """Creditor cancels a pending_confirmation debt with an empty message."""
    debt = _create_pending_debt(client)
    assert debt["status"] == "pending_confirmation"

    resp = client.post(
        f"/api/v1/debts/{debt['id']}/cancel",
        headers=auth_headers("creditor-1", "Creditor"),
        json={"message": ""},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_pending_debt_empty_message_writes_debt_event(client: TestClient) -> None:
    """Cancellation with empty message records a debt_cancelled debt_events row."""
    from app.repositories import get_repository
    from app.repositories.memory import InMemoryRepository

    debt = _create_pending_debt(client)
    client.post(
        f"/api/v1/debts/{debt['id']}/cancel",
        headers=auth_headers("creditor-1", "Creditor"),
        json={"message": ""},
    )

    repo = get_repository()
    assert isinstance(repo, InMemoryRepository)
    events = [e for e in repo.debt_events if e.debt_id == debt["id"] and e.event_type == "debt_cancelled"]
    assert len(events) == 1
    assert events[0].message == ""


# ────────────────────────────────────────────────────────────────────────────
# Positive: with-message cancel (T012 — US2 verification)
# ────────────────────────────────────────────────────────────────────────────

def test_cancel_pending_debt_with_message(client: TestClient) -> None:
    """Creditor cancels a pending_confirmation debt with a 50-char message."""
    debt = _create_pending_debt(client, creditor_id="creditor-2", debtor_id="debtor-2")
    message = "Wrong amount, will re-issue tomorrow. Sorry!" [:50]

    resp = client.post(
        f"/api/v1/debts/{debt['id']}/cancel",
        headers=auth_headers("creditor-2", "Creditor"),
        json={"message": message},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


def test_cancel_with_message_propagates_to_event(client: TestClient) -> None:
    """The 50-char message lands verbatim in the debt_events row."""
    from app.repositories import get_repository
    from app.repositories.memory import InMemoryRepository

    debt = _create_pending_debt(client, creditor_id="creditor-3", debtor_id="debtor-3")
    message = "A" * 50

    client.post(
        f"/api/v1/debts/{debt['id']}/cancel",
        headers=auth_headers("creditor-3", "Creditor"),
        json={"message": message},
    )

    repo = get_repository()
    assert isinstance(repo, InMemoryRepository)
    events = [e for e in repo.debt_events if e.debt_id == debt["id"] and e.event_type == "debt_cancelled"]
    assert len(events) == 1
    assert events[0].message == message


def test_cancel_with_message_creates_debt_cancelled_notification(client: TestClient) -> None:
    """A debt_cancelled notification is created for the debtor when message is present."""
    from app.repositories import get_repository
    from app.repositories.memory import InMemoryRepository
    from app.schemas.domain import NotificationType

    debt = _create_pending_debt(client, creditor_id="creditor-4", debtor_id="debtor-4")
    message = "Re-issuing with correct terms"

    client.post(
        f"/api/v1/debts/{debt['id']}/cancel",
        headers=auth_headers("creditor-4", "Creditor"),
        json={"message": message},
    )

    repo = get_repository()
    assert isinstance(repo, InMemoryRepository)
    notifications = [n for n in repo.notifications if n.user_id == "debtor-4" and n.notification_type == NotificationType.debt_cancelled]
    assert len(notifications) >= 1
    # The message is used as the notification body when non-empty.
    assert message in notifications[-1].body


# ────────────────────────────────────────────────────────────────────────────
# Positive: cancel from edit_requested state
# ────────────────────────────────────────────────────────────────────────────

def test_cancel_edit_requested_debt(client: TestClient) -> None:
    """Creditor can also cancel a debt that is in edit_requested."""
    debt = _create_pending_debt(client, creditor_id="creditor-5", debtor_id="debtor-5")

    # Debtor requests edit → moves to edit_requested
    client.post(
        f"/api/v1/debts/{debt['id']}/request-edit",
        headers=auth_headers("debtor-5", "Debtor"),
        json={"message": "Please update amount", "requested_amount": "150.00"},
    )

    resp = client.post(
        f"/api/v1/debts/{debt['id']}/cancel",
        headers=auth_headers("creditor-5", "Creditor"),
        json={"message": ""},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


# ────────────────────────────────────────────────────────────────────────────
# Negative: cancel from active state must return 409
# ────────────────────────────────────────────────────────────────────────────

def test_cancel_active_debt_returns_409(client: TestClient) -> None:
    """Attempting to cancel an active debt returns 409 Conflict."""
    debt = _create_pending_debt(client, creditor_id="creditor-6", debtor_id="debtor-6")

    # Debtor accepts → moves to active
    client.post(
        f"/api/v1/debts/{debt['id']}/accept",
        headers=auth_headers("debtor-6", "Debtor"),
    )

    resp = client.post(
        f"/api/v1/debts/{debt['id']}/cancel",
        headers=auth_headers("creditor-6", "Creditor"),
        json={"message": ""},
    )
    assert resp.status_code == 409


# ────────────────────────────────────────────────────────────────────────────
# Negative: debtor cannot cancel
# ────────────────────────────────────────────────────────────────────────────

def test_debtor_cannot_cancel_debt(client: TestClient) -> None:
    """Only the creditor can cancel; debtor gets 403."""
    debt = _create_pending_debt(client, creditor_id="creditor-7", debtor_id="debtor-7")

    resp = client.post(
        f"/api/v1/debts/{debt['id']}/cancel",
        headers=auth_headers("debtor-7", "Debtor"),
        json={"message": ""},
    )
    assert resp.status_code == 403

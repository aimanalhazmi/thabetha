from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def _create_debt(client: TestClient, creditor_headers: dict[str, str], debtor_id: str = "customer-receipt") -> dict:
    response = client.post(
        "/api/v1/debts",
        headers=creditor_headers,
        json={
            "debtor_name": "Receipt Customer",
            "debtor_id": debtor_id,
            "amount": "42.00",
            "currency": "SAR",
            "description": "Receipt-backed order",
            "due_date": str(date.today() + timedelta(days=2)),
        },
    )
    assert response.status_code == 201
    return response.json()


def _upload_receipt(client: TestClient, debt_id: str, headers: dict[str, str], filename: str, content_type: str = "image/jpeg") -> dict:
    response = client.post(
        f"/api/v1/debts/{debt_id}/attachments",
        headers=headers,
        params={"attachment_type": "invoice"},
        files={"file": (filename, b"receipt-bytes", content_type)},
    )
    assert response.status_code == 201
    return response.json()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_create_debt_uploads_two_invoice_receipts_and_audits_events(client: TestClient) -> None:
    creditor_headers = auth_headers("merchant-receipt", "Receipt Shop")
    debtor_headers = auth_headers("customer-receipt", "Receipt Customer")
    client.get("/api/v1/profiles/me", headers=creditor_headers)
    client.get("/api/v1/profiles/me", headers=debtor_headers)
    debt = _create_debt(client, creditor_headers)

    first = _upload_receipt(client, debt["id"], creditor_headers, "invoice-1.jpg")
    second = _upload_receipt(client, debt["id"], creditor_headers, "invoice-2.pdf", "application/pdf")

    assert first["attachment_type"] == "invoice"
    assert second["attachment_type"] == "invoice"
    assert first["retention_state"] == "available"
    assert second["url_expires_at"] is not None

    events = client.get(f"/api/v1/debts/{debt['id']}/events", headers=creditor_headers)
    assert events.status_code == 200
    uploaded_events = [event for event in events.json() if event["event_type"] == "attachment_uploaded"]
    assert len(uploaded_events) == 2
    assert {event["metadata"]["file_name"] for event in uploaded_events} == {"invoice-1.jpg", "invoice-2.pdf"}


def test_debtor_lists_receipts_with_signed_expiry_and_archived_retention(client: TestClient) -> None:
    creditor_headers = auth_headers("merchant-retention", "Retention Shop")
    debtor_headers = auth_headers("customer-retention", "Retention Customer")
    outsider_headers = auth_headers("outsider-retention", "Outsider")
    client.get("/api/v1/profiles/me", headers=creditor_headers)
    client.get("/api/v1/profiles/me", headers=debtor_headers)
    debt = _create_debt(client, creditor_headers, debtor_id="customer-retention")
    _upload_receipt(client, debt["id"], creditor_headers, "paid-receipt.jpg")

    forbidden = client.get(f"/api/v1/debts/{debt['id']}/attachments", headers=outsider_headers)
    assert forbidden.status_code == 403

    accepted = client.post(f"/api/v1/debts/{debt['id']}/accept", headers=debtor_headers)
    assert accepted.status_code == 200
    payment = client.post(f"/api/v1/debts/{debt['id']}/mark-paid", headers=debtor_headers, json={"note": "cash"})
    assert payment.status_code == 200
    confirmed = client.post(f"/api/v1/debts/{debt['id']}/confirm-payment", headers=creditor_headers)
    assert confirmed.status_code == 200

    listed = client.get(f"/api/v1/debts/{debt['id']}/attachments", headers=debtor_headers)
    assert listed.status_code == 200
    attachments = listed.json()
    assert len(attachments) == 1
    attachment = attachments[0]
    assert attachment["retention_state"] == "archived"
    assert attachment["retention_expires_at"] is not None

    expires_at = _parse_datetime(attachment["url_expires_at"])
    ttl = expires_at - datetime.now(UTC)
    assert timedelta(minutes=59) <= ttl <= timedelta(minutes=61)


def test_invalid_receipt_upload_does_not_hide_created_debt(client: TestClient) -> None:
    creditor_headers = auth_headers("merchant-invalid", "Invalid Shop")
    debtor_headers = auth_headers("customer-invalid", "Invalid Customer")
    client.get("/api/v1/profiles/me", headers=creditor_headers)
    client.get("/api/v1/profiles/me", headers=debtor_headers)
    debt = _create_debt(client, creditor_headers, debtor_id="customer-invalid")

    invalid = client.post(
        f"/api/v1/debts/{debt['id']}/attachments",
        headers=creditor_headers,
        params={"attachment_type": "invoice"},
        files={"file": ("receipt.txt", b"not a receipt", "text/plain")},
    )
    assert invalid.status_code == 400

    readable = client.get(f"/api/v1/debts/{debt['id']}", headers=creditor_headers)
    assert readable.status_code == 200
    assert readable.json()["id"] == debt["id"]

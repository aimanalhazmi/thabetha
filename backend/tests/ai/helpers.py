from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def enable_ai(client: TestClient, user_id: str = "merchant-1", account_type: str = "creditor", locale: str = "en") -> dict[str, str]:
    headers = auth_headers(user_id, name=user_id)
    response = client.patch(
        "/api/v1/profiles/me",
        headers=headers,
        json={"ai_enabled": True, "preferred_language": locale, "account_type": account_type},
    )
    assert response.status_code == 200, response.text
    return headers


def create_debt(
    client: TestClient,
    creditor_h: dict[str, str],
    *,
    debtor_name: str,
    amount: str,
    due_date: str,
    description: str = "test debt",
    currency: str = "SAR",
) -> dict:
    response = client.post(
        "/api/v1/debts",
        headers=creditor_h,
        json={
            "debtor_name": debtor_name,
            "amount": amount,
            "currency": currency,
            "description": description,
            "due_date": due_date,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def post_chat(
    client: TestClient,
    headers: dict[str, str],
    message: str,
    *,
    history: list | None = None,
    locale: str = "en",
    timezone: str = "Asia/Riyadh",
):
    return client.post(
        "/api/v1/ai/merchant-chat",
        headers=headers,
        json={
            "message": message,
            "history": history or [],
            "locale": locale,
            "timezone": timezone,
        },
    )

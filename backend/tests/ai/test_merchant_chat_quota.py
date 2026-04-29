"""US4 — tier gating + daily quota."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from app.repositories import get_repository
from app.services.ai.limits import MERCHANT_CHAT_FEATURE
from tests.ai.helpers import enable_ai, post_chat
from tests.conftest import auth_headers


def test_disabled_returns_403(client: TestClient) -> None:
    headers = auth_headers("free-tier-user")
    # Make sure profile exists but ai_enabled stays false.
    client.get("/api/v1/profiles/me", headers=headers)
    r = post_chat(client, headers, "Who owes me the most?")
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["detail"]["code"] in ("ai_subscription_required", "ai_not_enabled")


def test_quota_exhausted_returns_429(client: TestClient) -> None:
    headers = enable_ai(client, "quota-user-1")
    repo = get_repository()
    # Pre-fill the daily count to the cap.
    cap = 50
    for _ in range(cap):
        repo.increment_ai_usage("quota-user-1", MERCHANT_CHAT_FEATURE, date.today(), cap)
    r = post_chat(client, headers, "Who owes me the most?")
    assert r.status_code == 429, r.text
    assert r.headers.get("Retry-After")
    assert r.json()["detail"]["code"] == "ai_daily_limit_reached"


def test_successful_call_increments_quota_once(client: TestClient) -> None:
    headers = enable_ai(client, "quota-user-2")
    repo = get_repository()
    before = repo.get_ai_usage_count("quota-user-2", MERCHANT_CHAT_FEATURE, date.today())
    r = post_chat(client, headers, "What's my overdue exposure?")
    assert r.status_code == 200
    after = repo.get_ai_usage_count("quota-user-2", MERCHANT_CHAT_FEATURE, date.today())
    assert after == before + 1


def test_provider_error_returns_503_without_consuming_quota(client: TestClient, monkeypatch) -> None:
    headers = enable_ai(client, "quota-user-3")
    repo = get_repository()
    before = repo.get_ai_usage_count("quota-user-3", MERCHANT_CHAT_FEATURE, date.today())

    from app.services.ai.merchant_chat import orchestrator
    from app.services.ai.merchant_chat.provider import MerchantChatProvider, MerchantChatProviderError

    class BoomProvider(MerchantChatProvider):
        def chat(self, request):
            raise MerchantChatProviderError("upstream down")

    monkeypatch.setattr(orchestrator, "_select_provider", lambda _name: BoomProvider())

    r = post_chat(client, headers, "Who owes me the most?")
    assert r.status_code == 503, r.text
    assert r.json()["detail"]["code"] == "ai_provider_unavailable"
    after = repo.get_ai_usage_count("quota-user-3", MERCHANT_CHAT_FEATURE, date.today())
    assert after == before, "provider failure must not consume quota"

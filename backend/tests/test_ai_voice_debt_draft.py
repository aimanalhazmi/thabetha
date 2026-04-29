from datetime import date

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.repositories.memory import InMemoryRepository
from tests.conftest import auth_headers


def _enable_ai(client: TestClient, user_id: str = "merchant-1", preferred_language: str = "ar") -> dict[str, str]:
    headers = auth_headers(user_id)
    response = client.patch(
        "/api/v1/profiles/me",
        headers=headers,
        json={"ai_enabled": True, "preferred_language": preferred_language, "account_type": "creditor"},
    )
    assert response.status_code == 200
    return headers


def test_voice_draft_from_multipart_audio_success(client: TestClient) -> None:
    headers = _enable_ai(client)
    response = client.post(
        "/api/v1/ai/debt-draft-from-voice",
        headers=headers,
        files={"audio": ("voice.webm", b"for Ahmed 25 SAR groceries due 2026-05-01", "audio/webm")},
        data={"client_duration_seconds": "30"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["debtor_name"] == "Ahmed"
    assert body["amount"] == "25"
    assert body["currency"] == "SAR"
    assert body["due_date"] == "2026-05-01"
    assert body["raw_transcript"] == "for Ahmed 25 SAR groceries due 2026-05-01"
    assert body["field_confirmations"]["amount"] == "extracted_unconfirmed"


def test_voice_draft_rejects_unsupported_audio_and_long_audio(client: TestClient) -> None:
    headers = _enable_ai(client)
    unsupported = client.post(
        "/api/v1/ai/debt-draft-from-voice",
        headers=headers,
        files={"audio": ("voice.txt", b"for Ahmed 25", "text/plain")},
    )
    assert unsupported.status_code == 415
    assert unsupported.json()["detail"]["code"] == "unsupported_audio_type"

    too_long = client.post(
        "/api/v1/ai/debt-draft-from-voice",
        headers=headers,
        files={"audio": ("voice.webm", b"for Ahmed 25", "audio/webm")},
        data={"client_duration_seconds": "61"},
    )
    assert too_long.status_code == 413
    assert too_long.json()["detail"]["code"] == "audio_too_long"


def test_successful_voice_draft_deletes_temp_audio(client: TestClient, reset_repository: InMemoryRepository) -> None:
    headers = _enable_ai(client)
    response = client.post(
        "/api/v1/ai/debt-draft-from-voice",
        headers=headers,
        files={"audio": ("voice.webm", b"for Ahmed 25 SAR groceries", "audio/webm")},
    )
    assert response.status_code == 200
    assert response.json().get("url") is None
    assert reset_repository.temp_voice_notes
    assert all(note["deleted_at"] is not None and note["content"] == b"" for note in reset_repository.temp_voice_notes.values())


def test_voice_draft_never_profile_matches_debtor_name(client: TestClient) -> None:
    headers = _enable_ai(client)
    client.get("/api/v1/profiles/me", headers=auth_headers("ahmed-1", "Ahmed"))
    response = client.post(
        "/api/v1/ai/debt-draft-from-voice",
        headers=headers,
        files={"audio": ("voice.webm", b"for Ahmed 25 SAR groceries", "audio/webm")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["debtor_name"] == "Ahmed"
    assert "debtor_id" not in body
    assert "matches" not in body


def test_json_transcript_missing_fields_and_currency_locale(client: TestClient) -> None:
    headers = _enable_ai(client, preferred_language="en")
    response = client.post(
        "/api/v1/ai/debt-draft-from-voice",
        headers=headers,
        json={"transcript": "for Ahmed groceries due 2026-05-01"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["amount"] is None
    assert body["currency"] == "USD"
    assert body["raw_transcript"] == "for Ahmed groceries due 2026-05-01"
    assert body["field_confirmations"]["amount"] == "missing"
    assert body["field_confirmations"]["currency"] == "extracted_unconfirmed"


def test_ai_subscription_required_for_json_and_multipart(client: TestClient) -> None:
    headers = auth_headers("merchant-1")
    json_response = client.post(
        "/api/v1/ai/debt-draft-from-voice",
        headers=headers,
        json={"transcript": "for Ahmed 25 SAR groceries"},
    )
    assert json_response.status_code == 403
    assert json_response.json()["detail"]["code"] == "ai_subscription_required"

    multipart_response = client.post(
        "/api/v1/ai/debt-draft-from-voice",
        headers=headers,
        files={"audio": ("voice.webm", b"for Ahmed 25 SAR groceries", "audio/webm")},
    )
    assert multipart_response.status_code == 403
    assert multipart_response.json()["detail"]["code"] == "ai_subscription_required"


def test_daily_limit_applies_to_json_and_multipart(client: TestClient) -> None:
    settings = get_settings()
    original_limit = settings.ai_voice_draft_daily_limit
    settings.ai_voice_draft_daily_limit = 1
    try:
        headers = _enable_ai(client)
        first = client.post(
            "/api/v1/ai/debt-draft-from-voice",
            headers=headers,
            json={"transcript": "for Ahmed 25 SAR groceries"},
        )
        assert first.status_code == 200
        second = client.post(
            "/api/v1/ai/debt-draft-from-voice",
            headers=headers,
            files={"audio": ("voice.webm", b"for Ahmed 25 SAR groceries", "audio/webm")},
        )
        assert second.status_code == 429
        assert second.headers["Retry-After"]
        assert second.json()["detail"]["code"] == "ai_daily_limit_reached"
    finally:
        settings.ai_voice_draft_daily_limit = original_limit


def test_invalid_audio_and_failed_transcription_do_not_increment_usage(client: TestClient, reset_repository: InMemoryRepository) -> None:
    headers = _enable_ai(client)
    invalid = client.post(
        "/api/v1/ai/debt-draft-from-voice",
        headers=headers,
        files={"audio": ("voice.txt", b"for Ahmed 25", "text/plain")},
    )
    assert invalid.status_code == 415
    failed = client.post(
        "/api/v1/ai/debt-draft-from-voice",
        headers=headers,
        files={"audio": ("voice.webm", b"", "audio/webm")},
    )
    assert failed.status_code == 422
    assert reset_repository.get_ai_usage_count("merchant-1", "voice_debt_draft", date.today()) == 0

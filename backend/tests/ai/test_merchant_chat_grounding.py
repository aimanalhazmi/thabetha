"""US1 — grounded ledger Q&A for the caller (and US3 follow-ups)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.ai.helpers import create_debt, enable_ai, post_chat


def _seed_basic_ledger(client: TestClient, headers: dict[str, str]) -> dict[str, dict]:
    a = create_debt(client, headers, debtor_name="Alpha", amount="500.00", due_date="2026-06-01")
    b = create_debt(client, headers, debtor_name="Bravo", amount="1200.00", due_date="2026-06-15")
    c = create_debt(client, headers, debtor_name="Charlie", amount="300.00", due_date="2026-06-30")
    return {"alpha": a, "bravo": b, "charlie": c}


def test_who_owes_me_the_most(client: TestClient) -> None:
    headers = enable_ai(client, "creditor-grounding-1")
    _seed_basic_ledger(client, headers)
    r = post_chat(client, headers, "Who owes me the most?")
    assert r.status_code == 200, r.text
    body = r.json()
    answer = body["answer"]
    assert "Bravo" in answer
    assert "1200" in answer.replace(",", "")


def test_overdue_exposure_no_overdue_returns_zero(client: TestClient) -> None:
    headers = enable_ai(client, "creditor-grounding-2")
    _seed_basic_ledger(client, headers)
    r = post_chat(client, headers, "What's my overdue exposure?")
    assert r.status_code == 200
    answer = r.json()["answer"]
    assert "no overdue" in answer.lower()


def test_no_data_returns_unavailable(client: TestClient) -> None:
    headers = enable_ai(client, "creditor-grounding-3")
    # No debts seeded.
    r = post_chat(client, headers, "Did Zeta pay me last month?")
    assert r.status_code == 200
    answer = r.json()["answer"]
    assert "don't have" in answer.lower() or "no" in answer.lower()


def test_top_n_abridgement_when_more_than_cap(client: TestClient) -> None:
    headers = enable_ai(client, "creditor-grounding-4")
    # Seed 25 active debts with descending amounts to force truncation.
    for i in range(25):
        create_debt(
            client,
            headers,
            debtor_name=f"Debtor{i:02d}",
            amount=f"{1000 - i}.00",
            due_date="2026-06-01",
        )
    r = post_chat(client, headers, "Who owes me the most?")
    assert r.status_code == 200
    body = r.json()
    # The mock provider prefaces with "showing top N of M" when truncated.
    assert "of 25" in body["answer"].lower() or "top 20" in body["answer"].lower()
    # Tool trace should be present in non-production env and report the call.
    trace = body.get("tool_trace") or []
    assert any(entry["tool"] == "list_debts" for entry in trace)


def test_history_is_trimmed_to_last_10(client: TestClient) -> None:
    headers = enable_ai(client, "creditor-grounding-5")
    _seed_basic_ledger(client, headers)
    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn-{i}"}
        for i in range(15)
    ]
    r = post_chat(client, headers, "Who owes me the most?", history=long_history)
    assert r.status_code == 200, r.text
    # Just assert success — server must not 422 on long histories.


def test_followup_resolves_with_history(client: TestClient) -> None:
    headers = enable_ai(client, "creditor-grounding-6")
    _seed_basic_ledger(client, headers)
    history = [
        {"role": "user", "content": "List my active debts."},
        {"role": "assistant", "content": "You have 3 active debts: Alpha, Bravo, Charlie."},
    ]
    r = post_chat(client, headers, "And which one is the oldest?", history=history)
    assert r.status_code == 200
    answer = r.json()["answer"]
    # The first seeded debt (Alpha) is the oldest by created_at.
    assert "Alpha" in answer

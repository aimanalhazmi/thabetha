"""Tool functions in isolation against InMemoryRepository."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.repositories import get_repository
from app.services.ai.merchant_chat.tools import (
    LIST_DEBTS_ROW_CAP,
    make_get_dashboard_summary,
    make_get_debt,
    make_list_debts,
)
from tests.ai.helpers import create_debt, enable_ai


def test_list_debts_filters_and_caps(client: TestClient) -> None:
    headers = enable_ai(client, "tools-user-1")
    for i in range(25):
        create_debt(
            client,
            headers,
            debtor_name=f"Debtor{i:02d}",
            amount=f"{1000 - i}.00",
            due_date="2026-06-01",
        )
    repo = get_repository()
    fn = make_list_debts(repo, "tools-user-1")
    result = fn({"role": "creditor"})
    assert result["total_count"] == 25
    assert len(result["rows"]) == LIST_DEBTS_ROW_CAP
    assert result["truncated"] is True
    # Sorted by amount desc — top row is the largest amount (1000).
    assert result["rows"][0]["amount"] == "1000.00"


def test_list_debts_status_filter(client: TestClient) -> None:
    headers = enable_ai(client, "tools-user-2")
    create_debt(client, headers, debtor_name="Pending", amount="100.00", due_date="2026-06-01")
    repo = get_repository()
    fn = make_list_debts(repo, "tools-user-2")
    paid_only = fn({"role": "creditor", "status": ["paid"]})
    assert paid_only["total_count"] == 0


def test_get_debt_for_unauthorised_returns_none(client: TestClient) -> None:
    enable_ai(client, "tools-user-3a")
    b_h = enable_ai(client, "tools-user-3b")
    b_debt = create_debt(client, b_h, debtor_name="X", amount="50.00", due_date="2026-06-01")
    repo = get_repository()
    fn = make_get_debt(repo, "tools-user-3a")
    assert fn({"debt_id": b_debt["id"]}) == {"row": None}


def test_get_dashboard_summary_returns_facts(client: TestClient) -> None:
    headers = enable_ai(client, "tools-user-4")
    create_debt(client, headers, debtor_name="X", amount="50.00", due_date="2026-06-01")
    repo = get_repository()
    fn = make_get_dashboard_summary(repo, "tools-user-4")
    result = fn({})
    assert "total_receivable" in result
    assert "active_count" in result


def test_tools_only_use_scoped_repo_methods(client: TestClient) -> None:
    """Defence in depth: tools must never reach for elevated/system pathways.

    We monkey-patch the repository so any method whose name starts with
    `system_` or ends with `_admin` raises immediately. Each tool must run
    cleanly through this hostile repo.
    """
    headers = enable_ai(client, "tools-user-5")
    create_debt(client, headers, debtor_name="X", amount="50.00", due_date="2026-06-01")
    repo = get_repository()

    forbidden_calls: list[str] = []
    original_getattr = type(repo).__getattribute__

    def _hostile_getattr(self, name):
        if name.startswith("system_") or name.endswith("_admin"):
            forbidden_calls.append(name)
            raise AssertionError(f"forbidden repo call: {name}")
        return original_getattr(self, name)

    # Apply on the class so closures see it.
    type(repo).__getattribute__ = _hostile_getattr  # type: ignore[assignment]
    try:
        from app.services.ai.merchant_chat.tools import (
            make_get_commitment_history,
            make_get_dashboard_summary,
            make_get_debt,
            make_list_debts,
        )

        make_list_debts(repo, "tools-user-5")({"role": "creditor"})
        make_get_dashboard_summary(repo, "tools-user-5")({})
        make_get_commitment_history(repo, "tools-user-5")({})
        # get_debt with a non-existent id is fine; we just want to exercise the path.
        make_get_debt(repo, "tools-user-5")({"debt_id": "nonexistent"})
    finally:
        type(repo).__getattribute__ = original_getattr  # type: ignore[assignment]

    assert forbidden_calls == [], f"tools called forbidden repo methods: {forbidden_calls}"

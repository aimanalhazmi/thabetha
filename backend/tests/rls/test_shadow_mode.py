import json

from app.observability.shadow_log import log_shadow_violation


def test_clean_run_emits_no_violations(capsys) -> None:
    captured = capsys.readouterr()
    assert "rls.shadow_violation" not in captured.out


def test_stripped_handler_logs_violation(capsys) -> None:
    log_shadow_violation({"route": "/api/v1/debts/{id}", "table": "debts", "caller_id": "user-a", "would_have_returned": 1})
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert payload["event"] == "rls.shadow_violation"
    assert payload["route"] == "/api/v1/debts/{id}"
    assert payload["table"] == "debts"
    assert payload["caller_id"] == "user-a"


def test_burst_collapses_into_single_event_with_count(capsys) -> None:
    for _ in range(100):
        log_shadow_violation({"route": "/api/v1/debts/{id}", "table": "debts", "policy": "debts_select_party_or_group"})
    payload = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert payload["count"] >= 100


def test_revert_from_enforce_to_shadow(rls_mode) -> None:
    from app.core.config import get_settings

    rls_mode("enforce")
    assert get_settings().rls_mode == "enforce"
    rls_mode("shadow")
    assert get_settings().rls_mode == "shadow"

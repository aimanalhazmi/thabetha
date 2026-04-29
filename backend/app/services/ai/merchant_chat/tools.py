from __future__ import annotations

import hashlib
import hmac
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.repositories import Repository
from app.schemas.domain import DebtOut, DebtStatus

LIST_DEBTS_ROW_CAP = 20
COMMITMENT_HISTORY_CAP = 20


def hash_user_id(user_id: str) -> str:
    salt = get_settings().merchant_chat_log_salt.encode("utf-8")
    digest = hmac.new(salt, user_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:8]


def _serialise_debt(debt: DebtOut) -> dict[str, Any]:
    return {
        "id": debt.id,
        "creditor_id": debt.creditor_id,
        "debtor_id": debt.debtor_id,
        "debtor_name": debt.debtor_name,
        "amount": str(debt.amount),
        "currency": debt.currency,
        "description": debt.description,
        "status": str(debt.status),
        "due_date": debt.due_date.isoformat(),
        "created_at": debt.created_at.isoformat(),
        "paid_at": debt.paid_at.isoformat() if debt.paid_at else None,
        "group_id": debt.group_id,
    }


def _matches_role(debt: DebtOut, user_id: str, role: str) -> bool:
    if role == "any":
        return True
    if role == "creditor":
        return debt.creditor_id == user_id
    if role == "debtor":
        return debt.debtor_id == user_id
    return True


def _matches_status(debt: DebtOut, statuses: list[str] | None) -> bool:
    if not statuses:
        return True
    return str(debt.status) in {str(s) for s in statuses}


def _matches_counterparty(debt: DebtOut, query: str | None) -> bool:
    if not query:
        return True
    return query.lower() in (debt.debtor_name or "").lower()


def _matches_amount(debt: DebtOut, min_amount: Decimal | None, max_amount: Decimal | None) -> bool:
    if min_amount is not None and debt.amount < min_amount:
        return False
    if max_amount is not None and debt.amount > max_amount:
        return False
    return True


def _matches_date(debt: DebtOut, from_date: date | None, to_date: date | None) -> bool:
    created = debt.created_at.date() if isinstance(debt.created_at, datetime) else debt.created_at
    if from_date is not None and created < from_date:
        return False
    if to_date is not None and created >= to_date:
        return False
    return True


def make_list_debts(repo: Repository, user_id: str):
    def list_debts(args: dict[str, Any]) -> dict[str, Any]:
        role = args.get("role", "any")
        statuses = args.get("status") or []
        counterparty = args.get("counterparty_name_query")
        from_d = _parse_date(args.get("from_date"))
        to_d = _parse_date(args.get("to_date"))
        min_amt = _parse_decimal(args.get("min_amount"))
        max_amt = _parse_decimal(args.get("max_amount"))

        all_debts = repo.list_debts_for_user(user_id)
        matched = [
            d
            for d in all_debts
            if _matches_role(d, user_id, role)
            and _matches_status(d, statuses)
            and _matches_counterparty(d, counterparty)
            and _matches_date(d, from_d, to_d)
            and _matches_amount(d, min_amt, max_amt)
        ]
        matched.sort(key=lambda d: (-d.amount, d.created_at), reverse=False)
        # sort by amount desc, then created_at desc
        matched.sort(key=lambda d: (d.amount, d.created_at), reverse=True)
        rows = matched[:LIST_DEBTS_ROW_CAP]
        total_count = len(matched)
        total_sum = sum((d.amount for d in matched), Decimal("0"))
        return {
            "rows": [_serialise_debt(d) for d in rows],
            "total_count": total_count,
            "total_sum": str(total_sum),
            "truncated": total_count > len(rows),
        }

    return list_debts


def make_get_debt(repo: Repository, user_id: str):
    def get_debt(args: dict[str, Any]) -> dict[str, Any]:
        debt_id = args.get("debt_id")
        if not debt_id:
            return {"error": "invalid_filter", "message": "debt_id is required"}
        try:
            debt = repo.get_authorized_debt(user_id, str(debt_id))
        except Exception:
            return {"row": None}
        if debt is None:
            return {"row": None}
        return {"row": _serialise_debt(debt)}

    return get_debt


def make_get_dashboard_summary(repo: Repository, user_id: str):
    def get_dashboard_summary(_args: dict[str, Any]) -> dict[str, Any]:
        facts = repo.merchant_facts(user_id)
        return dict(facts)

    return get_dashboard_summary


def make_get_commitment_history(repo: Repository, user_id: str):
    def get_commitment_history(_args: dict[str, Any]) -> dict[str, Any]:
        events = repo.list_commitment_score_events(user_id)
        events_sorted = sorted(events, key=lambda e: getattr(e, "created_at", datetime.min), reverse=True)
        capped = events_sorted[:COMMITMENT_HISTORY_CAP]
        profile = repo.get_profile(user_id) if hasattr(repo, "get_profile") else None
        current_score = getattr(profile, "commitment_score", 50) if profile else 50
        return {
            "current_score": current_score,
            "events": [
                {
                    "delta": e.delta,
                    "kind": e.reason,
                    "at": e.created_at.isoformat(),
                    "debt_id": e.debt_id,
                }
                for e in capped
            ],
            "total_events": len(events_sorted),
        }

    return get_commitment_history


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def build_tool_specs(repo: Repository, user_id: str) -> dict[str, Any]:
    """Build the four tool functions; returned dict is `name -> callable`."""
    return {
        "list_debts": make_list_debts(repo, user_id),
        "get_debt": make_get_debt(repo, user_id),
        "get_dashboard_summary": make_get_dashboard_summary(repo, user_id),
        "get_commitment_history": make_get_commitment_history(repo, user_id),
    }


# Allowed status values for runtime validation in tools
ALLOWED_STATUSES = {str(s) for s in DebtStatus}

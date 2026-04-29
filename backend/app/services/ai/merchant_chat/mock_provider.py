from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.ai.merchant_chat.provider import (
    MerchantChatProvider,
    ProviderRequest,
    ProviderResponse,
)

UNAVAILABLE_EN = "I don't have that information."
UNAVAILABLE_AR = "لا أملك هذه المعلومات."

# Words that strongly suggest the caller is asking about another user.
_CROSS_USER_MARKERS = (
    "for user ",
    "user_id",
    "for someone else",
    "for another user",
    "list everyone",
    "all debts in the system",
    "anyone can",
    "every user",
    "system-wide",
    "global",
)


def _unavailable(locale: str) -> str:
    return UNAVAILABLE_AR if locale == "ar" else UNAVAILABLE_EN


def _tool(tools: dict[str, Any], name: str, args: dict[str, Any]) -> dict[str, Any]:
    fn = tools.get(name)
    if fn is None:
        return {}
    return fn(args)


def _format_amount(amount: str, currency: str) -> str:
    return f"{amount} {currency}"


def _looks_like_question_about_another_user(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _CROSS_USER_MARKERS)


def _has_keyword(text: str, en: tuple[str, ...], ar: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(k in lowered for k in en) or any(k in text for k in ar)


class MockMerchantChatProvider(MerchantChatProvider):
    """Deterministic provider for tests and offline demos.

    Picks one tool based on keyword heuristics, calls it, formats a natural-
    language reply. The orchestrator handles tool_trace + quota.
    """

    def chat(self, request: ProviderRequest) -> ProviderResponse:
        msg = request.user_message
        locale = request.locale
        tools = {t.name: t.fn for t in request.tools}
        invocations: list[dict[str, Any]] = []

        # Cross-user probe → refuse without invoking tools.
        if _looks_like_question_about_another_user(msg):
            return ProviderResponse(answer=_unavailable(locale), tool_invocations=invocations)

        # 1. Overdue exposure
        if _has_keyword(msg, ("overdue", "exposure"), ("متأخر", "تعرض")):
            result = _tool(tools, "get_dashboard_summary", {})
            invocations.append({"tool": "get_dashboard_summary", "outcome": "ok"})
            count = result.get("overdue_count", 0)
            total = result.get("total_receivable", "0")
            if count == 0:
                ans = "You have no overdue debts." if locale == "en" else "ليس لديك ديون متأخرة."
            else:
                ans = (
                    f"You have {count} overdue debts; total outstanding receivables: {total}."
                    if locale == "en"
                    else f"لديك {count} ديون متأخرة؛ إجمالي المستحقات: {total}."
                )
            return ProviderResponse(answer=ans, tool_invocations=invocations)

        # 2. Did <name> pay
        if _has_keyword(msg, ("did ", "paid", "pay me"), ("دفع", "سدد")):
            args: dict[str, Any] = {"role": "creditor", "status": ["paid"]}
            name_query = _extract_proper_name(msg)
            if name_query:
                args["counterparty_name_query"] = name_query
            result = _tool(tools, "list_debts", args)
            invocations.append(
                {"tool": "list_debts", "outcome": "ok" if result.get("total_count", 0) > 0 else "empty"}
            )
            rows = result.get("rows") or []
            if not rows:
                return ProviderResponse(answer=_unavailable(locale), tool_invocations=invocations)
            row = rows[0]
            paid_at = row.get("paid_at") or row.get("created_at", "")
            ans = (
                f"Yes — {row['debtor_name']} paid {_format_amount(row['amount'], row['currency'])} on {paid_at[:10]}."
                if locale == "en"
                else f"نعم، دفع {row['debtor_name']} مبلغ {_format_amount(row['amount'], row['currency'])} بتاريخ {paid_at[:10]}."
            )
            return ProviderResponse(answer=ans, tool_invocations=invocations)

        # 3. Who owes me / largest receivable / list receivables
        if _has_keyword(msg, ("owes me", "owes", "receivable", "list", "active"), ("يدين", "مستحقات", "ديوني")):
            result = _tool(
                tools,
                "list_debts",
                {"role": "creditor", "status": ["pending_confirmation", "active", "overdue"]},
            )
            invocations.append(
                {"tool": "list_debts", "outcome": "ok" if result.get("total_count", 0) > 0 else "empty"}
            )
            rows = result.get("rows") or []
            if not rows:
                return ProviderResponse(answer=_unavailable(locale), tool_invocations=invocations)
            top = rows[0]
            preface = ""
            if result.get("truncated"):
                preface = f"showing top {len(rows)} of {result['total_count']}. "
            ans = (
                f"{preface}{top['debtor_name']} owes you the most — {_format_amount(top['amount'], top['currency'])}."
                if locale == "en"
                else f"{preface}{top['debtor_name']} يدين لك بأكبر مبلغ — {_format_amount(top['amount'], top['currency'])}."
            )
            return ProviderResponse(answer=ans, tool_invocations=invocations)

        # 4. Oldest follow-up
        if _has_keyword(msg, ("oldest", "first"), ("الأقدم", "الأول")):
            result = _tool(
                tools,
                "list_debts",
                {"role": "creditor", "status": ["pending_confirmation", "active", "overdue"]},
            )
            invocations.append(
                {"tool": "list_debts", "outcome": "ok" if result.get("total_count", 0) > 0 else "empty"}
            )
            rows = result.get("rows") or []
            if not rows:
                return ProviderResponse(answer=_unavailable(locale), tool_invocations=invocations)
            # Oldest by created_at
            oldest = min(rows, key=lambda r: r["created_at"])
            ans = (
                f"The oldest is {oldest['debtor_name']} ({_format_amount(oldest['amount'], oldest['currency'])}), created {oldest['created_at'][:10]}."
                if locale == "en"
                else f"الأقدم هو {oldest['debtor_name']} ({_format_amount(oldest['amount'], oldest['currency'])}) بتاريخ {oldest['created_at'][:10]}."
            )
            return ProviderResponse(answer=ans, tool_invocations=invocations)

        # 5. Commitment indicator
        if _has_keyword(msg, ("commitment", "indicator", "score"), ("الالتزام", "مؤشر")):
            result = _tool(tools, "get_commitment_history", {})
            invocations.append({"tool": "get_commitment_history", "outcome": "ok"})
            score = result.get("current_score", 50)
            ans = (
                f"Your commitment indicator is {score}."
                if locale == "en"
                else f"مؤشر الالتزام لديك هو {score}."
            )
            return ProviderResponse(answer=ans, tool_invocations=invocations)

        # Fallback
        return ProviderResponse(answer=_unavailable(locale), tool_invocations=invocations)


_STOPWORDS = {
    "did",
    "does",
    "do",
    "pay",
    "paid",
    "me",
    "last",
    "this",
    "month",
    "week",
    "year",
    "the",
    "ago",
    "past",
    "to",
    "from",
    "for",
}


def _extract_proper_name(text: str) -> str | None:
    """Pick the first capitalised word that isn't a stopword."""
    for token in text.replace("?", " ").replace("'", " ").split():
        clean = token.strip(".,!?")
        if not clean:
            continue
        if clean.lower() in _STOPWORDS:
            continue
        if clean[0].isupper() and clean.isascii():
            return clean
    # Arabic — return first non-stopword token longer than 2 chars.
    for token in text.split():
        clean = token.strip(".,!?،")
        if not clean.isascii() and len(clean) > 2:
            return clean
    return None


# Re-exports for callers that just want a Decimal.
_ = Decimal  # keep import alive if linters flag it

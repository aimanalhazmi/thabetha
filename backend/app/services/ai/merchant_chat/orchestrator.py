from __future__ import annotations

import logging
from datetime import datetime
from time import perf_counter
from typing import Any

from app.core.config import get_settings
from app.repositories import Repository
from app.schemas.domain import MerchantChatOut, MerchantChatRequest, ToolTraceEntry
from app.services.ai.limits import MERCHANT_CHAT_FEATURE, record_ai_usage
from app.services.ai.merchant_chat.mock_provider import MockMerchantChatProvider
from app.services.ai.merchant_chat.provider import (
    MerchantChatProvider,
    MerchantChatProviderError,
    ProviderMessage,
    ProviderRequest,
    ToolSpec,
)
from app.services.ai.merchant_chat.system_prompt import SYSTEM_PROMPT
from app.services.ai.merchant_chat.time_resolver import detect_phrase, resolve, safe_zone
from app.services.ai.merchant_chat.tools import build_tool_specs, hash_user_id

logger = logging.getLogger(__name__)

HISTORY_TURN_CAP = 10


def _select_provider(name: str) -> MerchantChatProvider:
    if name == "anthropic":
        # Lazy import so the anthropic SDK isn't a hard dep for tests.
        from app.services.ai.merchant_chat.anthropic_provider import AnthropicMerchantChatProvider

        return AnthropicMerchantChatProvider()
    if name == "stub":
        # Backward-compat stub: same as mock for now.
        return MockMerchantChatProvider()
    return MockMerchantChatProvider()


def _build_context_block(now: datetime, tz_name: str, message: str) -> str:
    tz = safe_zone(tz_name)
    local_now = now.astimezone(tz)
    lines = [
        f"now (caller tz): {local_now.isoformat()}",
        f"caller timezone: {tz_name}",
    ]
    phrase = detect_phrase(message)
    if phrase:
        rng = resolve(now, tz, phrase)
        if rng is not None:
            lines.append(f'phrase "{phrase}" → [{rng.start.isoformat()}, {rng.end.isoformat()}) ({rng.human})')
    return "Current context:\n" + "\n".join(lines)


def _trim_history(history: list, cap: int = HISTORY_TURN_CAP):
    return list(history)[-cap:]


def run_merchant_chat(
    repo: Repository,
    user,
    payload: MerchantChatRequest,
) -> MerchantChatOut:
    """Drive the merchant-chat tool-use loop, then record quota on success."""
    settings = get_settings()
    user_hash = hash_user_id(user.id)
    history = _trim_history(payload.history)
    logger.info(
        "merchant_chat.start user=H(%s) lang=%s history_len=%d",
        user_hash,
        payload.locale,
        len(history),
    )

    tool_callables = build_tool_specs(repo, user.id)
    tools = [
        ToolSpec(name=name, description=name, input_schema={}, fn=fn)
        for name, fn in tool_callables.items()
    ]

    provider = _select_provider(settings.merchant_chat_provider)
    context_block = _build_context_block(datetime.now(), payload.timezone, payload.message)
    request = ProviderRequest(
        system_prompt=SYSTEM_PROMPT,
        history=[ProviderMessage(role=t.role, content=t.content) for t in history],
        user_message=payload.message,
        tools=tools,
        locale=payload.locale,
        context_block=context_block,
    )

    started = perf_counter()
    try:
        response = provider.chat(request)
    except MerchantChatProviderError:
        # Quota is NOT consumed on provider failures.
        raise

    total_ms = int((perf_counter() - started) * 1000)
    trace_entries: list[ToolTraceEntry] = []
    for inv in response.tool_invocations:
        trace_entries.append(
            ToolTraceEntry(tool=inv.get("tool", ""), outcome=inv.get("outcome", "ok"), duration_ms=inv.get("duration_ms", 0))
        )
        logger.info(
            "merchant_chat.tool user=H(%s) tool=%s outcome=%s",
            user_hash,
            inv.get("tool"),
            inv.get("outcome"),
        )

    record_ai_usage(repo, user.id, MERCHANT_CHAT_FEATURE)
    facts: dict[str, Any] = repo.merchant_facts(user.id)

    logger.info(
        "merchant_chat.end user=H(%s) tool_count=%d total_ms=%d answer_lang=%s",
        user_hash,
        len(trace_entries),
        total_ms,
        payload.locale,
    )

    show_trace = settings.app_env.lower() != "production"
    return MerchantChatOut(
        answer=response.answer,
        facts=facts,
        tool_trace=trace_entries if show_trace else None,
    )


__all__ = ["run_merchant_chat", "MerchantChatProviderError"]

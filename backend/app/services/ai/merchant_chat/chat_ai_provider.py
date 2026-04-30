from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.ai.merchant_chat.provider import (
    MerchantChatProvider,
    MerchantChatProviderError,
    ProviderRequest,
    ProviderResponse,
)

logger = logging.getLogger(__name__)

_TOOL_INPUT_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_debts": {
        "type": "object",
        "properties": {
            "role": {"type": "string", "enum": ["creditor", "debtor", "any"]},
            "status": {"type": "array", "items": {"type": "string"}},
            "counterparty_name_query": {"type": "string"},
            "from_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
            "to_date": {"type": "string", "description": "ISO date YYYY-MM-DD (exclusive)"},
            "min_amount": {"type": "string"},
            "max_amount": {"type": "string"},
        },
    },
    "get_debt": {
        "type": "object",
        "properties": {"debt_id": {"type": "string"}},
        "required": ["debt_id"],
    },
    "get_dashboard_summary": {"type": "object", "properties": {}},
    "get_commitment_history": {"type": "object", "properties": {}},
}

_TOOL_DESCRIPTIONS: dict[str, str] = {
    "list_debts": "List the caller's debts with optional filters; returns up to 20 rows plus exact total_count and total_sum.",
    "get_debt": "Fetch a single debt the caller is a party to. Returns null row if the caller is not authorised.",
    "get_dashboard_summary": "Get the caller's dashboard summary: outstanding/overdue counts and totals, alerts.",
    "get_commitment_history": "Get the caller's commitment indicator history.",
}


class ChatAIMerchantChatProvider(MerchantChatProvider):
    """Merchant-chat provider backed by an OpenAI-compatible /chat/completions endpoint
    (e.g. https://chat-ai.academiccloud.de/v1). Drives a tool-use loop using the
    standard OpenAI `tools` / `tool_calls` shape."""

    def chat(self, request: ProviderRequest) -> ProviderResponse:
        settings = get_settings()
        api_key = settings.chat_ai_api_key or settings.openai_api_key
        if not api_key:
            raise MerchantChatProviderError("CHAT_AI_API_KEY is not configured")

        url = f"{settings.chat_ai_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        tool_defs = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": _TOOL_DESCRIPTIONS.get(t.name, t.description),
                    "parameters": _TOOL_INPUT_SCHEMAS.get(t.name, t.input_schema or {"type": "object", "properties": {}}),
                },
            }
            for t in request.tools
        ]
        tool_fns = {t.name: t.fn for t in request.tools}

        messages: list[dict[str, Any]] = [{"role": "system", "content": request.system_prompt}]
        for h in request.history:
            messages.append({"role": h.role, "content": h.content})
        messages.append({"role": "user", "content": f"{request.context_block}\n\n{request.user_message}"})

        invocations: list[dict[str, Any]] = []

        with httpx.Client(timeout=90) as client:
            for _hop in range(request.max_tool_hops):
                body = {
                    "model": settings.chat_ai_merchant_chat_model,
                    "messages": messages,
                    "tools": tool_defs,
                    "tool_choice": "auto",
                    "temperature": 0.2,
                }
                try:
                    response = client.post(url, headers=headers, json=body)
                    response.raise_for_status()
                    data = response.json()
                except httpx.HTTPStatusError as exc:
                    snippet = exc.response.text[:500] if exc.response is not None else ""
                    logger.warning("merchant_chat upstream %s returned %s: %s", url, exc.response.status_code, snippet)
                    raise MerchantChatProviderError(f"chat-ai HTTP {exc.response.status_code}") from exc
                except Exception as exc:
                    logger.warning("merchant_chat upstream %s failed: %r", url, exc)
                    raise MerchantChatProviderError("chat-ai request failed") from exc

                try:
                    message = data["choices"][0]["message"]
                except (KeyError, IndexError, TypeError) as exc:
                    logger.warning("merchant_chat upstream returned unexpected shape: %s", str(data)[:500])
                    raise MerchantChatProviderError("chat-ai response missing choices") from exc

                tool_calls = message.get("tool_calls") or []
                if tool_calls:
                    # Append the assistant's tool-call request, then run each tool and append results.
                    messages.append(
                        {
                            "role": "assistant",
                            "content": message.get("content") or "",
                            "tool_calls": tool_calls,
                        }
                    )
                    for call in tool_calls:
                        call_id = call.get("id") or ""
                        fn_block = call.get("function") or {}
                        name = fn_block.get("name") or ""
                        raw_args = fn_block.get("arguments") or "{}"
                        try:
                            tool_input = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                        except json.JSONDecodeError:
                            tool_input = {}
                        fn = tool_fns.get(name)
                        if fn is None:
                            invocations.append({"tool": name, "outcome": "error"})
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": call_id,
                                    "content": json.dumps({"error": "unknown_tool"}),
                                }
                            )
                            continue
                        try:
                            result = fn(tool_input)
                            outcome = "empty" if not result else "ok"
                            invocations.append({"tool": name, "outcome": outcome})
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": call_id,
                                    "content": json.dumps(result, default=str),
                                }
                            )
                        except Exception as exc:
                            invocations.append({"tool": name, "outcome": "error"})
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": call_id,
                                    "content": json.dumps({"error": str(exc)}),
                                }
                            )
                    continue

                answer = (message.get("content") or "").strip()
                return ProviderResponse(answer=answer, tool_invocations=invocations)

        return ProviderResponse(
            answer="I don't have that information.",
            tool_invocations=invocations,
        )

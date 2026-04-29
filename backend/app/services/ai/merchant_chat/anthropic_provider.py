from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings
from app.services.ai.merchant_chat.provider import (
    MerchantChatProvider,
    MerchantChatProviderError,
    ProviderRequest,
    ProviderResponse,
)

logger = logging.getLogger(__name__)

_TOOL_INPUT_SCHEMAS = {
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

_TOOL_DESCRIPTIONS = {
    "list_debts": "List the caller's debts with optional filters; returns up to 20 rows plus exact total_count and total_sum.",
    "get_debt": "Fetch a single debt the caller is a party to. Returns null row if the caller is not authorised.",
    "get_dashboard_summary": "Get the caller's dashboard summary: outstanding/overdue counts and totals, alerts.",
    "get_commitment_history": "Get the caller's commitment indicator history.",
}


class AnthropicMerchantChatProvider(MerchantChatProvider):
    def chat(self, request: ProviderRequest) -> ProviderResponse:  # pragma: no cover (network)
        try:
            import anthropic  # type: ignore[import-not-found]
        except ImportError as exc:
            raise MerchantChatProviderError("anthropic SDK not installed") from exc

        settings = get_settings()
        if not settings.anthropic_api_key:
            raise MerchantChatProviderError("ANTHROPIC_API_KEY is not configured")

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        tool_defs = [
            {
                "name": t.name,
                "description": _TOOL_DESCRIPTIONS.get(t.name, t.description),
                "input_schema": _TOOL_INPUT_SCHEMAS.get(t.name, t.input_schema),
            }
            for t in request.tools
        ]
        tool_fns = {t.name: t.fn for t in request.tools}

        messages: list[dict[str, Any]] = []
        for h in request.history:
            messages.append({"role": h.role, "content": h.content})
        messages.append({"role": "user", "content": f"{request.context_block}\n\n{request.user_message}"})

        invocations: list[dict[str, Any]] = []
        for _hop in range(request.max_tool_hops):
            try:
                resp = client.messages.create(
                    model=settings.merchant_chat_model,
                    max_tokens=1024,
                    temperature=0.2,
                    system=request.system_prompt,
                    tools=tool_defs,
                    messages=messages,
                )
            except Exception as exc:
                raise MerchantChatProviderError(str(exc)) from exc

            stop_reason = getattr(resp, "stop_reason", None)
            content_blocks = list(getattr(resp, "content", []))

            if stop_reason == "tool_use":
                tool_results = []
                assistant_blocks: list[dict[str, Any]] = []
                for block in content_blocks:
                    block_type = getattr(block, "type", None)
                    if block_type == "tool_use":
                        name = block.name
                        tool_input = block.input or {}
                        fn = tool_fns.get(name)
                        if fn is None:
                            invocations.append({"tool": name, "outcome": "error"})
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": json.dumps({"error": "unknown_tool"}),
                                    "is_error": True,
                                }
                            )
                            continue
                        try:
                            result = fn(tool_input)
                            outcome = "empty" if not result else "ok"
                            invocations.append({"tool": name, "outcome": outcome})
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": json.dumps(result, default=str),
                                }
                            )
                        except Exception as exc:
                            invocations.append({"tool": name, "outcome": "error"})
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": json.dumps({"error": str(exc)}),
                                    "is_error": True,
                                }
                            )
                        assistant_blocks.append(
                            {"type": "tool_use", "id": block.id, "name": name, "input": tool_input}
                        )
                    elif block_type == "text":
                        assistant_blocks.append({"type": "text", "text": block.text})

                messages.append({"role": "assistant", "content": assistant_blocks})
                messages.append({"role": "user", "content": tool_results})
                continue

            # Final answer
            answer_text = ""
            for block in content_blocks:
                if getattr(block, "type", None) == "text":
                    answer_text += block.text
            return ProviderResponse(answer=answer_text.strip(), tool_invocations=invocations)

        # Exhausted hops without final answer.
        return ProviderResponse(
            answer="I don't have that information.",
            tool_invocations=invocations,
        )

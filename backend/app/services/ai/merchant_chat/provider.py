from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class ProviderMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class ProviderRequest:
    system_prompt: str
    history: list[ProviderMessage]
    user_message: str
    tools: list[ToolSpec]
    locale: str
    context_block: str
    max_tool_hops: int = 4


@dataclass
class ProviderResponse:
    answer: str
    tool_invocations: list[dict[str, Any]] = field(default_factory=list)


class MerchantChatProviderError(Exception):
    """Raised when the upstream LLM provider is unavailable or misbehaves."""


class MerchantChatProvider(ABC):
    @abstractmethod
    def chat(self, request: ProviderRequest) -> ProviderResponse: ...

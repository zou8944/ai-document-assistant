"""Base backend for LLM tool calling."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from chat.agent.cancellation import CancellationToken


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0


@dataclass
class AssistantTurn:
    raw_content: list[dict] = field(default_factory=list)
    stop_reason: str = ""
    tool_uses: list[ToolUseBlock] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class ToolCallingBackend(ABC):
    @abstractmethod
    async def generate_with_tools(
        self,
        *,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
        temperature: float,
        cancellation: CancellationToken,
        on_text_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> AssistantTurn:
        """Call LLM with tools. Stream text deltas via on_text_delta.

        Must handle cancellation gracefully: if token.cancelled() becomes
        true during streaming, abort and raise asyncio.CancelledError after
        cleaning up the stream context.
        """
        ...

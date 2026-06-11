"""Base tool abstraction for the agent."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from chat.agent.cancellation import CancellationToken
from chat.models import SSEEvent


@dataclass
class ToolResult:
    """Result of a tool execution."""

    content: str
    structured: dict | None = None
    is_error: bool = False


@dataclass
class ToolContext:
    """Context passed to every tool invocation."""

    chat_id: str
    collection_ids: list[str]
    cancellation: CancellationToken
    emit: Callable[[SSEEvent], Awaitable[None]]
    deps: "AgentDeps"
    # Set of document IDs that have been accessed during this agent run.
    # Maintained by AgentRuntime — tools must treat this as read-only.
    visited_doc_ids: set[str] = field(default_factory=set)
    # When set, tools must restrict results to these document IDs only.
    document_ids: list[str] | None = None


@dataclass
class AgentDeps:
    """Injectable dependencies for tools."""

    collection_repo: object
    document_repo: object
    chunk_index: object | None = None
    chroma_client: object | None = None
    fast_llm: object | None = None


class Tool(ABC):
    """Abstract base for an agent tool."""

    name: str = ""
    description: str = ""
    input_schema: dict = {}
    preserve_in_compact: bool = False

    @abstractmethod
    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        """Execute the tool. Must not raise; errors go into ToolResult.is_error."""
        ...

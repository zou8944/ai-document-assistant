"""Agent module for tool-use based RAG chat."""

from chat.agent.cancellation import CancellationToken
from chat.agent.compaction import auto_compact, estimate_tokens, micro_compact
from chat.agent.registry import ToolRegistry
from chat.agent.runtime import AgentConfig, AgentRuntime
from chat.agent.tools.base import AgentDeps, Tool, ToolContext, ToolResult
from chat.agent.tools.collections import (
    GetCollectionOverviewTool,
    ListCollectionsTool,
)
from chat.agent.tools.documents import GetDocumentSummaryTool, GetDocumentTool
from chat.agent.tools.search import GrepDocumentsTool, SearchDocumentsTool
from chat.agent.trace import TranscriptWriter

__all__ = [
    "CancellationToken",
    "ToolRegistry",
    "Tool",
    "ToolContext",
    "ToolResult",
    "AgentDeps",
    "ListCollectionsTool",
    "GetCollectionOverviewTool",
    "SearchDocumentsTool",
    "GrepDocumentsTool",
    "GetDocumentTool",
    "GetDocumentSummaryTool",
]


def build_default_registry(deps: AgentDeps) -> ToolRegistry:
    """Build a registry with all default tools."""
    registry = ToolRegistry()
    registry.register(ListCollectionsTool())
    registry.register(GetCollectionOverviewTool())
    registry.register(SearchDocumentsTool())
    registry.register(GrepDocumentsTool())
    registry.register(GetDocumentTool())
    registry.register(GetDocumentSummaryTool())
    return registry

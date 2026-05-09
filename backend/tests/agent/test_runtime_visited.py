"""Runtime tests for visited_doc_ids accumulation and SOURCES emission."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from chat.agent.cancellation import CancellationToken
from chat.agent.llm.base import AssistantTurn, ToolCallingBackend, ToolUseBlock, Usage
from chat.agent.registry import ToolRegistry
from chat.agent.runtime import AgentConfig, AgentRuntime
from chat.agent.tools.base import AgentDeps, Tool, ToolContext, ToolResult
from chat.agent.tools.citations import CiteSourcesTool
from chat.models import SSEEventType


class FakeSearchTool(Tool):
    name = "search_documents"
    description = "fake"
    input_schema = {"type": "object", "properties": {}}
    preserve_in_compact = False

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        return ToolResult(
            content="found",
            structured={"doc_ids": ["d1", "d2"]},
        )


class FakeGetDocumentTool(Tool):
    name = "get_document"
    description = "fake"
    input_schema = {"type": "object", "properties": {}}
    preserve_in_compact = True

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        return ToolResult(content="document body")


def _make_backend(*turns):
    mock = MagicMock(spec=ToolCallingBackend)
    turn_iter = iter(turns)

    async def mock_generate(*, on_text_delta=None, **kwargs):
        return next(turn_iter)

    mock.generate_with_tools = AsyncMock(side_effect=mock_generate)
    return mock


@pytest.fixture
def patched_compaction(monkeypatch):
    import chat.agent.runtime as runtime_mod

    monkeypatch.setattr(runtime_mod, "micro_compact", lambda *a, **k: None)
    monkeypatch.setattr(runtime_mod, "auto_compact", lambda *a, **k: a[0])


class TestVisitedDocIds:
    async def test_search_then_cite_emits_sources(self, patched_compaction):
        document_repo = MagicMock()
        document_repo.get_summary_only.return_value = {
            "id": "d1",
            "name": "Doc One",
            "summary": "summary one",
            "keywords": None,
            "category": None,
            "total_tokens": 0,
        }
        deps = AgentDeps(
            collection_repo=MagicMock(),
            document_repo=document_repo,
        )

        registry = ToolRegistry()
        registry.register(FakeSearchTool())
        registry.register(CiteSourcesTool())

        backend = _make_backend(
            AssistantTurn(
                raw_content=[
                    {
                        "type": "tool_use",
                        "id": "tu-1",
                        "name": "search_documents",
                        "input": {"keywords": ["x"]},
                    }
                ],
                stop_reason="tool_use",
                tool_uses=[
                    ToolUseBlock(id="tu-1", name="search_documents", input={"keywords": ["x"]})
                ],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
            AssistantTurn(
                raw_content=[
                    {
                        "type": "tool_use",
                        "id": "tu-2",
                        "name": "cite_sources",
                        "input": {"document_ids": ["d1"]},
                    }
                ],
                stop_reason="tool_use",
                tool_uses=[
                    ToolUseBlock(
                        id="tu-2",
                        name="cite_sources",
                        input={"document_ids": ["d1"]},
                    )
                ],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
            AssistantTurn(
                raw_content=[{"type": "text", "text": "final answer"}],
                stop_reason="end_turn",
                tool_uses=[],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
        )

        runtime = AgentRuntime(backend, registry, AgentConfig(max_iterations=5))

        events = []
        async for event in runtime.run(
            chat_id="c1",
            query="q",
            history=[],
            collection_ids=["col-1"],
            cancellation=CancellationToken(),
            deps=deps,
            emit=AsyncMock(),
            transcript=None,
        ):
            events.append(event)

        sources_events = [e for e in events if e.type == SSEEventType.SOURCES]
        assert len(sources_events) == 1
        docs = sources_events[0].data["documents"]
        assert len(docs) == 1
        assert docs[0]["document_id"] == "d1"
        assert docs[0]["document_name"] == "Doc One"

    async def test_cite_unvisited_id_rejected(self, patched_compaction):
        document_repo = MagicMock()
        deps = AgentDeps(
            collection_repo=MagicMock(),
            document_repo=document_repo,
        )

        registry = ToolRegistry()
        registry.register(CiteSourcesTool())

        backend = _make_backend(
            AssistantTurn(
                raw_content=[
                    {
                        "type": "tool_use",
                        "id": "tu-1",
                        "name": "cite_sources",
                        "input": {"document_ids": ["d-never-seen"]},
                    }
                ],
                stop_reason="tool_use",
                tool_uses=[
                    ToolUseBlock(
                        id="tu-1",
                        name="cite_sources",
                        input={"document_ids": ["d-never-seen"]},
                    )
                ],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
            AssistantTurn(
                raw_content=[{"type": "text", "text": "done"}],
                stop_reason="end_turn",
                tool_uses=[],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
        )

        runtime = AgentRuntime(backend, registry, AgentConfig(max_iterations=5))

        events = []
        async for event in runtime.run(
            chat_id="c1",
            query="q",
            history=[],
            collection_ids=["col-1"],
            cancellation=CancellationToken(),
            deps=deps,
            emit=AsyncMock(),
            transcript=None,
        ):
            events.append(event)

        sources_events = [e for e in events if e.type == SSEEventType.SOURCES]
        assert len(sources_events) == 1
        assert sources_events[0].data["documents"] == []
        document_repo.get_summary_only.assert_not_called()

    async def test_get_document_marks_visited(self, patched_compaction):
        document_repo = MagicMock()
        document_repo.get_summary_only.return_value = {
            "id": "abc",
            "name": "ABC",
            "summary": "",
            "keywords": None,
            "category": None,
            "total_tokens": 0,
        }
        deps = AgentDeps(
            collection_repo=MagicMock(),
            document_repo=document_repo,
        )

        registry = ToolRegistry()
        registry.register(FakeGetDocumentTool())
        registry.register(CiteSourcesTool())

        backend = _make_backend(
            AssistantTurn(
                raw_content=[
                    {
                        "type": "tool_use",
                        "id": "tu-1",
                        "name": "get_document",
                        "input": {"document_id": "doc_abc"},
                    }
                ],
                stop_reason="tool_use",
                tool_uses=[
                    ToolUseBlock(
                        id="tu-1",
                        name="get_document",
                        input={"document_id": "doc_abc"},
                    )
                ],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
            AssistantTurn(
                raw_content=[
                    {
                        "type": "tool_use",
                        "id": "tu-2",
                        "name": "cite_sources",
                        "input": {"document_ids": ["abc"]},
                    }
                ],
                stop_reason="tool_use",
                tool_uses=[
                    ToolUseBlock(
                        id="tu-2",
                        name="cite_sources",
                        input={"document_ids": ["abc"]},
                    )
                ],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
            AssistantTurn(
                raw_content=[{"type": "text", "text": "done"}],
                stop_reason="end_turn",
                tool_uses=[],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
        )

        runtime = AgentRuntime(backend, registry, AgentConfig(max_iterations=5))

        events = []
        async for event in runtime.run(
            chat_id="c1",
            query="q",
            history=[],
            collection_ids=["col-1"],
            cancellation=CancellationToken(),
            deps=deps,
            emit=AsyncMock(),
            transcript=None,
        ):
            events.append(event)

        sources_events = [e for e in events if e.type == SSEEventType.SOURCES]
        assert len(sources_events) == 1
        docs = sources_events[0].data["documents"]
        assert len(docs) == 1
        assert docs[0]["document_id"] == "abc"

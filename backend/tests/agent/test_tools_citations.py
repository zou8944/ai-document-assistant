"""Tests for chat.agent.tools.citations."""

from unittest.mock import AsyncMock, MagicMock

from chat.agent.cancellation import CancellationToken
from chat.agent.tools.base import AgentDeps, ToolContext
from chat.agent.tools.citations import CiteSourcesTool


def _make_ctx(visited=None, document_repo=None):
    return ToolContext(
        chat_id="test",
        collection_ids=["c1"],
        cancellation=CancellationToken(),
        emit=AsyncMock(),
        deps=AgentDeps(
            collection_repo=MagicMock(),
            document_repo=document_repo or MagicMock(),
        ),
        visited_doc_ids=visited if visited is not None else set(),
    )


class TestCiteSourcesTool:
    async def test_empty_document_ids(self):
        ctx = _make_ctx()
        tool = CiteSourcesTool()
        result = await tool.run(ctx, document_ids=[])

        assert not result.is_error
        assert result.structured == {"sources": []}
        assert "Recorded 0 citation(s)" in result.content

    async def test_valid_document_id(self):
        repo = MagicMock()
        repo.get_summary_only.return_value = {
            "id": "d1",
            "name": "Intro",
            "uri": "https://example.com/d1",
            "summary": "Getting started guide",
            "keywords": '["a"]',
            "category": "guide",
            "total_tokens": 100,
        }
        ctx = _make_ctx(visited={"d1"}, document_repo=repo)
        tool = CiteSourcesTool()
        result = await tool.run(ctx, document_ids=["d1"])

        assert not result.is_error
        assert result.structured is not None
        sources = result.structured["sources"]
        assert len(sources) == 1
        assert sources[0]["document_id"] == "d1"
        assert sources[0]["document_name"] == "Intro"
        assert sources[0]["document_uri"] == "https://example.com/d1"
        assert sources[0]["chunk_index"] == 0
        assert sources[0]["content_preview"] == "Getting started guide"
        assert sources[0]["relevance_score"] == 1.0
        assert "Recorded 1 citation(s)" in result.content

    async def test_unvisited_document_id_rejected(self):
        repo = MagicMock()
        ctx = _make_ctx(visited=set(), document_repo=repo)
        tool = CiteSourcesTool()
        result = await tool.run(ctx, document_ids=["d-unknown"])

        assert not result.is_error
        assert result.structured == {"sources": []}
        assert "Rejected 1 id(s)" in result.content
        assert "d-unknown" in result.content
        # rejected text must be a clean join, not a Python list repr
        assert "['d-unknown']" not in result.content
        repo.get_summary_only.assert_not_called()

    async def test_mixed_valid_and_invalid(self):
        repo = MagicMock()
        repo.get_summary_only.return_value = {
            "id": "d1",
            "name": "Doc 1",
            "uri": "https://example.com/d1",
            "summary": "summary",
            "keywords": None,
            "category": None,
            "total_tokens": 0,
        }
        ctx = _make_ctx(visited={"d1"}, document_repo=repo)
        tool = CiteSourcesTool()
        result = await tool.run(ctx, document_ids=["d1", "d-bad"])

        assert not result.is_error
        sources = result.structured["sources"]
        assert len(sources) == 1
        assert sources[0]["document_id"] == "d1"
        assert "Recorded 1 citation(s)" in result.content
        assert "Rejected 1 id(s)" in result.content
        assert "d-bad" in result.content
        # rejected text must not include list-repr brackets
        assert "['d-bad']" not in result.content

    async def test_repo_returns_none_marks_rejected(self):
        repo = MagicMock()
        repo.get_summary_only.return_value = None
        ctx = _make_ctx(visited={"d1"}, document_repo=repo)
        tool = CiteSourcesTool()
        result = await tool.run(ctx, document_ids=["d1"])

        assert not result.is_error
        assert result.structured == {"sources": []}
        assert "Rejected 1 id(s)" in result.content

    async def test_doc_prefix_stripped(self):
        repo = MagicMock()
        repo.get_summary_only.return_value = {
            "id": "abc",
            "name": "X",
            "summary": "",
            "keywords": None,
            "category": None,
            "total_tokens": 0,
        }
        ctx = _make_ctx(visited={"abc"}, document_repo=repo)
        tool = CiteSourcesTool()
        result = await tool.run(ctx, document_ids=["doc_abc"])

        assert not result.is_error
        sources = result.structured["sources"]
        assert len(sources) == 1
        assert sources[0]["document_id"] == "abc"

    async def test_long_summary_truncated(self):
        long_summary = "x" * 500
        repo = MagicMock()
        repo.get_summary_only.return_value = {
            "id": "d1",
            "name": "Long",
            "summary": long_summary,
            "keywords": None,
            "category": None,
            "total_tokens": 0,
        }
        ctx = _make_ctx(visited={"d1"}, document_repo=repo)
        tool = CiteSourcesTool()
        result = await tool.run(ctx, document_ids=["d1"])

        assert not result.is_error
        sources = result.structured["sources"]
        assert len(sources[0]["content_preview"]) == 300

    async def test_repo_exception_marks_rejected_and_continues(self):
        """F3: per-id error tolerance — one repo failure must not abort the tool."""
        repo = MagicMock()

        def _side_effect(doc_id: str):
            if doc_id == "d2":
                raise RuntimeError("transient db error")
            return {
                "id": doc_id,
                "name": f"Doc {doc_id}",
                "uri": f"https://example.com/{doc_id}",
                "summary": f"summary-{doc_id}",
                "keywords": None,
                "category": None,
                "total_tokens": 0,
            }

        repo.get_summary_only.side_effect = _side_effect
        ctx = _make_ctx(visited={"d1", "d2", "d3"}, document_repo=repo)
        tool = CiteSourcesTool()
        result = await tool.run(ctx, document_ids=["d1", "d2", "d3"])

        # The tool itself does NOT fail — partial results are returned
        assert not result.is_error
        sources = result.structured["sources"]
        assert len(sources) == 2
        assert {s["document_id"] for s in sources} == {"d1", "d3"}
        # d2 is reported as rejected
        assert "Recorded 2 citation(s)" in result.content
        assert "Rejected 1 id(s)" in result.content
        assert "d2" in result.content
        # All three were attempted
        assert repo.get_summary_only.call_count == 3

"""Tests for chat.agent.tools.search."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from chat.agent.cancellation import CancellationToken
from chat.agent.tools.base import AgentDeps, ToolContext
from chat.agent.tools.search import GrepDocumentsTool, SearchDocumentsTool


def _make_ctx(collection_ids=None, document_repo=None):
    return ToolContext(
        chat_id="test",
        collection_ids=collection_ids if collection_ids is not None else ["c1"],
        cancellation=CancellationToken(),
        emit=AsyncMock(),
        deps=AgentDeps(
            collection_repo=MagicMock(),
            document_repo=document_repo or MagicMock(),
        ),
    )


class TestSearchDocumentsTool:
    async def test_success_returns_markdown(self):
        mock_doc = MagicMock()
        mock_doc.id = "d1"
        mock_doc.name = "Intro"
        mock_doc.category = "guide"
        mock_doc.summary = "Getting started"
        mock_doc.keywords = "[quickstart]"

        repo = MagicMock()
        repo.search_by_keywords.return_value = [mock_doc]

        ctx = _make_ctx(document_repo=repo)
        tool = SearchDocumentsTool()
        result = await tool.run(ctx, keywords=["intro"])

        assert not result.is_error
        assert "Found 1 documents" in result.content
        assert "[doc:d1]" in result.content
        repo.search_by_keywords.assert_called_once_with(
            keywords=["intro"],
            collection_ids=None,
            category=None,
            limit=15,
        )

    async def test_empty_results(self):
        repo = MagicMock()
        repo.search_by_keywords.return_value = []

        ctx = _make_ctx(document_repo=repo)
        tool = SearchDocumentsTool()
        result = await tool.run(ctx, keywords=["xyz"])

        assert not result.is_error
        assert "No documents matched" in result.content

    async def test_repo_exception_returns_error(self):
        repo = MagicMock()
        repo.search_by_keywords.side_effect = RuntimeError("db down")

        ctx = _make_ctx(document_repo=repo)
        tool = SearchDocumentsTool()
        result = await tool.run(ctx, keywords=["intro"])

        assert result.is_error
        assert "db down" in result.content


class TestGrepDocumentsTool:
    async def test_success_returns_markdown(self):
        mock_doc = MagicMock()
        mock_doc.id = "d1"
        mock_doc.name = "config.md"
        mock_doc.category = None
        mock_doc.content = "host = localhost\nport = 8080\n"

        repo = MagicMock()
        repo.get_by_collection.return_value = [mock_doc]

        ctx = _make_ctx(collection_ids=["c1"], document_repo=repo)
        tool = GrepDocumentsTool()
        result = await tool.run(ctx, pattern="port", collection_ids=["c1"])

        assert not result.is_error
        assert 'Found 1 matches for pattern "port"' in result.content
        assert "port = 8080" in result.content

    async def test_empty_results(self):
        mock_doc = MagicMock()
        mock_doc.id = "d1"
        mock_doc.name = "empty.md"
        mock_doc.content = ""

        repo = MagicMock()
        repo.get_by_collection.return_value = [mock_doc]

        ctx = _make_ctx(collection_ids=["c1"], document_repo=repo)
        tool = GrepDocumentsTool()
        result = await tool.run(ctx, pattern="zzz")

        assert not result.is_error
        assert "No matches" in result.content

    async def test_repo_exception_returns_error(self):
        repo = MagicMock()
        repo.get_by_collection.side_effect = RuntimeError("db down")

        ctx = _make_ctx(collection_ids=["c1"], document_repo=repo)
        tool = GrepDocumentsTool()
        result = await tool.run(ctx, pattern="port", collection_ids=["c1"])

        assert result.is_error
        assert "db down" in result.content

    async def test_max_matches_truncation(self):
        lines = [f"line {i}" for i in range(30)]
        mock_doc = MagicMock()
        mock_doc.id = "d1"
        mock_doc.name = "big.md"
        mock_doc.content = "\n".join(lines)

        repo = MagicMock()
        repo.get_by_collection.return_value = [mock_doc]

        ctx = _make_ctx(collection_ids=["c1"], document_repo=repo)
        tool = GrepDocumentsTool()
        result = await tool.run(ctx, pattern="line", max_matches=5, collection_ids=["c1"])

        assert not result.is_error
        assert "Results truncated to 5 matches" in result.content

    async def test_invalid_regex(self):
        repo = MagicMock()
        repo.get_by_collection.return_value = []

        ctx = _make_ctx(collection_ids=["c1"], document_repo=repo)
        tool = GrepDocumentsTool()
        result = await tool.run(ctx, pattern="[invalid", regex=True)

        assert result.is_error
        assert "invalid regex" in result.content

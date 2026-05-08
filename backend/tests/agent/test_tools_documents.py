"""Tests for chat.agent.tools.documents."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from chat.agent.cancellation import CancellationToken
from chat.agent.tools.base import AgentDeps, ToolContext
from chat.agent.tools.documents import GetDocumentSummaryTool, GetDocumentTool


def _make_ctx(document_repo=None):
    return ToolContext(
        chat_id="test",
        collection_ids=["c1"],
        cancellation=CancellationToken(),
        emit=AsyncMock(),
        deps=AgentDeps(
            collection_repo=MagicMock(),
            document_repo=document_repo or MagicMock(),
        ),
    )


class TestGetDocumentTool:
    async def test_success_returns_markdown(self):
        mock_doc = MagicMock()
        mock_doc.id = "d1"
        mock_doc.name = "readme.md"
        mock_doc.content = "Hello world"

        repo = MagicMock()
        repo.get_by_id.return_value = mock_doc

        ctx = _make_ctx(document_repo=repo)
        tool = GetDocumentTool()
        result = await tool.run(ctx, document_id="d1")

        assert not result.is_error
        assert 'Document d1 "readme.md"' in result.content
        assert "Hello world" in result.content
        repo.get_by_id.assert_called_once_with("d1")

    async def test_pagination_boundary(self):
        mock_doc = MagicMock()
        mock_doc.id = "d1"
        mock_doc.name = "big.md"
        mock_doc.content = "A" * 9000

        repo = MagicMock()
        repo.get_by_id.return_value = mock_doc

        ctx = _make_ctx(document_repo=repo)
        tool = GetDocumentTool()
        result = await tool.run(ctx, document_id="d1", page=3, page_size_tokens=500)

        assert not result.is_error
        assert "page 3/5" in result.content

    async def test_empty_content(self):
        mock_doc = MagicMock()
        mock_doc.id = "d1"
        mock_doc.name = "empty.md"
        mock_doc.content = ""

        repo = MagicMock()
        repo.get_by_id.return_value = mock_doc

        ctx = _make_ctx(document_repo=repo)
        tool = GetDocumentTool()
        result = await tool.run(ctx, document_id="d1")

        assert result.is_error
        assert "has no content" in result.content

    async def test_document_not_found(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None

        ctx = _make_ctx(document_repo=repo)
        tool = GetDocumentTool()
        result = await tool.run(ctx, document_id="missing")

        assert result.is_error
        assert "not found" in result.content

    async def test_repo_exception_returns_error(self):
        repo = MagicMock()
        repo.get_by_id.side_effect = RuntimeError("db down")

        ctx = _make_ctx(document_repo=repo)
        tool = GetDocumentTool()
        result = await tool.run(ctx, document_id="d1")

        assert result.is_error
        assert "db down" in result.content

    async def test_no_document_id(self):
        ctx = _make_ctx()
        tool = GetDocumentTool()
        result = await tool.run(ctx)

        assert result.is_error
        assert "document_id is required" in result.content


class TestGetDocumentSummaryTool:
    async def test_success_returns_markdown(self):
        repo = MagicMock()
        repo.get_summary_only.return_value = {
            "id": "d1",
            "name": "readme",
            "summary": "Overview",
            "keywords": "[intro]",
            "category": "guide",
            "total_tokens": 120,
        }

        ctx = _make_ctx(document_repo=repo)
        tool = GetDocumentSummaryTool()
        result = await tool.run(ctx, document_id="d1")

        assert not result.is_error
        assert 'Summary for d1 "readme"' in result.content
        assert "category: guide" in result.content
        assert "total_tokens: 120" in result.content
        repo.get_summary_only.assert_called_once_with("d1")

    async def test_summary_not_found(self):
        repo = MagicMock()
        repo.get_summary_only.return_value = None

        ctx = _make_ctx(document_repo=repo)
        tool = GetDocumentSummaryTool()
        result = await tool.run(ctx, document_id="missing")

        assert result.is_error
        assert "not found" in result.content

    async def test_repo_exception_returns_error(self):
        repo = MagicMock()
        repo.get_summary_only.side_effect = RuntimeError("db down")

        ctx = _make_ctx(document_repo=repo)
        tool = GetDocumentSummaryTool()
        result = await tool.run(ctx, document_id="d1")

        assert result.is_error
        assert "db down" in result.content

    async def test_no_document_id(self):
        ctx = _make_ctx()
        tool = GetDocumentSummaryTool()
        result = await tool.run(ctx)

        assert result.is_error
        assert "document_id is required" in result.content
